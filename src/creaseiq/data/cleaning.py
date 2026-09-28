"""Cleaning, canonicalisation and derived columns (FR-02).

Every transformation increments a named counter in ``fixes``. The data-quality report
(FR-03) prints those counters, so each change to the raw data is accounted for.

Key derived columns:

* ``season_year``: calendar year of the season's first match (``"2009/10"`` -> 2010).
* ``bat_first`` / ``chasing_team``: derived from the toss, never from team1/team2 order.
  That order means "batting first" only from 2018 onward (PLAN §2, finding 1).
* ``first_innings_runs`` / ``second_innings_runs``: regulation scores. Tied rows in the
  source include super-over runs, so they are replaced by the verified tied score (ADR-004).
* ``stage``: labelled by era (semi-finals in 2008-10, qualifiers/eliminator from 2011).
* ``dls_flag``: heuristic OR membership of the external D/L list.
* ``voided``: matches abandoned and replayed in full (config list).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from creaseiq.data.canonical import CanonicalMaps
from creaseiq.data.schema import DATE_FORMAT, PLAYER_SEPARATOR
from creaseiq.exceptions import DataValidationError
from creaseiq.logging_setup import get_logger, log_event

logger = get_logger(__name__)

PLAYOFF_STAGES_BY_COUNT: dict[int, tuple[str, ...]] = {
    3: ("semi_final", "semi_final", "final"),
    4: ("qualifier_1", "eliminator", "qualifier_2", "final"),
}
# 2010 had four playoff fixtures but a different format (R10).
PLAYOFF_STAGES_2010 = ("semi_final", "semi_final", "third_place", "final")


@dataclass
class ExternalFacts:
    """Hand-verified facts that are not in the raw CSV (``data/external``)."""

    super_overs: pd.DataFrame
    dls_matches: pd.DataFrame
    voided: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CleanResult:
    """Output of :func:`clean_matches`."""

    matches: pd.DataFrame
    players: pd.DataFrame
    fixes: Counter[str]
    notes: dict[str, Any]


def load_external_facts(external_dir: Path, voided: list[dict[str, Any]]) -> ExternalFacts:
    """Load the super-over and D/L reference tables."""
    so = pd.read_csv(external_dir / "super_over_winners.csv", dtype=str)
    dls = pd.read_csv(external_dir / "dls_matches.csv", dtype=str)
    return ExternalFacts(super_overs=so, dls_matches=dls, voided=list(voided))


def _key(date: str, a: str, b: str) -> tuple[str, frozenset[str]]:
    return (date, frozenset((a, b)))


def season_year_map(df: pd.DataFrame) -> dict[str, int]:
    """Map each raw season label to the calendar year of its first match."""
    dates = pd.to_datetime(df["date"], format=DATE_FORMAT)
    return {str(k): int(v) for k, v in dates.groupby(df["season"]).min().dt.year.items()}


def _split_players(value: str) -> list[str]:
    return [p.strip() for p in str(value).split(PLAYER_SEPARATOR) if p.strip()]


def _assign_stages(m: pd.DataFrame, fixes: Counter[str]) -> pd.Series:
    """Label league vs playoff fixtures by era (rows with no match_number are playoffs)."""
    stage = pd.Series("league", index=m.index, dtype="object")
    for year, grp in m[m["match_number"].isna()].groupby("season_year"):
        grp = grp.sort_values(["date", "match_id"])
        labels = PLAYOFF_STAGES_2010 if year == 2010 else PLAYOFF_STAGES_BY_COUNT.get(len(grp))
        if labels is None:
            raise DataValidationError(f"Unexpected playoff count {len(grp)} in {year}")
        stage.loc[grp.index] = list(labels)
        fixes["stage_derived_playoff"] += len(grp)
    return stage


def clean_matches(valid: pd.DataFrame, maps: CanonicalMaps, facts: ExternalFacts) -> CleanResult:
    """Turn validated raw rows into the canonical match table.

    Args:
        valid: Typed rows from :func:`creaseiq.data.ingest.validate_raw`.
        maps: Canonical maps.
        facts: External verified facts.

    Returns:
        CleanResult with ``matches`` (one row per match), ``players`` (long format),
        the ``fixes`` counters and free-form ``notes`` for the quality report.

    Raises:
        DataValidationError: Unmapped identities or inconsistent reference data.
    """
    fixes: Counter[str] = Counter()
    notes: dict[str, Any] = {}
    raw = valid.copy()
    raw["_date"] = pd.to_datetime(raw["date"], format=DATE_FORMAT)
    raw = raw.sort_values(["_date"], kind="stable").reset_index(drop=True)

    m = pd.DataFrame(index=raw.index)
    m["match_id"] = np.arange(1, len(raw) + 1)
    m["date"] = raw["_date"]
    m["date_raw"] = raw["date"].astype(str)

    # Seasons -------------------------------------------------------------------------
    smap = season_year_map(raw)
    m["season_raw"] = raw["season"].astype(str)
    m["season_year"] = m["season_raw"].map(smap).astype(int)
    fixes["season_label_mapped"] = int((m["season_raw"] != m["season_year"].astype(str)).sum())
    m["match_number"] = raw["match_number"]

    # Teams (fail-loud canonicalisation with validity windows) ------------------------------
    for col in ("team1", "team2", "toss_winner", "winner"):
        m[f"{col}_raw"] = raw[col]
        m[col] = [
            None if pd.isna(v) else maps.team_id(str(v), int(y))
            for v, y in zip(raw[col], m["season_year"], strict=True)
        ]
    renamed = sum(
        int((raw[c].notna() & (raw[c] != raw[c].map(lambda s: _current_name(maps, s)))).sum())
        for c in ("team1", "team2")
    )
    fixes["team_alias_canonicalised"] = renamed

    # Venues and cities ---------------------------------------------------------------
    m["venue_raw"] = raw["venue"]
    m["venue_id"] = [maps.venue_id(str(v)) for v in raw["venue"]]
    m["venue"] = m["venue_id"].map(lambda v: maps.venue_attr(v, "name"))
    m["city_raw"] = raw["city"]
    m["city"] = m["venue_id"].map(lambda v: maps.venue_attr(v, "city"))
    m["country"] = m["venue_id"].map(lambda v: maps.venue_attr(v, "country"))
    fixes["venue_alias_canonicalised"] = int((m["venue_raw"] != m["venue"]).sum())
    fixes["city_unknown_imputed"] = int((raw["city"] == "Unknown").sum())
    fixes["city_corrected"] = int(((raw["city"] != "Unknown") & (raw["city"] != m["city"])).sum())

    # Toss and batting order -----------------------------------------------------------
    m["toss_decision"] = raw["toss_decision"].astype(str)
    toss_bats = m["toss_decision"] == "bat"
    other = np.where(m["toss_winner"] == m["team1"], m["team2"], m["team1"])
    m["bat_first"] = np.where(toss_bats, m["toss_winner"], other)
    m["chasing_team"] = np.where(m["bat_first"] == m["team1"], m["team2"], m["team1"])
    m["team1_bats_first"] = m["bat_first"] == m["team1"]

    # Result ----------------------------------------------------------------------------
    m["result_type"] = raw["result_type"].astype(str)
    decided = m["result_type"] == "complete"
    m["is_decided"] = decided
    m["win_by_runs"] = raw["win_by_runs"].astype(int)
    m["win_by_wickets"] = raw["win_by_wickets"].astype(int)
    margin_type = pd.Series(None, index=m.index, dtype="object")
    margin_type[decided & (m["win_by_runs"] > 0)] = "runs"
    margin_type[decided & (m["win_by_wickets"] > 0)] = "wickets"
    m["margin_type"] = margin_type
    m["margin_value"] = np.where(
        m["margin_type"] == "runs",
        m["win_by_runs"],
        np.where(m["margin_type"] == "wickets", m["win_by_wickets"], np.nan),
    )
    m["bat_first_won"] = pd.array(
        [
            bool(w == b) if d else None
            for w, b, d in zip(m["winner"], m["bat_first"], decided, strict=True)
        ],
        dtype="boolean",
    )
    m["toss_winner_won"] = pd.array(
        [
            bool(w == t) if d else None
            for w, t, d in zip(m["winner"], m["toss_winner"], decided, strict=True)
        ],
        dtype="boolean",
    )

    # Scores (per team, then per innings) -----------------------------------------------
    for c in ("team1_runs", "team1_wickets", "team2_runs", "team2_wickets"):
        m[c] = raw[c].astype(int)
    t1_first = m["team1_bats_first"]
    m["first_innings_runs"] = np.where(t1_first, m["team1_runs"], m["team2_runs"]).astype(float)
    m["second_innings_runs"] = np.where(t1_first, m["team2_runs"], m["team1_runs"]).astype(float)
    m["first_innings_wickets"] = np.where(t1_first, m["team1_wickets"], m["team2_wickets"]).astype(
        float
    )
    m["second_innings_wickets"] = np.where(t1_first, m["team2_wickets"], m["team1_wickets"]).astype(
        float
    )

    # Ties: undo the super-over contamination (ADR-004) ----------------------------------
    so = facts.super_overs
    so_index = {
        _key(r.date, maps.team_id(r.team1), maps.team_id(r.team2)): r for r in so.itertuples()
    }
    m["super_over_winner"] = None
    tie_rows = m.index[m["result_type"] == "tie"]
    matched_ties = 0
    for i in tie_rows:
        rec = so_index.get(_key(m.at[i, "date_raw"], m.at[i, "team1"], m.at[i, "team2"]))
        if rec is None:
            raise DataValidationError(
                f"Tie on {m.at[i, 'date_raw']} missing from super_over_winners.csv"
            )
        tied = float(rec.regulation_score_tied)
        m.loc[i, ["first_innings_runs", "second_innings_runs"]] = tied
        # Regulation wickets are not separable from super-over wickets in the source.
        m.loc[i, ["first_innings_wickets", "second_innings_wickets"]] = np.nan
        m.at[i, "super_over_winner"] = maps.team_id(rec.super_over_winner)
        matched_ties += 1
    fixes["tie_innings_corrected_super_over_removed"] = matched_ties
    # A subset of the data (fixture, upload) legitimately lacks some ties; the full dataset
    # must match all of them, which is asserted by tests/unit/test_cleaning.py.
    notes["super_over_records_unmatched"] = len(so) - matched_ties

    # Voided / no-result ----------------------------------------------------------------
    voided_keys = {
        _key(v["date"], maps.team_id(v["teams"][0]), maps.team_id(v["teams"][1]))
        for v in facts.voided
    }
    m["voided"] = [
        _key(d, a, b) in voided_keys
        for d, a, b in zip(m["date_raw"], m["team1"], m["team2"], strict=True)
    ]
    fixes["voided_flagged"] = int(m["voided"].sum())
    # Scores from abandoned games are not comparable, so blank them for scoring statistics.
    no_score = (m["result_type"] == "no result") | m["voided"]
    m["scores_usable"] = ~no_score
    fixes["no_result_scores_excluded"] = int(no_score.sum())

    # D/L -------------------------------------------------------------------------------
    winner_runs = np.where(m["winner"] == m["team1"], m["team1_runs"], m["team2_runs"])
    loser_runs = np.where(m["winner"] == m["team1"], m["team2_runs"], m["team1_runs"])
    runs_heuristic = decided & (winner_runs <= loser_runs)
    margin_heuristic = decided & (
        (m["bat_first_won"].fillna(False) & (m["win_by_wickets"] > 0))
        | (~m["bat_first_won"].fillna(True) & (m["win_by_runs"] > 0))
    )
    m["dls_heuristic"] = runs_heuristic | margin_heuristic
    dls_keys = {
        _key(r.date, maps.team_id(r.team_a), maps.team_id(r.team_b))
        for r in facts.dls_matches.itertuples()
    }
    m["dls_external"] = [
        _key(d, a, b) in dls_keys
        for d, a, b in zip(m["date_raw"], m["team1"], m["team2"], strict=True)
    ]
    m["dls_flag"] = m["dls_heuristic"] | m["dls_external"]
    fixes["dls_flag_heuristic"] = int(m["dls_heuristic"].sum())
    fixes["dls_flag_external"] = int(m["dls_external"].sum())
    fixes["dls_flag_total"] = int(m["dls_flag"].sum())
    notes["dls_external_unmatched"] = len(dls_keys) - int(m["dls_external"].sum())

    # Stages, finals, champions ---------------------------------------------------------
    m["stage"] = _assign_stages(m, fixes)
    m["is_playoff"] = m["stage"] != "league"
    m["is_final"] = m["stage"] == "final"
    champions = m.loc[m["is_final"]].set_index("season_year")["winner"].to_dict()
    m["season_champion"] = m["season_year"].map(champions)

    # Eras, home, context -------------------------------------------------------------
    m["impact_era"] = m["season_year"] >= 2023
    m["neutral_season"] = m["season_year"].map(maps.is_neutral_season)
    m["team1_home"] = [
        maps.is_home(t, v, y)
        for t, v, y in zip(m["team1"], m["venue_id"], m["season_year"], strict=True)
    ]
    m["team2_home"] = [
        maps.is_home(t, v, y)
        for t, v, y in zip(m["team2"], m["venue_id"], m["season_year"], strict=True)
    ]

    # People ------------------------------------------------------------------------------
    for c in (
        "player_of_match",
        "match_referee",
        "umpire1",
        "umpire2",
        "tv_umpire",
        "reserve_umpire",
    ):
        m[c] = raw[c]
    t1p = raw["team1_players"].map(_split_players)
    t2p = raw["team2_players"].map(_split_players)
    m["n_players_t1"] = t1p.map(len)
    m["n_players_t2"] = t2p.map(len)
    players = _players_long(m, t1p, t2p)
    fixes["player_lists_parsed"] = len(m) * 2

    notes["n_matches"] = len(m)
    notes["n_decided"] = int(decided.sum())
    log_event(logger, "clean", rows=len(m), decided=int(decided.sum()), fixes=sum(fixes.values()))
    return CleanResult(matches=m, players=players, fixes=fixes, notes=notes)


def _current_name(maps: CanonicalMaps, raw_name: str) -> str:
    return maps.team_name(maps.team_id(raw_name))


def _players_long(m: pd.DataFrame, t1p: pd.Series, t2p: pd.Series) -> pd.DataFrame:
    rows: list[tuple[int, str, str, int]] = []
    for mid, a, b, pa_, pb_ in zip(m["match_id"], m["team1"], m["team2"], t1p, t2p, strict=True):
        rows.extend((int(mid), a, name, slot) for slot, name in enumerate(pa_, 1))
        rows.extend((int(mid), b, name, slot) for slot, name in enumerate(pb_, 1))
    out = pd.DataFrame(rows, columns=["match_id", "team", "player", "slot_no"])
    dup = out.duplicated(["match_id", "team", "player"])
    if dup.any():
        raise DataValidationError(
            "Duplicate player within one team's list", out.index[dup].tolist()
        )
    return out
