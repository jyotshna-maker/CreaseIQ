"""Idempotent database load (FR-04).

Strategy:

* **Dimension tables** (franchise, team_alias, venue, season, player, official) are
  *upserted* on their keys. Player and official ids are stable: existing names keep their
  id and new names get the next free id.
* **Fact tables** (match, match_player) are rebuilt from the canonical match table. They
  are fully derived from the immutable raw file, so a refresh is simpler and safer than a
  row diff.
* ``model_run`` and ``prediction_log`` are operational history and are **never** touched.

All of this runs in one transaction, so a failure leaves the previous database intact
(no partial writes). Loading the same data twice gives identical table contents; a test
checks this.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, cast

import pandas as pd
from sqlalchemy import Engine, Table, delete, func, insert, inspect, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from creaseiq.data.canonical import CanonicalMaps
from creaseiq.db.models import (
    VIEWS,
    Base,
    Franchise,
    Match,
    MatchPlayer,
    Official,
    Player,
    Season,
    TeamAlias,
    Venue,
)
from creaseiq.db.session import session_scope
from creaseiq.logging_setup import get_logger, log_event

logger = get_logger(__name__)
OFFICIAL_COLS = ("match_referee", "umpire1", "umpire2", "tv_umpire", "reserve_umpire")


def create_schema(engine: Engine) -> None:
    """Create all tables and views if they do not exist."""
    Base.metadata.create_all(engine)
    existing = set(inspect(engine).get_view_names())
    with engine.begin() as conn:
        for name, ddl in VIEWS.items():
            if name not in existing:
                conn.execute(text(ddl))


def _upsert(
    session: Session, model: type[Base], rows: Sequence[dict[str, Any]], keys: Iterable[str]
) -> None:
    """Dialect-aware INSERT ... ON CONFLICT DO UPDATE."""
    if not rows:
        return
    table = cast(Table, model.__table__)
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        stmt: Any = sqlite.insert(table)
    elif dialect == "postgresql":
        stmt = postgresql.insert(table)
    else:  # pragma: no cover - other backends fall back to delete+insert per key
        raise NotImplementedError(f"Upsert not implemented for dialect {dialect}")
    keys = list(keys)
    update_cols = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
    stmt = (
        stmt.on_conflict_do_update(index_elements=keys, set_=update_cols)
        if update_cols
        else stmt.on_conflict_do_nothing(index_elements=keys)
    )
    session.execute(stmt, list(rows))


def _ensure_names(
    session: Session, model: type[Player] | type[Official], id_col: str, names: Iterable[str]
) -> dict[str, int]:
    """Insert unseen names with stable, increasing ids; return the full name -> id map."""
    id_attr = getattr(model, id_col)
    existing: dict[str, int] = {
        n: int(i) for n, i in session.execute(select(model.name, id_attr)).all()
    }
    start = max(existing.values(), default=0) + 1
    new = sorted(set(names) - set(existing))
    rows: list[dict[str, Any]] = [{id_col: start + i, "name": n} for i, n in enumerate(new)]
    if rows:
        session.execute(insert(model), rows)
        existing.update({str(r["name"]): int(r[id_col]) for r in rows})
    return existing


def _none(v: Any) -> Any:
    """Convert pandas missing values to None for the DB driver."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def load_database(
    engine: Engine, matches: pd.DataFrame, players: pd.DataFrame, maps: CanonicalMaps
) -> dict[str, int]:
    """Load the canonical tables into the database idempotently.

    Args:
        engine: Target engine.
        matches: Canonical match table (``clean.matches``).
        players: Long player table (``clean.players``).
        maps: Canonical maps (franchise and venue metadata).

    Returns:
        Row counts per table after the load.
    """
    create_schema(engine)
    with session_scope(engine) as s:
        _upsert(
            s,
            Franchise,
            [
                {
                    "franchise_id": fid,
                    "canonical_name": f["name"],
                    "short_code": f["short"],
                    "active": bool(f.get("active", True)),
                    "lineage_note": f.get("note"),
                }
                for fid, f in maps.franchises.items()
            ],
            ["franchise_id"],
        )
        _upsert(
            s,
            TeamAlias,
            [
                {
                    "alias": a.alias,
                    "franchise_id": a.franchise_id,
                    "valid_from_year": a.valid_from,
                    "valid_to_year": a.valid_to,
                }
                for a in maps.team_aliases.values()
            ],
            ["alias"],
        )
        _upsert(
            s,
            Venue,
            [
                {
                    "venue_id": vid,
                    "canonical_name": v["name"],
                    "city": v["city"],
                    "country": v["country"],
                }
                for vid, v in maps.venues.items()
            ],
            ["venue_id"],
        )
        seasons = (
            matches.groupby("season_year")
            .agg(
                raw_label=("season_raw", "first"),
                n_matches=("match_id", "size"),
                champion=("season_champion", "first"),
            )
            .reset_index()
        )
        _upsert(
            s,
            Season,
            [
                {
                    "season_id": int(r.season_year),
                    "season_year": int(r.season_year),
                    "raw_label": r.raw_label,
                    "n_matches": int(r.n_matches),
                    "champion_id": _none(r.champion),
                    "host_note": maps.neutral_seasons.get(int(r.season_year)),
                }
                for r in seasons.itertuples()
            ],
            ["season_id"],
        )
        player_names = set(players["player"]) | set(matches["player_of_match"].dropna())
        pid = _ensure_names(s, Player, "player_id", player_names)
        official_names = set(pd.concat([matches[c] for c in OFFICIAL_COLS]).dropna())
        oid = _ensure_names(s, Official, "official_id", official_names)

        # Facts: refresh in the same transaction.
        s.execute(delete(MatchPlayer))
        s.execute(delete(Match))
        s.execute(
            insert(Match), [_match_row(r, pid, oid) for r in matches.to_dict(orient="records")]
        )
        s.execute(
            insert(MatchPlayer),
            [
                {
                    "match_id": int(r.match_id),
                    "team_id": r.team,
                    "player_id": pid[r.player],
                    "slot_no": int(r.slot_no),
                }
                for r in players.itertuples()
            ],
        )
    counts = table_counts(engine)
    log_event(logger, "db_load", **counts)
    return counts


