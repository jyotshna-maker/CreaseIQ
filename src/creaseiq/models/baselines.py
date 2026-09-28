"""Baselines (FR-14, PLAN §7). Rates are estimated **on the training fold only** (plan review #6).

B0  constant 0.5
B1  chase prior: P(A wins) = training chase-win rate if A bats second (post-toss only)
B2  toss winner: P(A wins) = training toss-winner win rate if A won the toss (post-toss only)
B3  Elo probability: logistic in (elo_diff + home_bonus·home_diff) / scale, with no fitting
B4  venue chase rate: as-of shrunk venue bat-first rate, applied to A's batting order (post-toss)
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from creaseiq.features.builder import Tier

BaselineFn = Callable[[pd.DataFrame, pd.DataFrame, pd.Series], np.ndarray]


def b0_constant(_train: pd.DataFrame, valid: pd.DataFrame, _y: pd.Series) -> np.ndarray:
    """Always 0.5."""
    return np.full(len(valid), 0.5)


def b1_chase_prior(train: pd.DataFrame, valid: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """Training chase-win rate applied to A's batting order."""
    a_chases = train["a_bats_first"] < 0
    chase_rate = float(np.where(a_chases, y, 1 - y).mean())
    return np.where(valid["a_bats_first"] < 0, chase_rate, 1 - chase_rate)


def b2_toss_winner(train: pd.DataFrame, valid: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """Training toss-winner win rate applied to who won the toss."""
    a_toss = train["a_won_toss"] > 0
    rate = float(np.where(a_toss, y, 1 - y).mean())
    return np.where(valid["a_won_toss"] > 0, rate, 1 - rate)


def make_b3_elo(home_bonus: float, scale: float = 400.0) -> BaselineFn:
    """Elo expected score (with the tuned home bonus); needs no training."""

    def b3(_train: pd.DataFrame, valid: pd.DataFrame, _y: pd.Series) -> np.ndarray:
        z = (valid["elo_diff"] + home_bonus * valid["home_diff"]) / scale
        return 1.0 / (1.0 + np.power(10.0, -z.to_numpy()))

    return b3


def b4_venue_chase(_train: pd.DataFrame, valid: pd.DataFrame, _y: pd.Series) -> np.ndarray:
    """As-of shrunk venue bat-first win rate, oriented to A's batting order."""
    bf = valid["venue_bat_first_rate"].to_numpy()
    return np.where(valid["a_bats_first"] > 0, bf, 1 - bf)


def baselines_for(tier: Tier, home_bonus: float) -> dict[str, BaselineFn]:
    """Baselines applicable to a tier (B1, B2 and B4 need post-toss information)."""
    out: dict[str, BaselineFn] = {"B0_constant": b0_constant, "B3_elo": make_b3_elo(home_bonus)}
    if tier == "post_toss":
        out.update(
            {
                "B1_chase_prior": b1_chase_prior,
                "B2_toss_winner": b2_toss_winner,
                "B4_venue_chase": b4_venue_chase,
            }
        )
    return out
