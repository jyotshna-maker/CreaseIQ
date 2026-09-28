"""First-innings score regression (FR-17, P1).

Target: regulation first-innings runs. Ties use the corrected score; no-result and voided
matches are excluded. Features are all pre-match and post-toss (the batting order is known).
The inputs are the venue's as-of shrunk scoring level, a **rolling league mean over the
previous ~one season of matches** (it adapts to the Impact Player scoring jump), the batting
side's recent runs scored, the bowling side's recent runs conceded, the Elo gap, era and stage.

Models: Ridge (scaled) and HistGradientBoostingRegressor.
Baselines: the venue level alone, and the recent league mean alone.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from creaseiq.features.builder import FeatureSet
from creaseiq.models.splits import dev_holdout_masks, walk_forward_folds

SCORE_FEATURES = [
    "venue_first_innings",
    "league_recent_first_innings",
    "bat_runs_for10",
    "bowl_runs_against10",
    "elo_gap_bat_minus_bowl",
    "impact_era",
    "is_playoff",
]
LEAGUE_WINDOW = 74  # about one season of matches


def league_recent_mean(matches: pd.DataFrame, window: int = LEAGUE_WINDOW) -> pd.Series:
    """Mean of the previous ``window`` usable first-innings scores from strictly earlier dates."""
    m = matches.sort_values(["date", "match_id"])
    usable = m["scores_usable"] & m["first_innings_runs"].notna()
    history: list[float] = []
    out: dict[int, float] = {}
    for _, day in m.groupby("date", sort=True):
        prior = history[-window:]
        val = float(np.mean(prior)) if prior else np.nan
        for mid in day["match_id"]:
            out[int(mid)] = val
        history.extend(day.loc[usable.loc[day.index], "first_innings_runs"].astype(float).tolist())
    return pd.Series(out, name="league_recent_first_innings")


def build_score_frame(matches: pd.DataFrame, fs: FeatureSet) -> pd.DataFrame:
    """One row per usable match with bat-first-oriented features and the target."""
    m = matches[matches["scores_usable"] & matches["first_innings_runs"].notna()]
    ts = fs.team_state.set_index(["match_id", "team"])
    ctx = fs.frame.set_index("match_id")[["venue_first_innings", "impact_era", "is_playoff"]]
    league = league_recent_mean(matches)
    rows = []
    for r in m.itertuples(index=False):
        bat, bowl = ts.loc[(r.match_id, r.bat_first)], ts.loc[(r.match_id, r.chasing_team)]
        c = ctx.loc[r.match_id]
        rows.append(
            {
                "match_id": r.match_id,
                "season_year": r.season_year,
                "venue_first_innings": c["venue_first_innings"],
                "league_recent_first_innings": league.get(int(r.match_id), np.nan),
                "bat_runs_for10": bat["runs_for10"],
                "bowl_runs_against10": bowl["runs_against10"],
                "elo_gap_bat_minus_bowl": bat["elo"] - bowl["elo"],
                "impact_era": c["impact_era"],
                "is_playoff": c["is_playoff"],
                "target": float(r.first_innings_runs),
            }
        )
    out = pd.DataFrame(rows)
    # The first match ever has no league history: fall back to its (prior-only) venue level.
    out["league_recent_first_innings"] = out["league_recent_first_innings"].fillna(
        out["venue_first_innings"]
    )
    return out


def _models(seed: int) -> dict[str, Any]:
    return {
        "ridge": Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=10.0))]),
        "hist_gb": HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=30, random_state=seed
        ),
    }


def _errors(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    e = p - y
    return {
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e**2))),
        "bias": float(np.mean(e)),
    }


def _bootstrap_mae(y: np.ndarray, p: np.ndarray, n: int, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y), (n, len(y)))
    maes = np.abs(p[idx] - y[idx]).mean(axis=1)
    return {"low": float(np.percentile(maes, 2.5)), "high": float(np.percentile(maes, 97.5))}


def evaluate_score_models(
    frame: pd.DataFrame,
    first_valid: int,
    dev_last: int,
    holdout: list[int],
    seed: int,
    n_boot: int = 2000,
) -> dict[str, Any]:
    """Walk-forward on development seasons, then a single holdout evaluation."""
    x, y = frame[SCORE_FEATURES], frame["target"].to_numpy()
    baselines = {
        "venue_level": frame["venue_first_innings"].to_numpy(),
        "recent_league_mean": frame["league_recent_first_innings"].to_numpy(),
    }
    dev, hold = dev_holdout_masks(frame["season_year"], dev_last, holdout)
    folds = walk_forward_folds(frame["season_year"][dev], first_valid, dev_last)
    xd, yd = x[dev].reset_index(drop=True), y[dev]
    wf: dict[str, dict[str, float]] = {}
    for name, model in _models(seed).items():
        preds = np.full(len(yd), np.nan)
        for f in folds:
            preds[f.valid] = model.fit(xd[f.train], yd[f.train]).predict(xd[f.valid])
        mask = ~np.isnan(preds)
        wf[name] = _errors(yd[mask], preds[mask])
    valid_rows = np.zeros(len(yd), dtype=bool)
    for f in folds:
        valid_rows |= f.valid
    for name, b in baselines.items():
        wf[f"baseline_{name}"] = _errors(yd[valid_rows], b[dev][valid_rows])
    holdout_res: dict[str, Any] = {}
    fitted = {}
    for name, model in _models(seed).items():
        fitted[name] = model.fit(x[dev], y[dev])
        p = fitted[name].predict(x[hold])
        holdout_res[name] = {
            **_errors(y[hold], p),
            "mae_ci": _bootstrap_mae(y[hold], p, n_boot, seed),
        }
    for name, b in baselines.items():
        holdout_res[f"baseline_{name}"] = {
            **_errors(y[hold], b[hold]),
            "mae_ci": _bootstrap_mae(y[hold], b[hold], n_boot, seed),
        }
    best = min(("ridge", "hist_gb"), key=lambda n: wf[n]["mae"])
    ridge = fitted["ridge"]
    coefs = dict(
        zip(
            SCORE_FEATURES,
            (ridge.named_steps["ridge"].coef_ / ridge.named_steps["scale"].scale_).tolist(),
            strict=True,
        )
    )
    return {
        "features": SCORE_FEATURES,
        "n_dev": int(dev.sum()),
        "n_holdout": int(hold.sum()),
        "walk_forward": wf,
        "chosen": best,
        "holdout": holdout_res,
        "ridge_coefficients_per_unit": coefs,
    }
