"""Analytics service: filtered analytics for the dashboard, plus safe CSV export (FR-06..FR-11)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from creaseiq.analytics import (
    player_stats,
    season_trends,
    team_stats,
    toss_analysis,
    venue_clusters,
    venue_stats,
)
from creaseiq.analytics.common import filter_matches
from creaseiq.services.context import AppContext

# Leading characters that make spreadsheet apps treat a cell as a formula (CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: Any) -> Any:
    """Neutralise spreadsheet formulas by prefixing a single quote (NFR-03)."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_safe_csv(df: pd.DataFrame) -> bytes:
    """CSV bytes with every string cell (and header) sanitised."""
    safe = df.copy()
    safe.columns = [sanitize_cell(str(c)) for c in safe.columns]
    for col in safe.columns:
        if safe[col].dtype == object or pd.api.types.is_string_dtype(safe[col]):
            safe[col] = safe[col].map(sanitize_cell)
    buf = io.StringIO()
    safe.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


EXPLORER_COLUMNS = [
    "date",
    "season_year",
    "stage",
    "team1",
    "team2",
    "venue",
    "city",
    "toss_winner",
    "toss_decision",
    "bat_first",
    "first_innings_runs",
    "second_innings_runs",
    "winner",
    "result_type",
    "margin_type",
    "margin_value",
    "dls_flag",
    "player_of_match",
]


class AnalyticsService:
    """Thin, filter-aware facade over the pure analytics functions."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    def filtered(
        self,
        season_from: int | None = None,
        season_to: int | None = None,
        team: str | None = None,
        venue_id: str | None = None,
        stage: str | None = None,
    ) -> pd.DataFrame:
        """Matches after dashboard filters."""
        return filter_matches(self.ctx.matches, season_from, season_to, team, venue_id, stage)

    def explorer_table(self, m: pd.DataFrame) -> pd.DataFrame:
        """Readable match table for the Data Explorer."""
        out = m[EXPLORER_COLUMNS].copy()
        for col in ("team1", "team2", "toss_winner", "bat_first", "winner"):
            out[col] = out[col].map(lambda v: self.ctx.team_label(v) if isinstance(v, str) else v)
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        return out.reset_index(drop=True)

    def kpis(self) -> dict[str, Any]:
        """Headline numbers for the home page."""
        m = self.ctx.matches
        return {
            "matches": len(m),
            "decided": int(m["is_decided"].sum()),
            "seasons": int(m["season_year"].nunique()),
            "franchises": int(pd.concat([m["team1"], m["team2"]]).nunique()),
            "venues": int(m["venue_id"].nunique()),
            "first_date": m["date"].min().strftime("%Y-%m-%d"),
            "last_date": m["date"].max().strftime("%Y-%m-%d"),
            "latest_champion": self.ctx.team_label(
                str(m.loc[m["is_final"]].sort_values("date").iloc[-1]["winner"])
            ),
        }

    def team_table(self, m: pd.DataFrame) -> pd.DataFrame:
        """Team records."""
        return team_stats.team_table(m)

    def season_form(self, m: pd.DataFrame) -> pd.DataFrame:
        """Season win% per team."""
        return team_stats.season_win_pct(m)

    def h2h_matrix(self, m: pd.DataFrame, min_meetings: int) -> pd.DataFrame:
        """Head-to-head win% matrix."""
        return team_stats.head_to_head_matrix(m, min_meetings)

    def venue_profiles(self, m: pd.DataFrame) -> pd.DataFrame:
        """Shrunk venue profiles."""
        return venue_stats.venue_profiles(m)

    def venue_clusters(self, m: pd.DataFrame) -> venue_clusters.VenueClustering:
        """k-means venue clusters."""
        return venue_clusters.cluster_venues(
            venue_stats.venue_profiles(m), seed=self.ctx.settings.seed
        )

    def toss(self, m: pd.DataFrame) -> dict[str, Any]:
        """Toss effect and chasing advantage."""
        return {
            "toss": toss_analysis.toss_effect(m),
            "chase": toss_analysis.chasing_advantage(m),
            "field_share": toss_analysis.field_first_share(m),
        }

    def scoring(self, m: pd.DataFrame) -> pd.DataFrame:
        """Scoring trend by season."""
        return season_trends.scoring_by_season(m)

    def potm(self, m: pd.DataFrame, top: int = 15) -> pd.DataFrame:
        """Player-of-the-Match leaderboard."""
        return player_stats.potm_leaderboard(m, self.ctx.players, top)

    def elo_history(self) -> pd.DataFrame:
        """Tuned Elo history (from the processed cache written by `creaseiq features/train`)."""
        path = self.ctx.settings.path("processed_dir") / "elo_history.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()
