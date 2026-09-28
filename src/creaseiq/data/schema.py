"""Raw-data contract (FR-01): column schema plus row-level business rules.

Validation runs in two layers:

1. A **pandera** schema checks column presence, dtypes, allowed values, value ranges and
   the columns that must be constant.
2. **Row rules** are vectorised checks that span several columns, such as "the toss winner
   is one of the two teams". Each rule returns a boolean mask of *violating* rows, so a
   lenient run can quarantine exactly those rows with a named reason.

Raw wickets may exceed 10 only on tied rows, because the source adds super-over wickets to
the innings total (research R8, ADR-004).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
import pandera.pandas as pa

RAW_COLUMNS: tuple[str, ...] = (
    "event_name", "season", "match_number", "date", "city", "venue", "team1", "team2",
    "toss_winner", "toss_decision", "team1_runs", "team1_wickets", "team2_runs",
    "team2_wickets", "winner", "result_type", "win_by_runs", "win_by_wickets",
    "player_of_match", "match_referee", "umpire1", "umpire2", "tv_umpire", "reserve_umpire",
    "match_type", "overs_limit", "balls_per_over", "gender", "team_type",
    "team1_players", "team2_players",
)  # fmt: skip

CONSTANT_COLUMNS: dict[str, object] = {
    "event_name": "Indian Premier League",
    "match_type": "T20",
    "overs_limit": 20,
    "balls_per_over": 6,
    "gender": "male",
    "team_type": "club",
}

RESULT_TYPES = ("complete", "tie", "no result")
TOSS_DECISIONS = ("bat", "field")
PLAYER_SEPARATOR = ", "
DATE_FORMAT = "%d-%m-%Y"


def _str_col(nullable: bool = False, **kw: object) -> pa.Column:
    return pa.Column(str, nullable=nullable, coerce=True, **kw)  # type: ignore[arg-type]


RAW_SCHEMA = pa.DataFrameSchema(
    {
        "event_name": _str_col(checks=pa.Check.isin([CONSTANT_COLUMNS["event_name"]])),
        "season": _str_col(checks=pa.Check.str_matches(r"^\d{4}(/\d{2})?$")),
        "match_number": pa.Column(float, nullable=True, coerce=True, checks=pa.Check.ge(1)),
        "date": _str_col(checks=pa.Check.str_matches(r"^\d{2}-\d{2}-\d{4}$")),
        "city": _str_col(),
        "venue": _str_col(),
        "team1": _str_col(),
        "team2": _str_col(),
        "toss_winner": _str_col(),
        "toss_decision": _str_col(checks=pa.Check.isin(list(TOSS_DECISIONS))),
        "team1_runs": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 350)),
        "team1_wickets": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 20)),
        "team2_runs": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 350)),
        "team2_wickets": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 20)),
        "winner": _str_col(nullable=True),
        "result_type": _str_col(checks=pa.Check.isin(list(RESULT_TYPES))),
        "win_by_runs": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 300)),
        "win_by_wickets": pa.Column(int, coerce=True, checks=pa.Check.in_range(0, 10)),
        "player_of_match": _str_col(nullable=True),
        "match_referee": _str_col(nullable=True),
        "umpire1": _str_col(nullable=True),
        "umpire2": _str_col(nullable=True),
        "tv_umpire": _str_col(nullable=True),
        "reserve_umpire": _str_col(nullable=True),
        "match_type": _str_col(checks=pa.Check.isin([CONSTANT_COLUMNS["match_type"]])),
        "overs_limit": pa.Column(
            int, coerce=True, checks=pa.Check.isin([CONSTANT_COLUMNS["overs_limit"]])
        ),
        "balls_per_over": pa.Column(
            int, coerce=True, checks=pa.Check.isin([CONSTANT_COLUMNS["balls_per_over"]])
        ),
        "gender": _str_col(checks=pa.Check.isin([CONSTANT_COLUMNS["gender"]])),
        "team_type": _str_col(checks=pa.Check.isin([CONSTANT_COLUMNS["team_type"]])),
        "team1_players": _str_col(),
        "team2_players": _str_col(),
    },
    strict=True,
    ordered=False,
)


@dataclass(frozen=True)
class RowRule:
    """A named cross-column rule; ``violations(df)`` is True where a row breaks it."""

    name: str
    description: str
    violations: Callable[[pd.DataFrame], pd.Series]


def _players(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].astype(str).str.split(PLAYER_SEPARATOR).str.len()


ROW_RULES: tuple[RowRule, ...] = (
    RowRule(
        "distinct_teams",
        "team1 and team2 must differ",
        lambda d: d["team1"] == d["team2"],
    ),
    RowRule(
        "toss_winner_in_match",
        "toss_winner must be team1 or team2",
        lambda d: ~((d["toss_winner"] == d["team1"]) | (d["toss_winner"] == d["team2"])),
    ),
    RowRule(
        "winner_in_match",
        "winner, when present, must be team1 or team2",
        lambda d: (
            d["winner"].notna() & ~((d["winner"] == d["team1"]) | (d["winner"] == d["team2"]))
        ),
    ),
    RowRule(
        "winner_iff_complete",
        "winner is present exactly when result_type == 'complete'",
        lambda d: d["winner"].notna() != (d["result_type"] == "complete"),
    ),
    RowRule(
        "single_margin",
        "a complete result has exactly one positive margin (runs xor wickets)",
        lambda d: (
            (d["result_type"] == "complete") & ((d["win_by_runs"] > 0) == (d["win_by_wickets"] > 0))
        ),
    ),
    RowRule(
        "no_margin_without_result",
        "ties and no-results carry no margin",
        lambda d: (
            (d["result_type"] != "complete") & ((d["win_by_runs"] > 0) | (d["win_by_wickets"] > 0))
        ),
    ),
    RowRule(
        "wickets_le_10_unless_tie",
        "innings wickets <= 10 except on ties (super-over wickets are added; R8)",
        lambda d: (
            (d["result_type"] != "tie") & ((d["team1_wickets"] > 10) | (d["team2_wickets"] > 10))
        ),
    ),
    RowRule(
        "valid_date",
        "date parses as dd-mm-yyyy",
        lambda d: pd.to_datetime(d["date"], format=DATE_FORMAT, errors="coerce").isna(),
    ),
    RowRule(
        "squad_size",
        "each side lists 11-13 players (12 is normal from 2023: Impact Player)",
        lambda d: (
            ~_players(d, "team1_players").between(11, 13)
            | ~_players(d, "team2_players").between(11, 13)
        ),
    ),
)
