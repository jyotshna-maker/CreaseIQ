"""Probability calibration (FR-15; research R7).

We compare three options: no calibration, Platt (sigmoid) and isotonic. Each is evaluated in
**time order**: the calibrator applied to season S is fitted only on out-of-fold predictions
from seasons before S. scikit-learn's ``CalibratedClassifierCV`` is not used, because its
default CV is not time-aware. With fewer than about 1,000 calibration points, isotonic
tends to overfit (Niculescu-Mizil & Caruana 2005), so the simpler method wins ties.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from creaseiq.models.evaluate import log_loss

Method = Literal["none", "sigmoid", "isotonic"]
METHODS: tuple[Method, ...] = ("none", "sigmoid", "isotonic")
EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


@dataclass
class Calibrator:
    """A fitted probability mapping. ``none`` is the identity map."""

    method: Method
    platt: LogisticRegression | None = None
    iso: IsotonicRegression | None = None

    def fit(self, p: np.ndarray, y: np.ndarray) -> Calibrator:
        """Fit on (prediction, outcome) pairs."""
        if self.method == "sigmoid":
            self.platt = LogisticRegression(C=1e6, max_iter=1000).fit(
                _logit(p).reshape(-1, 1), y.astype(int)
            )
        elif self.method == "isotonic":
            self.iso = IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1 - EPS).fit(p, y)
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        """Map raw probabilities to calibrated ones."""
        p = np.asarray(p, dtype=float)
        if self.method == "sigmoid" and self.platt is not None:
            return np.asarray(self.platt.predict_proba(_logit(p).reshape(-1, 1))[:, 1])
        if self.method == "isotonic" and self.iso is not None:
            return np.asarray(self.iso.predict(p))
        return p

    def symmetric_transform(self, p: np.ndarray) -> np.ndarray:
        """Calibrate while keeping p(A,B) = 1 − p(B,A): average g(p) and 1 − g(1 − p)."""
        return 0.5 * (self.transform(p) + 1.0 - self.transform(1.0 - np.asarray(p, dtype=float)))


def time_ordered_calibration(
    oof: pd.Series, y: pd.Series, seasons: pd.Series, min_history_seasons: int = 2
) -> dict[str, dict[str, float]]:
    """Log-loss of each method when season S uses a calibrator fitted on seasons < S.

    Returns ``{method: {season: log_loss, ..., "mean": ...}}`` over the seasons that have
    at least ``min_history_seasons`` earlier OOF seasons.
    """
    s = seasons.loc[oof.index]
    yy = y.loc[oof.index].to_numpy()
    pp = oof.to_numpy()
    uniq = sorted(s.unique())
    out: dict[str, dict[str, float]] = {m: {} for m in METHODS}
    for season in uniq[min_history_seasons:]:
        hist, cur = (s < season).to_numpy(), (s == season).to_numpy()
        for method in METHODS:
            cal = Calibrator(method).fit(pp[hist], yy[hist])
            out[method][str(season)] = log_loss(yy[cur], cal.symmetric_transform(pp[cur]))
    for method in METHODS:
        vals = list(out[method].values())
        out[method]["mean"] = float(np.mean(vals)) if vals else float("nan")
    return out


def choose_method(comparison: dict[str, dict[str, float]], tolerance: float = 1e-3) -> Method:
    """Pick the simplest method whose mean log-loss is within ``tolerance`` of the best."""
    best = min(comparison[m]["mean"] for m in METHODS)
    for method in METHODS:  # ordered simplest first
        if comparison[method]["mean"] <= best + tolerance:
            return method
    return "none"