def _match_row(r: dict[str, Any], pid: dict[str, int], oid: dict[str, int]) -> dict[str, Any]:
    def official(col: str) -> int | None:
        name = _none(r[col])
        return None if name is None else oid[name]

    potm = _none(r["player_of_match"])
    return {
        "match_id": int(r["match_id"]),
        "season_id": int(r["season_year"]),
        "date": pd.Timestamp(r["date"]).date(),
        "match_number": None if _none(r["match_number"]) is None else int(r["match_number"]),
        "stage": r["stage"],
        "venue_id": r["venue_id"],
        "team1_id": r["team1"],
        "team2_id": r["team2"],
        "toss_winner_id": r["toss_winner"],
        "toss_decision": r["toss_decision"],
        "bat_first_id": r["bat_first"],
        "team1_runs": int(r["team1_runs"]),
        "team1_wkts": int(r["team1_wickets"]),
        "team2_runs": int(r["team2_runs"]),
        "team2_wkts": int(r["team2_wickets"]),
        "first_innings_runs": _none(r["first_innings_runs"]),
        "second_innings_runs": _none(r["second_innings_runs"]),
        "winner_id": _none(r["winner"]),
        "super_over_winner_id": _none(r["super_over_winner"]),
        "result_type": r["result_type"],
        "margin_type": _none(r["margin_type"]),
        "margin_value": _none(r["margin_value"]),
        "dls_flag": bool(r["dls_flag"]),
        "voided": bool(r["voided"]),
        "team1_home": bool(r["team1_home"]),
        "team2_home": bool(r["team2_home"]),
        "potm_player_id": None if potm is None else pid[potm],
        "referee_id": official("match_referee"),
        "umpire1_id": official("umpire1"),
        "umpire2_id": official("umpire2"),
        "tv_umpire_id": official("tv_umpire"),
        "reserve_umpire_id": official("reserve_umpire"),
    }


def table_counts(engine: Engine) -> dict[str, int]:
    """Row count of every table (for logging and tests)."""
    with Session(engine) as s:
        return {
            t.name: int(s.execute(select(func.count()).select_from(t)).scalar_one())
            for t in Base.metadata.sorted_tables
        }
