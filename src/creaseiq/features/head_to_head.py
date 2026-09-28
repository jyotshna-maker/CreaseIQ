"""Head-to-head state (FR-12): all-time and recent-seasons records between two franchises."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class HeadToHeadState:
    """Per unordered pair: a list of (season_year, winner) for decided meetings."""

    recent_seasons: int = 5
    prior_m: float = 2.0
    meetings: dict[frozenset[str], list[tuple[int, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def features(self, a: str, b: str, season_year: int) -> dict[str, float]:
        """Antisymmetric H2H edges for A over B, plus the (symmetric) meeting count.

        ``h2h_edge = (wins_a - wins_b) / (n + prior_m)`` lies in (-1, 1) and is 0 with no history.
        """
        games = self.meetings[frozenset((a, b))]
        wa = sum(1 for _, w in games if w == a)
        wb = len(games) - wa
        recent = [(s, w) for s, w in games if s >= season_year - self.recent_seasons]
        ra = sum(1 for _, w in recent if w == a)
        rb = len(recent) - ra
        return {
            "h2h_edge": (wa - wb) / (len(games) + self.prior_m),
            "h2h_recent_edge": (ra - rb) / (len(recent) + self.prior_m),
            "h2h_meetings": float(len(games)),
        }

    def update(self, a: str, b: str, season_year: int, winner: str | None) -> None:
        """Record a decided meeting (ties and no-results are skipped)."""
        if winner is not None:
            self.meetings[frozenset((a, b))].append((season_year, winner))
