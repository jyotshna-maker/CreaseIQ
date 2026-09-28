"""Static report figures (FR-22), rendered with matplotlib from the experiment outputs.

The palette is Okabe–Ito, which is colour-blind safe (NFR-04). Every figure is saved as a
300-dpi PNG in ``reports/figures`` and embedded in the report and README.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]
DPI = 300


def _style(ax: Any, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=11, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def _save(fig: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def reliability_diagram(tables: dict[str, list[dict[str, float]]], path: Path) -> Path:
    """Observed win rate vs mean predicted probability per equal-mass bin."""
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.plot([0.2, 0.8], [0.2, 0.8], ls="--", color="grey", lw=1, label="perfect calibration")
    for (name, rows), color in zip(tables.items(), OKABE_ITO, strict=False):
        xs = [r["mean_pred"] for r in rows]
        ys = [r["observed"] for r in rows]
        ax.plot(xs, ys, marker="o", color=color, label=name)
    ax.set_xlim(0.2, 0.8)
    ax.set_ylim(0.0, 1.0)
    ax.legend(frameon=False, fontsize=8)
    _style(
        ax,
        "Reliability (holdout 2025-26, equal-mass bins)",
        "mean predicted P(A wins)",
        "observed frequency",
    )
    return _save(fig, path)


def walk_forward_by_season(series: dict[str, dict[str, float]], path: Path) -> Path:
    """Per-season validation log-loss of the chosen model and baselines."""
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for (name, folds), color in zip(series.items(), OKABE_ITO, strict=False):
        seasons = sorted(int(s) for s in folds)
        ax.plot(
            seasons, [folds[str(s)] for s in seasons], marker="o", ms=3, color=color, label=name
        )
    ax.axhline(np.log(2), color="grey", ls=":", lw=1)
    ax.text(ax.get_xlim()[0], np.log(2) + 0.001, " coin flip (ln 2)", fontsize=7, color="grey")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    _style(
        ax,
        "Walk-forward validation log-loss by season (lower is better)",
        "validation season",
        "log-loss",
    )
    return _save(fig, path)


def walk_forward_timeline(
    first_valid: int, dev_last: int, holdout: list[int], first_season: int, path: Path
) -> Path:
    """Diagram D11: expanding training windows, validation seasons and the locked holdout."""
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    folds = list(range(first_valid, dev_last + 1))
    for i, s in enumerate(folds):
        ax.barh(i, s - first_season, left=first_season, color=OKABE_ITO[0], alpha=0.35)
        ax.barh(i, 1, left=s, color=OKABE_ITO[1])
    ax.barh(
        len(folds), dev_last - first_season + 1, left=first_season, color=OKABE_ITO[0], alpha=0.35
    )
    ax.barh(len(folds), len(holdout), left=min(holdout), color=OKABE_ITO[3])
    ax.set_yticks(range(len(folds) + 1), [f"fold {s}" for s in folds] + ["final"], fontsize=7)
    ax.invert_yaxis()
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=c, alpha=a)
        for c, a in ((OKABE_ITO[0], 0.35), (OKABE_ITO[1], 1), (OKABE_ITO[3], 1))
    ]
    ax.legend(
        handles,
        ["train", "validate", "holdout (evaluated once)"],
        frameon=False,
        fontsize=8,
        loc="lower left",
    )
    _style(ax, "Expanding-window walk-forward and locked holdout", "season")
    return _save(fig, path)


def importance_bar(rows: list[dict[str, Any]], path: Path, top: int = 12) -> Path:
    """Permutation importance (increase in log-loss) with ±1 sd error bars."""
    df = pd.DataFrame(rows).head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.barh(df["label"], df["importance"], xerr=df["std"], color=OKABE_ITO[0], alpha=0.8)
    ax.axvline(0, color="black", lw=0.8)
    _style(ax, "Permutation importance (development seasons)", "increase in log-loss when shuffled")
    return _save(fig, path)


def elo_timeline(history: pd.DataFrame, teams: list[str], path: Path) -> Path:
    """Pre-match Elo rating over time for selected franchises."""
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for team, color in zip(teams, OKABE_ITO, strict=False):
        h = history[history["team"] == team].sort_values("date")
        ax.plot(h["date"], h["rating_before"] + h["delta"], color=color, lw=1.2, label=team.upper())
    ax.axhline(1500, color="grey", ls=":", lw=1)
    ax.legend(frameon=False, fontsize=8, ncol=len(teams))
    _style(ax, "Elo ratings (tuned, margin-aware)", "", "rating")
    return _save(fig, path)


def scoring_trend(scoring: list[dict[str, Any]], path: Path) -> Path:
    """Mean first-innings score and 200+ share per season, with the Impact Player era shaded."""
    df = pd.DataFrame(scoring)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.axvspan(
        2022.5,
        df["season_year"].max() + 0.5,
        color=OKABE_ITO[1],
        alpha=0.12,
        label="Impact Player era",
    )
    ax.plot(
        df["season_year"],
        df["mean_first_innings"],
        marker="o",
        color=OKABE_ITO[0],
        label="mean first-innings score",
    )
    ax2 = ax.twinx()
    ax2.bar(
        df["season_year"],
        100 * df["share_200_plus"],
        color=OKABE_ITO[3],
        alpha=0.35,
        label="% of first innings ≥ 200",
    )
    ax2.set_ylabel("% innings ≥ 200")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax2.legend(frameon=False, fontsize=8, loc="center left")
    _style(ax, "Scoring by season", "season", "runs")
    ax2.spines[["top"]].set_visible(False)
    return _save(fig, path)


def chase_by_season(rows: list[dict[str, Any]], overall: float, path: Path) -> Path:
    """Chasing side's win rate per season with 95% Wilson intervals."""
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.errorbar(
        df["season_year"],
        df["rate"],
        yerr=[df["rate"] - df["ci_low"], df["ci_high"] - df["rate"]],
        fmt="o",
        color=OKABE_ITO[0],
        capsize=2,
    )
    ax.axhline(0.5, color="grey", ls=":", lw=1)
    ax.axhline(overall, color=OKABE_ITO[3], lw=1, label=f"all seasons {overall:.1%}")
    ax.legend(frameon=False, fontsize=8)
    _style(ax, "Chasing side's win rate by season (95% CI)", "season", "win rate")
    return _save(fig, path)


