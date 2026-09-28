"""Chronological splits (FR-14; research R7).

* **Development seasons** (≤ ``dev_last_season``) are used for all tuning and model selection,
  through an expanding-window walk-forward: train on seasons < S, validate on S.
* **Holdout seasons** (2025, 2026) are evaluated once, after the model is frozen.

Random K-fold is forbidden for time-ordered data. Every fold is checked to be chronological.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from creaseiq.exceptions import InputError


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold: boolean masks over the frame it was built from."""

    season: int
    train: np.ndarray
    valid: np.ndarray


def assert_chronological(
    train_seasons: pd.Series | np.ndarray, valid_seasons: pd.Series | np.ndarray
) -> None:
    """Raise if any training season is not strictly earlier than every validation season."""
    tr, va = np.asarray(train_seasons), np.asarray(valid_seasons)
    if len(tr) == 0 or len(va) == 0:
        raise InputError("Empty train or validation fold")
    if tr.max() >= va.min():
        raise InputError(
            f"Non-chronological fold: train up to {tr.max()}, validate from {va.min()}"
        )


def walk_forward_folds(seasons: pd.Series, first_valid: int, last_valid: int) -> list[Fold]:
    """Expanding-window folds for validation seasons ``first_valid..last_valid`` (inclusive)."""
    s = np.asarray(seasons)
    folds = []
    for season in range(first_valid, last_valid + 1):
        train, valid = s < season, s == season
        if not valid.any():
            continue
        assert_chronological(s[train], s[valid])
        folds.append(Fold(season, train, valid))
    return folds


def dev_holdout_masks(
    seasons: pd.Series, dev_last: int, holdout: list[int]
) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks for the development and holdout periods (must be disjoint and ordered)."""
    s = np.asarray(seasons)
    dev, hold = s <= dev_last, np.isin(s, holdout)
    if (dev & hold).any():
        raise InputError("Development and holdout seasons overlap")
    if hold.any():
        assert_chronological(s[dev], s[hold])
    return dev, hold
