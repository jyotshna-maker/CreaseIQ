"""Model families, walk-forward training and model selection (FR-14).

Five model families. The search spaces are deliberately small: with about 1.2k matches,
heavy tuning would overfit the validation folds.

* ``elo_logit``: logistic regression on ``elo_diff`` and ``home_diff`` only. An
  interpretable ablation.
* ``logreg``: L2 logistic regression on all **antisymmetric** features, with **no
  intercept** and scaling but no centring. The logit is then an odd function of the
  features, so p(A,B) = 1 − p(B,A) exactly.
* ``random_forest`` and ``hist_gb``: tree ensembles on all features, including the
  symmetric context, which trees can use through interactions.
* ``blend``: a convex combination of ``logreg`` and ``hist_gb``.

Every model is wrapped in :class:`SymmetricModel`, which averages the two orientations at
prediction time (ADR-005).

**Selection rule (ADR-006):** the lowest walk-forward mean log-loss, subject to the
*one-standard-error rule*: take the simplest model whose mean is within one SE of the best.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from creaseiq.features.builder import Tier, antisymmetric_columns, feature_columns, swap_orientation
from creaseiq.models.evaluate import log_loss
from creaseiq.models.splits import Fold

COMPLEXITY_ORDER = ("elo_logit", "logreg", "random_forest", "hist_gb", "blend")


def _logreg(c: float) -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler(with_mean=False)),
            ("lr", LogisticRegression(C=c, fit_intercept=False, max_iter=5000)),
        ]
    )


@dataclass(frozen=True)
class ModelSpec:
    """A model family: how to build it, which columns it sees, and its search space."""

    name: str
    grid: tuple[dict[str, Any], ...]
    columns: Callable[[Tier], list[str]]
    build: Callable[[dict[str, Any], int], BaseEstimator]


def _grid(**axes: list[Any]) -> tuple[dict[str, Any], ...]:
    keys = list(axes)
    return tuple(dict(zip(keys, vals, strict=True)) for vals in itertools.product(*axes.values()))


SPECS: dict[str, ModelSpec] = {
    "elo_logit": ModelSpec("elo_logit", _grid(C=[1.0]), lambda _t: ["elo_diff", "home_diff"], lambda p, _s: _logreg(p["C"])),
    "logreg": ModelSpec("logreg", _grid(C=[0.003, 0.01, 0.03, 0.1, 1.0]), antisymmetric_columns, lambda p, _s: _logreg(p["C"])),
    "random_forest": ModelSpec(
        "random_forest",
        _grid(min_samples_leaf=[25, 60], max_features=[0.3, 0.6]),
        feature_columns,
        lambda p, s: RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=p["min_samples_leaf"], max_features=p["max_features"], random_state=s, n_jobs=1),
    ),
    "hist_gb": ModelSpec(
        "hist_gb",
        _grid(max_depth=[2, 3], learning_rate=[0.02, 0.05]),
        feature_columns,
        lambda p, s: HistGradientBoostingClassifier(max_depth=p["max_depth"], learning_rate=p["learning_rate"], max_iter=150, min_samples_leaf=40, l2_regularization=1.0, random_state=s),
    ),
}  # fmt: skip


@dataclass
class SymmetricModel:
    """A fitted estimator plus the columns it uses; predictions are orientation-symmetrised."""

    estimator: BaseEstimator
    columns: list[str]
    tier: Tier

    def fit(self, x: pd.DataFrame, y: pd.Series) -> SymmetricModel:
        """Fit on the given (single-orientation) rows."""
        self.estimator.fit(x[self.columns].to_numpy(), y.to_numpy().astype(int))
        return self

    def raw_proba(self, x: pd.DataFrame) -> np.ndarray:
        """P(A wins) without symmetrisation."""
        return np.asarray(self.estimator.predict_proba(x[self.columns].to_numpy())[:, 1])

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        """Symmetrised P(A wins) = ½ [p(A,B) + 1 − p(B,A)]."""
        return 0.5 * (self.raw_proba(x) + 1.0 - self.raw_proba(swap_orientation(x, self.tier)))


@dataclass
class BlendModel:
    """Convex blend of two symmetric models (weights sum to 1)."""

    first: SymmetricModel
    second: SymmetricModel
    weight: float
    tier: Tier
    columns: list[str] = field(default_factory=list)

    def fit(self, x: pd.DataFrame, y: pd.Series) -> BlendModel:
        """Fit both components."""
        self.first.fit(x, y)
        self.second.fit(x, y)
        self.columns = sorted(set(self.first.columns) | set(self.second.columns))
        return self

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        """Weighted average of the components' symmetrised probabilities."""
        return self.weight * self.first.predict_proba(x) + (
            1 - self.weight
        ) * self.second.predict_proba(x)


