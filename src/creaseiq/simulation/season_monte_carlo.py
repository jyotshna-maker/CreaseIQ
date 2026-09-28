"""Hypothetical season simulation (FR-20, P2).

A season is simulated as a double round-robin (each pair meets home and away), then the
2011+ playoff format: Q1 (1st v 2nd), Eliminator (3rd v 4th), Q2 (loser Q1 v winner
Eliminator) and the Final. Match probabilities come from the pre-toss model through a
supplied pairwise probability matrix. This is **hypothetical**. The real IPL uses groups,
and squads change at auctions, so the odds illustrate model beliefs, not forecasts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_season(
    teams: list[str], p_home: np.ndarray, n_sims: int = 10_000, seed: int = 42
) -> pd.DataFrame:
    """Monte Carlo title and top-4 odds.

    Args:
        teams: Franchise ids.
        p_home: ``p_home[i, j]`` = P(team i beats team j when i is at home).
        n_sims: Number of simulated seasons.
        seed: RNG seed (NFR-06).

    Returns:
        One row per team: mean wins, P(top 4), P(reach final), P(title).
    """
    n = len(teams)
    rng = np.random.default_rng(seed)
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]  # i at home vs j
    probs = np.array([p_home[i, j] for i, j in pairs])
    wins = np.zeros((n_sims, n))
    outcomes = rng.random((n_sims, len(pairs))) < probs
    for k, (i, j) in enumerate(pairs):
        wins[:, i] += outcomes[:, k]
        wins[:, j] += ~outcomes[:, k]
    # Random tie-break (standing in for net run rate).
    order = np.argsort(-(wins + rng.random((n_sims, n)) * 0.1), axis=1)
    top4 = order[:, :4]
    neutral = (p_home + (1 - p_home.T)) / 2  # playoff venues treated as neutral

    def play(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a_wins = rng.random(len(a)) < neutral[a, b]
        return np.where(a_wins, a, b), np.where(a_wins, b, a)

    q1_w, q1_l = play(top4[:, 0], top4[:, 1])
    el_w, _ = play(top4[:, 2], top4[:, 3])
    q2_w, _ = play(q1_l, el_w)
    champ, runner = play(q1_w, q2_w)
    rows = []
    for t in range(n):
        rows.append(
            {
                "team": teams[t],
                "mean_wins": float(wins[:, t].mean()),
                "p_top4": float((top4 == t).any(axis=1).mean()),
                "p_final": float(((champ == t) | (runner == t)).mean()),
                "p_title": float((champ == t).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("p_title", ascending=False).reset_index(drop=True)
