"""Explainability (FR-16): global permutation importance and per-prediction drivers.

* **Global:** the increase in log-loss when a feature's values are shuffled, averaged over
  repeats. It works for any model.
* **Per prediction:** the served logistic model is linear in scaled features, so each
  feature's contribution to the logit is ``coef * x / scale``, and the contributions add
  up exactly to the logit. For tree models the logistic component of the blend (or a
  logistic surrogate) supplies the drivers; the UI says so.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from creaseiq.models.evaluate import log_loss

READABLE: dict[str, str] = {
    "elo_diff": "team strength (Elo rating)",
    "home_diff": "home ground",
    "form5_diff": "form over the last 5 matches",
    "form10_diff": "form over the last 10 matches",
    "runs_for10_diff": "recent runs scored",
    "runs_against10_diff": "recent runs conceded",
    "season_winpct_diff": "win rate this season",
    "season_games_diff": "games played this season",
    "rest_days_diff": "days of rest",
    "h2h_edge": "head-to-head record",
    "h2h_recent_edge": "recent head-to-head record",
    "venue_team_edge": "record at this venue",
    "a_bats_first": "batting first",
    "a_won_toss": "winning the toss",
    "bats_first_x_venue": "batting order at this venue",
    "bats_first_x_impact": "batting order in the Impact Player era",
    "xi_experience_diff": "experience of the playing XI",
    "xi_potm_diff": "match-winners in the XI (prior POTM awards)",
    "xi_debutants_diff": "debutants in the XI",
    "xi_continuity_diff": "settled line-up",
    "h2h_meetings": "number of past meetings",
    "venue_first_innings": "venue scoring level",
    "venue_bat_first_rate": "venue bat-first record",
    "is_playoff": "playoff match",
    "impact_era": "Impact Player era",
}


def permutation_importance(
    model: Any, x: pd.DataFrame, y: pd.Series, columns: list[str], repeats: int = 20, seed: int = 42
) -> pd.DataFrame:
    """Mean and std increase in log-loss when each column is permuted."""
    rng = np.random.default_rng(seed)
    yv = y.to_numpy()
    base = log_loss(yv, model.predict_proba(x))
    rows = []
    for col in columns:
        deltas = []
        for _ in range(repeats):
            xp = x.copy()
            xp[col] = rng.permutation(xp[col].to_numpy())
            deltas.append(log_loss(yv, model.predict_proba(xp)) - base)
        rows.append(
            {
                "feature": col,
                "importance": float(np.mean(deltas)),
                "std": float(np.std(deltas)),
                "label": READABLE.get(col, col),
            }
        )
    return pd.DataFrame(rows).sort_values("importance", ascending=False).reset_index(drop=True)


def logistic_component(model: Any) -> Any | None:
    """Return the SymmetricModel holding a no-intercept logistic pipeline, if any."""
    candidates = [model, getattr(model, "first", None)]
    for cand in candidates:
        est = getattr(cand, "estimator", None)
        if est is not None and hasattr(est, "named_steps") and "lr" in est.named_steps:
            return cand
    return None


def linear_contributions(sym_model: Any, row: pd.DataFrame) -> pd.DataFrame:
    """Per-feature logit contributions for one row (``coef * x / scale``); they sum to the logit."""
    pipe = sym_model.estimator
    scale = pipe.named_steps["scale"].scale_
    coef = pipe.named_steps["lr"].coef_[0]
    x = row[sym_model.columns].to_numpy()[0]
    contrib = coef * x / scale
    out = pd.DataFrame({"feature": sym_model.columns, "value": x, "contribution": contrib})
    out["label"] = out["feature"].map(lambda c: READABLE.get(c, c))
    return out.reindex(out["contribution"].abs().sort_values(ascending=False).index).reset_index(
        drop=True
    )


def driver_sentence(contribs: pd.DataFrame, team_a: str, team_b: str, top: int = 3) -> str:
    """Plain-English summary of the three strongest drivers."""
    parts = []
    for r in contribs[contribs["contribution"].abs() > 1e-9].head(top).itertuples():
        favoured = team_a if r.contribution > 0 else team_b
        parts.append(f"{r.label} favours {favoured}")
    if not parts:
        return "No feature moves this prediction away from a coin flip."
    return "Main drivers: " + "; ".join(parts) + "."