Model = SymmetricModel | BlendModel


def make_model(name: str, params: dict[str, Any], tier: Tier, seed: int) -> Model:
    """Instantiate an unfitted model. ``blend`` params: logreg_C, hgb_depth, hgb_lr, weight."""
    if name == "blend":
        lr = SymmetricModel(_logreg(params["logreg_C"]), antisymmetric_columns(tier), tier)
        hgb_spec = SPECS["hist_gb"]
        hgb = SymmetricModel(
            hgb_spec.build(
                {"max_depth": params["hgb_depth"], "learning_rate": params["hgb_lr"]}, seed
            ),
            feature_columns(tier),
            tier,
        )
        return BlendModel(lr, hgb, float(params["weight"]), tier)
    spec = SPECS[name]
    return SymmetricModel(clone(spec.build(params, seed)), spec.columns(tier), tier)


@dataclass
class CVResult:
    """Walk-forward result for one model configuration."""

    name: str
    params: dict[str, Any]
    fold_log_loss: dict[int, float]
    oof: pd.Series  # OOF probability indexed like the input frame (validation rows only)

    @property
    def mean(self) -> float:
        """Mean fold log-loss."""
        return float(np.mean(list(self.fold_log_loss.values())))

    @property
    def std(self) -> float:
        """Std of fold log-losses."""
        return float(np.std(list(self.fold_log_loss.values()), ddof=1))

    @property
    def se(self) -> float:
        """Standard error of the mean fold log-loss."""
        return self.std / np.sqrt(len(self.fold_log_loss))

    def summary(self) -> dict[str, Any]:
        """Serialisable summary."""
        return {
            "model": self.name,
            "params": self.params,
            "mean_log_loss": self.mean,
            "std_log_loss": self.std,
            "se": self.se,
            "folds": {str(k): v for k, v in self.fold_log_loss.items()},
        }


def walk_forward(
    name: str,
    params: dict[str, Any],
    x: pd.DataFrame,
    y: pd.Series,
    folds: list[Fold],
    tier: Tier,
    seed: int,
) -> CVResult:
    """Train on seasons < S, predict season S, for each fold."""
    oof = pd.Series(np.nan, index=x.index)
    losses: dict[int, float] = {}
    for fold in folds:
        model = make_model(name, params, tier, seed).fit(x[fold.train], y[fold.train])
        p = model.predict_proba(x[fold.valid])
        oof[x.index[fold.valid]] = p
        losses[fold.season] = log_loss(y[fold.valid].to_numpy(), p)
    return CVResult(name, params, losses, oof.dropna())


def blend_grid(best: dict[str, CVResult]) -> tuple[dict[str, Any], ...]:
    """Blend search space built around the best logreg and hist_gb configurations."""
    lr, hgb = best["logreg"].params, best["hist_gb"].params
    return tuple(
        {
            "logreg_C": lr["C"],
            "hgb_depth": hgb["max_depth"],
            "hgb_lr": hgb["learning_rate"],
            "weight": w,
        }
        for w in (0.25, 0.5, 0.75)
    )


def select_model(results: dict[str, CVResult]) -> tuple[str, dict[str, Any]]:
    """One-standard-error rule over the best configuration of each family."""
    best_name = min(results, key=lambda n: results[n].mean)
    threshold = results[best_name].mean + results[best_name].se
    for name in COMPLEXITY_ORDER:
        if name in results and results[name].mean <= threshold:
            return name, {
                "chosen": name,
                "best_by_mean": best_name,
                "threshold": threshold,
                "rule": "one-standard-error",
            }
    return best_name, {
        "chosen": best_name,
        "best_by_mean": best_name,
        "threshold": threshold,
        "rule": "lowest-mean",
    }
