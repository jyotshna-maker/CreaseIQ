"""Venue state (FR-12): as-of, shrunk venue scoring and chase rates, plus team-at-venue records.

Everything is computed from matches *before* the current date. The shrinkage prior is the
league-wide value observed so far, not the all-data value, so no future information leaks
into it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from creaseiq.analytics.hypothesis_tests import shrunk_mean, shrunk_rate

DEFAULT_FIRST_INNINGS = 160.0  # prior before any match has been observed
DEFAULT_BAT_FIRST_RATE = 0.5


@dataclass
class VenueState:
    """Running venue and team-at-venue counters."""

    prior_m: float = 10.0
    runs_sum: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    runs_n: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    bf_wins: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    decided: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    team_wins: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    team_games: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    global_runs_sum: float = 0.0
    global_runs_n: int = 0
    global_bf_wins: int = 0
    global_decided: int = 0

    @property
    def global_first_innings(self) -> float:
        """League mean first-innings score so far."""
        return (
            self.global_runs_sum / self.global_runs_n
            if self.global_runs_n
            else DEFAULT_FIRST_INNINGS
        )

    @property
    def global_bat_first_rate(self) -> float:
        """League bat-first win rate so far."""
        return (
            self.global_bf_wins / self.global_decided
            if self.global_decided
            else DEFAULT_BAT_FIRST_RATE
        )

    def features(self, venue: str, a: str, b: str) -> dict[str, float]:
        """Symmetric venue context plus A-minus-B team-at-venue edge."""
        m = self.prior_m
        wa = shrunk_rate(self.team_wins[(a, venue)], self.team_games[(a, venue)], 0.5, m / 2)
        wb = shrunk_rate(self.team_wins[(b, venue)], self.team_games[(b, venue)], 0.5, m / 2)
        return {
            "venue_first_innings": shrunk_mean(
                self.runs_sum[venue], self.runs_n[venue], self.global_first_innings, m
            ),
            "venue_bat_first_rate": shrunk_rate(
                self.bf_wins[venue], self.decided[venue], self.global_bat_first_rate, m
            ),
            "venue_team_edge": wa - wb,
        }

    def update(
        self,
        venue: str,
        first_innings: float | None,
        bat_first_won: bool | None,
        a: str,
        b: str,
        winner: str | None,
    ) -> None:
        """Record one match at ``venue``."""
        if first_innings is not None:
            self.runs_sum[venue] += first_innings
            self.runs_n[venue] += 1
            self.global_runs_sum += first_innings
            self.global_runs_n += 1
        if bat_first_won is not None:
            self.bf_wins[venue] += int(bat_first_won)
            self.decided[venue] += 1
            self.global_bf_wins += int(bat_first_won)
            self.global_decided += 1
        if winner is not None:
            for team in (a, b):
                self.team_games[(team, venue)] += 1
                self.team_wins[(team, venue)] += int(winner == team)