def holdout_comparison(tier_metrics: dict[str, Any], path: Path) -> Path:
    """Holdout log-loss: model (with bootstrap CI) against each baseline."""
    names = ["model", *[k for k in tier_metrics["holdout"] if k != "model"]]
    vals = [tier_metrics["holdout"][n]["log_loss"] for n in names]
    ci = tier_metrics["holdout"]["model"]["ci"]["log_loss"]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    colors = [OKABE_ITO[0]] + [OKABE_ITO[5]] * (len(names) - 1)
    ax.bar(names, vals, color=colors)
    ax.errorbar(
        [0],
        [vals[0]],
        yerr=[[vals[0] - ci["low"]], [ci["high"] - vals[0]]],
        color="black",
        capsize=4,
    )
    ax.axhline(np.log(2), color="grey", ls=":", lw=1)
    ax.set_ylim(min(vals) - 0.03, max(max(vals), ci["high"]) + 0.01)
    ax.tick_params(axis="x", labelsize=7, rotation=15)
    _style(ax, "Holdout log-loss vs baselines (lower is better)", "", "log-loss")
    return _save(fig, path)


def ablation_bar(rows: list[dict[str, Any]], path: Path) -> Path:
    """Walk-forward log-loss as feature groups are added."""
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    ax.plot(df["groups"], df["mean_log_loss"], marker="o", color=OKABE_ITO[2])
    ax.axhline(np.log(2), color="grey", ls=":", lw=1)
    ax.tick_params(axis="x", labelsize=7, rotation=20)
    _style(ax, "Feature-group ablation (logistic, walk-forward)", "", "mean log-loss")
    return _save(fig, path)
