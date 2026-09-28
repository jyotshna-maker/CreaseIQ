"""Shared helpers for the analytics layer: filters and the per-team long view."""

from __future__ import annotations

import pandas as pd


def decided(m: pd.DataFrame) -> pd.DataFrame:
    """Matches with a winner (the population for win-rate statistics)."""
    return m[m["is_decided"]]


def filter_matches(
    m: pd.DataFrame,
    season_from: int | None = None,
    season_to: int | None = None,
    team: str | None = None,
    venue_id: str | None = None,
    stage: str | None = None,
) -> pd.DataFrame:
    """Apply the dashboard filters (FR-11). ``stage`` may be ``league``, ``playoff`` or a label."""
    out = m
    if season_from is not None:
        out = out[out["season_year"] >= season_from]
    if season_to is not None:
        out = out[out["season_year"] <= season_to]
    if team is not None:
        out = out[(out["team1"] == team) | (out["team2"] == team)]
    if venue_id is not None:
        out = out[out["venue_id"] == venue_id]
    if stage == "playoff":
        out = out[out["is_playoff"]]
    elif stage is not None:
        out = out[out["stage"] == stage]
    return out


def team_long(m: pd.DataFrame) -> pd.DataFrame:
    """One row per (match, team) with the opponent and the team's outcome.

    Columns: match_id, date, season_year, venue_id, stage, team, opponent, is_home,
    opp_home, bats_first, won (bool, NA unless decided), is_decided, voided,
    runs_for, runs_against.
    """
    common = ["match_id", "date", "season_year", "venue_id", "stage", "is_decided", "voided"]
    sides = []
    for me, other in (("team1", "team2"), ("team2", "team1")):
        s = m[common].copy()
        s["team"] = m[me]
        s["opponent"] = m[other]
        s["is_home"] = m[f"{me}_home"]
        s["opp_home"] = m[f"{other}_home"]
        s["bats_first"] = m["bat_first"] == m[me]
        s["won"] = (m["winner"] == m[me]).where(m["is_decided"]).astype("boolean")
        s["runs_for"] = m[f"{me}_runs"].where(m["scores_usable"] & (m["result_type"] != "tie"))
        s["runs_against"] = m[f"{other}_runs"].where(
            m["scores_usable"] & (m["result_type"] != "tie")
        )
        sides.append(s)
    return (
        pd.concat(sides, ignore_index=True)
        .sort_values(["date", "match_id", "team"])
        .reset_index(drop=True)
    )
