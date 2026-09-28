"""Elo hyperparameter search (FR-13; research R3 grid).

Search is framed as heuristic grid search over a validation-loss landscape (ADR-001):
K × home bonus × season regression × margin on/off. Each candidate is scored by the
walk-forward log-loss of an ``elo_logit`` model on the development seasons. The lean
rating pass here reuses :class:`EloRatingSystem` (the same update code as the
FeatureBuilder) and the same orientation flip, so tuned values carry over exactly.
"""

from __future__ import annotations

import itertools
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from creaseiq.features.builder import orientation_flip
from creaseiq.features.elo import EloParams, EloRatingSystem
from creaseiq.models.evaluate import log_loss
from creaseiq.models.splits import walk_forward_folds


def prepare_records(matches: pd.DataFrame) -> list[list[Any]]:
    """Date-ordered batches of plain records (prepared once, reused for every candidate)."""
    ordered = matches.sort_values(["date", "match_id"], kind="stable")
    recs = [SimpleNamespace(**d) for d in ordered.to_dict(orient="records")]
    return [list(g) for _, g in itertools.groupby(recs, key=lambda r: r.date)]


def elo_pass(batches: list[list[Any]], params: EloParams, seed: int) -> pd.DataFrame:
    """Pre-match ``elo_diff`` and ``home_diff`` (A − B) for every match."""
    elo = EloRatingSystem(params)
    rows = []
    for batch in batches:
        elo.start_season(int(batch[0].season_year))
        for r in batch:
            flip = orientation_flip(r.date_raw, r.team1, r.team2, seed)
            a, b = (r.team2, r.team1) if flip else (r.team1, r.team2)
            ah, bh = (r.team2_home, r.team1_home) if flip else (r.team1_home, r.team2_home)
            rows.append(
                (
                    int(r.match_id),
                    int(r.season_year),
                    bool(r.is_decided),
                    float(r.winner == a) if r.is_decided else np.nan,
                    elo.rating(a) - elo.rating(b),
                    float(int(ah) - int(bh)),
                )
            )
        deltas: dict[str, float] = {}
        played: list[str] = []
        for r in batch:
            if r.is_decided or r.result_type == "tie":
                s1 = 0.5 if r.result_type == "tie" else float(r.winner == r.team1)
                d1, d2 = elo.compute_update(
                    r.team1,
                    r.team2,
                    s1,
                    bool(r.team1_home),
                    bool(r.team2_home),
                    r.margin_type if r.is_decided else None,
                    float(r.margin_value) if r.is_decided else None,
                    bool(r.dls_flag),
                )
                deltas[r.team1] = deltas.get(r.team1, 0.0) + d1
                deltas[r.team2] = deltas.get(r.team2, 0.0) + d2
                played += [r.team1, r.team2]
        elo.apply(deltas, played)
    return pd.DataFrame(
        rows, columns=["match_id", "season_year", "is_decided", "a_wins", "elo_diff", "home_diff"]
    )


def score_candidate(
    frame: pd.DataFrame, first_valid: int, last_valid: int
) -> tuple[float, dict[int, float]]:
    """Walk-forward log-loss of a no-intercept logistic on (elo_diff/100, home_diff)."""
    d = frame[frame["is_decided"]].reset_index(drop=True)
    x = np.column_stack([d["elo_diff"] / 100.0, d["home_diff"]])
    y = d["a_wins"].to_numpy().astype(int)
    losses = {}
    for fold in walk_forward_folds(d["season_year"], first_valid, last_valid):
        lr = LogisticRegression(C=1.0, fit_intercept=False).fit(x[fold.train], y[fold.train])
        losses[fold.season] = log_loss(y[fold.valid], lr.predict_proba(x[fold.valid])[:, 1])
    return float(np.mean(list(losses.values()))), losses


def tune_elo(
    matches: pd.DataFrame,
    grid: dict[str, list[Any]],
    base: EloParams,
    seed: int,
    first_valid: int,
    last_valid: int,
) -> dict[str, Any]:
    """Evaluate every grid combination; return the best parameters and the full table."""
    batches = prepare_records(matches)
    keys = list(grid)
    table = []
    for values in itertools.product(*grid.values()):
        cand = EloParams(**{**asdict(base), **dict(zip(keys, values, strict=True))})
        mean, _ = score_candidate(elo_pass(batches, cand, seed), first_valid, last_valid)
        table.append({**dict(zip(keys, values, strict=True)), "mean_log_loss": mean})
    ranked = sorted(table, key=lambda r: r["mean_log_loss"])
    best = {k: ranked[0][k] for k in keys}
    default_score = score_candidate(elo_pass(batches, base, seed), first_valid, last_valid)[0]
    return {
        "best": best,
        "best_mean_log_loss": ranked[0]["mean_log_loss"],
        "default_params": asdict(base),
        "default_mean_log_loss": default_score,
        "n_candidates": len(table),
        "top10": ranked[:10],
        "worst": ranked[-1],
    }
