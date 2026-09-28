"""Evaluation metrics, uncertainty and model comparison (FR-15; research R7).

* Primary metric: **log-loss**. Also reported: Brier score with its Murphy decomposition
  (reliability − resolution + uncertainty), accuracy, ROC-AUC, and ECE with **equal-mass**
  bins (less biased than equal-width, per Roelofs et al. 2022; treated as descriptive).
* Uncertainty: percentile bootstrap CIs.
* Comparison: a **paired** bootstrap of per-match log-loss differences, plus the
  Diebold–Mariano test with the Harvey–Leybourne–Newbold small-sample correction.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

EPS = 1e-12


def _clip(p: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def per_match_log_loss(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Per-observation log-loss."""
    y, p = np.asarray(y, dtype=float), _clip(p)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    """Mean log-loss (natural log). A constant 0.5 forecast scores ln 2 ≈ 0.693."""
    return float(per_match_log_loss(y, p).mean())


def brier(y: np.ndarray, p: np.ndarray) -> float:
    """Mean squared error of probabilities."""
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))


def accuracy(y: np.ndarray, p: np.ndarray) -> float:
    """Share of correct 0.5-threshold calls."""
    return float(np.mean((np.asarray(p) >= 0.5) == (np.asarray(y) == 1)))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """ROC-AUC (nan if only one class is present)."""
    y = np.asarray(y)
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else math.nan


def equal_mass_bins(p: np.ndarray, n_bins: int) -> np.ndarray:
    """Bin index per prediction using quantile (equal-mass) bins."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p, kind="stable")
    bins = np.empty(len(p), dtype=int)
    bins[order] = np.minimum((np.arange(len(p)) * n_bins) // max(len(p), 1), n_bins - 1)
    return bins


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict[str, float]]:
    """Mean prediction vs observed frequency per equal-mass bin."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    bins = equal_mass_bins(p, n_bins)
    rows = []
    for b in range(n_bins):
        mask = bins == b
        if mask.any():
            rows.append(
                {
                    "bin": b,
                    "n": int(mask.sum()),
                    "mean_pred": float(p[mask].mean()),
                    "observed": float(y[mask].mean()),
                }
            )
    return rows


def ece(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error with equal-mass bins (descriptive at small n)."""
    table = reliability_table(y, p, n_bins)
    n = sum(r["n"] for r in table)
    return (
        float(sum(r["n"] / n * abs(r["mean_pred"] - r["observed"]) for r in table))
        if n
        else math.nan
    )


def brier_decomposition(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict[str, float]:
    """Murphy decomposition on equal-mass bins: BS ≈ reliability − resolution + uncertainty."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    base = float(y.mean())
    rel = res = 0.0
    for r in reliability_table(y, p, n_bins):
        w = r["n"] / len(y)
        rel += w * (r["mean_pred"] - r["observed"]) ** 2
        res += w * (r["observed"] - base) ** 2
    return {"reliability": rel, "resolution": res, "uncertainty": base * (1 - base)}


def metric_suite(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict[str, Any]:
    """All point metrics for one set of predictions."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return {
        "n": len(y),
        "log_loss": log_loss(y, p),
        "brier": brier(y, p),
        "brier_skill_vs_coin": 1 - brier(y, p) / 0.25,
        "accuracy": accuracy(y, p),
        "auc": auc(y, p),
        "ece": ece(y, p, n_bins),
        "brier_decomposition": brier_decomposition(y, p, n_bins),
        "mean_pred": float(p.mean()),
        "base_rate": float(y.mean()),
    }


def bootstrap_ci(
    y: np.ndarray, p: np.ndarray, n_resamples: int = 2000, seed: int = 42, alpha: float = 0.05
) -> dict[str, dict[str, float]]:
    """Percentile bootstrap CIs for log-loss, Brier, accuracy and AUC."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    rng = np.random.default_rng(seed)
    fns = {"log_loss": log_loss, "brier": brier, "accuracy": accuracy, "auc": auc}
    draws: dict[str, list[float]] = {k: [] for k in fns}
    for _ in range(n_resamples):
        idx = rng.integers(0, len(y), len(y))
        for k, fn in fns.items():
            draws[k].append(fn(y[idx], p[idx]))
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    return {
        k: {"low": float(np.nanpercentile(v, lo)), "high": float(np.nanpercentile(v, hi))}
        for k, v in draws.items()
    }


def paired_bootstrap(
    y: np.ndarray, p_model: np.ndarray, p_ref: np.ndarray, n_resamples: int = 10000, seed: int = 42
) -> dict[str, float]:
    """Paired bootstrap of mean log-loss difference (model − reference). Negative = model better.

    Returns the observed difference, its 95% CI and the share of resamples where the model
    was *not* better (a one-sided bootstrap p-value).
    """
    d = per_match_log_loss(y, p_model) - per_match_log_loss(y, p_ref)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (n_resamples, len(d)))
    means = d[idx].mean(axis=1)
    return {
        "diff": float(d.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "p_not_better": float(np.mean(means >= 0)),
    }


def diebold_mariano(y: np.ndarray, p_model: np.ndarray, p_ref: np.ndarray) -> dict[str, float]:
    """Diebold–Mariano test on per-match log-loss differences, with the HLN correction (h = 1)."""
    d = per_match_log_loss(y, p_model) - per_match_log_loss(y, p_ref)
    n = len(d)
    var = float(np.var(d, ddof=0))
    if n < 3 or var == 0:
        return {"dm_stat": math.nan, "p_value": math.nan}
    dm = float(d.mean() / math.sqrt(var / n))
    hln = dm * math.sqrt((n + 1 - 2 + 0) / n)  # h = 1 → sqrt((n - 1) / n)
    p = float(2 * stats.t.sf(abs(hln), df=n - 1))
    return {"dm_stat": hln, "p_value": p}


def too_good_check(metrics: dict[str, Any], max_auc: float, max_accuracy: float) -> dict[str, Any]:
    """Flag implausibly good holdout results (PLAN §7 leakage guard 5)."""
    flags = []
    if metrics.get("auc", 0) > max_auc:
        flags.append(f"AUC {metrics['auc']:.3f} > {max_auc}")
    if metrics.get("accuracy", 0) > max_accuracy:
        flags.append(f"accuracy {metrics['accuracy']:.3f} > {max_accuracy}")
    return {
        "suspicious": bool(flags),
        "reasons": flags,
        "max_auc": max_auc,
        "max_accuracy": max_accuracy,
    }
