"""Margin-aware Elo ratings with season carry-over (FR-13).

Design (research R3):

* **Expected score** of A vs B: ``1 / (1 + 10^(-(R_A - R_B + H) / scale))``. ``H`` is the home
  bonus times ``(a_home - b_home)``, so it applies only when exactly one side is at home.
* **Update:** ``R += K_eff * mult * (S - E)`` with ``S`` = 1/0 for a win or loss and 0.5 for a
  tie. No-results and voided matches do not update ratings.
* **Margin-of-victory multiplier** (FiveThirtyEight form):
  ``ln(units + 1) * 2.2 / (0.001 * elo_diff_winner + 2.2)``. The denominator stops
  favourites' ratings from inflating. Margins are converted to comparable units:
  runs / 10 or wickets / 2 (the median win of about 20 runs or about 6 wickets both give
  2–3 units). D/L results use a multiplier of 1 because their margins are not comparable.
* **Season carry-over:** at each new season every rating moves a fraction
  ``season_regression`` of the way back to the mean. Auctions reshuffle squads, so last
  season's strength only partly carries over.
* **Optional early-season K boost:** ``K_eff = K * (1 + boost * max(0, 1 - games / 7))``.
* Ratings are zero-sum: the total rating mass is conserved by every update.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class EloParams:
    """Elo hyperparameters (tuned by walk-forward log-loss in Phase 4)."""

    initial: float = 1500.0
    scale: float = 400.0
    k: float = 20.0
    home_bonus: float = 30.0
    season_regression: float = 0.33
    use_margin: bool = True
    early_season_k_boost: float = 0.0


def expected_score(r_a: float, r_b: float, scale: float = 400.0, home_adv: float = 0.0) -> float:
    """Probability that A beats B under the Elo model."""
    return 1.0 / (1.0 + 10.0 ** (-(r_a - r_b + home_adv) / scale))


def margin_units(margin_type: str | None, margin_value: float | None) -> float:
    """Convert a winning margin to comparable units (runs/10 or wickets/2)."""
    if margin_type == "runs" and margin_value is not None:
        return float(margin_value) / 10.0
    if margin_type == "wickets" and margin_value is not None:
        return float(margin_value) / 2.0
    return 0.0


def margin_multiplier(units: float, winner_elo_diff: float) -> float:
    """FiveThirtyEight margin-of-victory multiplier with autocorrelation correction."""
    return math.log(max(units, 0.0) + 1.0) * 2.2 / (0.001 * winner_elo_diff + 2.2)


@dataclass
class EloRatingSystem:
    """Stateful Elo engine. Call :meth:`start_season` before a season's first date batch."""

    params: EloParams = field(default_factory=EloParams)
    ratings: dict[str, float] = field(default_factory=dict)
    games_this_season: dict[str, int] = field(default_factory=dict)
    season: int | None = None
    history: list[dict[str, object]] = field(default_factory=list)

    def rating(self, team: str) -> float:
        """Current rating (new teams start at ``params.initial``)."""
        return self.ratings.get(team, self.params.initial)

    def start_season(self, season_year: int) -> None:
        """Apply the season carry-over when a new season begins (idempotent within a season)."""
        if self.season == season_year:
            return
        if self.season is not None:
            lam = self.params.season_regression
            mean = self.params.initial
            self.ratings = {t: r - lam * (r - mean) for t, r in self.ratings.items()}
        self.season = season_year
        self.games_this_season = {}

    def home_adv(self, a_home: bool, b_home: bool) -> float:
        """Home advantage in rating points from A's perspective."""
        return self.params.home_bonus * (int(a_home) - int(b_home))

    def win_probability(self, a: str, b: str, a_home: bool = False, b_home: bool = False) -> float:
        """P(A beats B) from current ratings."""
        return expected_score(
            self.rating(a), self.rating(b), self.params.scale, self.home_adv(a_home, b_home)
        )

    def _k(self, team: str) -> float:
        boost = self.params.early_season_k_boost
        games = self.games_this_season.get(team, 0)
        return self.params.k * (1.0 + boost * max(0.0, 1.0 - games / 7.0))

    def compute_update(
        self,
        a: str,
        b: str,
        score_a: float,
        a_home: bool = False,
        b_home: bool = False,
        margin_type: str | None = None,
        margin_value: float | None = None,
        dls: bool = False,
    ) -> tuple[float, float]:
        """Return rating deltas (dA, dB) for one result without applying them.

        ``score_a`` is 1 (A won), 0 (B won) or 0.5 (tie).
        """
        ra, rb = self.rating(a), self.rating(b)
        e_a = expected_score(ra, rb, self.params.scale, self.home_adv(a_home, b_home))
        mult = 1.0
        if self.params.use_margin and score_a in (0.0, 1.0) and not dls:
            winner_diff = (ra - rb) if score_a == 1.0 else (rb - ra)
            units = margin_units(margin_type, margin_value)
            if units > 0:
                mult = margin_multiplier(units, winner_diff)
        k = (self._k(a) + self._k(b)) / 2.0
        delta = k * mult * (score_a - e_a)
        return delta, -delta

    def apply(self, deltas: dict[str, float], played: list[str]) -> None:
        """Apply accumulated deltas for a date batch and count games played."""
        for team, d in deltas.items():
            self.ratings[team] = self.rating(team) + d
        for team in played:
            self.ratings.setdefault(team, self.params.initial)
            self.games_this_season[team] = self.games_this_season.get(team, 0) + 1

    def history_frame(self) -> pd.DataFrame:
        """Rating history (one row per team per rated match)."""
        return pd.DataFrame(self.history)
