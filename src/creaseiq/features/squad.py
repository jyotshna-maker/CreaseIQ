"""Squad (XI) state for the post-toss tier (FR-12).

The playing XI (XII from 2023) is announced at the toss, so these features belong to Tier B
only. They use each player's appearances and Player-of-the-Match awards from **earlier**
matches.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SquadState:
    """Per-player appearance and POTM counts, plus each team's previous XI."""

    appearances: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    potm: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_xi: dict[str, frozenset[str]] = field(default_factory=dict)

    def features(self, team: str, xi: frozenset[str]) -> dict[str, float]:
        """Experience (hundreds of prior caps), prior POTM awards, debutants and continuity."""
        prev = self.last_xi.get(team)
        continuity = len(prev & xi) / len(prev | xi) if prev else 0.0
        return {
            "xi_experience": sum(self.appearances[p] for p in xi) / 100.0,
            "xi_potm": float(sum(self.potm[p] for p in xi)),
            "xi_debutants": float(sum(1 for p in xi if self.appearances[p] == 0)),
            "xi_continuity": continuity,
        }

    def update(self, team: str, xi: frozenset[str], potm: str | None) -> None:
        """Record that ``xi`` played for ``team``; credit the POTM if they were in it."""
        for p in xi:
            self.appearances[p] += 1
        if potm is not None and potm in xi:
            self.potm[potm] += 1
        self.last_xi[team] = xi
