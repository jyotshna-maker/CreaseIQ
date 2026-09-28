"""Write all training outputs: metrics.json, model card and figures (FR-22)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from creaseiq.config import Settings
from creaseiq.reporting import figures as fig
from creaseiq.reporting.model_card import render_model_card
from creaseiq.utils import write_json


def write_training_outputs(
    settings: Settings,
    metrics: dict[str, Any],
    elo_history: pd.DataFrame,
    analytics: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Persist metrics.json, docs/model_card.md and the report figures; return figure paths."""
    reports = settings.path("reports_dir")
    figs = settings.path("figures_dir")
    write_json(reports / "metrics.json", metrics)
    docs = settings.path("docs_dir")
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "model_card.md").write_text(render_model_card(metrics), encoding="utf-8")
    post, pre = metrics["tiers"]["post_toss"], metrics["tiers"]["pre_toss"]
    paths = {
        "reliability": fig.reliability_diagram(
            {
                "pre-toss model": pre["holdout_reliability"],
                "post-toss model": post["holdout_reliability"],
            },
            figs / "reliability_holdout.png",
        ),
        "walk_forward": fig.walk_forward_by_season(
            {
                f"post-toss {post['selection']['chosen']}": post["best_per_family"][
                    post["selection"]["chosen"]
                ]["folds"],
                f"pre-toss {pre['selection']['chosen']}": pre["best_per_family"][
                    pre["selection"]["chosen"]
                ]["folds"],
                "B1 chase prior": post["baselines_walk_forward"]["B1_chase_prior"]["folds"],
                "B3 Elo": post["baselines_walk_forward"]["B3_elo"]["folds"],
            },
            figs / "walk_forward_by_season.png",
        ),
        "timeline": fig.walk_forward_timeline(
            metrics["splits"]["first_validation_season"],
            metrics["splits"]["dev_last_season"],
            metrics["splits"]["holdout_seasons"],
            2008,
            figs / "walk_forward_timeline.png",
        ),
        "importance": fig.importance_bar(
            post["permutation_importance"], figs / "permutation_importance_post_toss.png"
        ),
        "holdout_post": fig.holdout_comparison(post, figs / "holdout_vs_baselines_post_toss.png"),
        "holdout_pre": fig.holdout_comparison(pre, figs / "holdout_vs_baselines_pre_toss.png"),
        "ablation": fig.ablation_bar(post["ablation"], figs / "ablation_post_toss.png"),
    }
    if not elo_history.empty:
        latest = elo_history.sort_values("date").groupby("team").tail(1)
        top = latest.sort_values("rating_before", ascending=False)["team"].head(4).tolist()
        paths["elo"] = fig.elo_timeline(elo_history, top, figs / "elo_timeline.png")
    if analytics is not None:
        paths["scoring"] = fig.scoring_trend(
            analytics["scoring_by_season"], figs / "scoring_trend.png"
        )
        paths["chase"] = fig.chase_by_season(
            analytics["chasing"]["by_season"],
            analytics["chasing"]["overall"]["rate"],
            figs / "chase_by_season.png",
        )
    return paths
