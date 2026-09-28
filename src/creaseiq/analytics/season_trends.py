"""Scoring and margin trends (FR-09)."""

from __future__ import annotations

from typing import Any

import pandas as pd
from scipy import stats


def _scored(m: pd.DataFrame) -> pd.DataFrame:
    return m[m["scores_usable"] & m["first_innings_runs"].notna()]


def scoring_by_season(m: pd.DataFrame) -> pd.DataFrame:
    """Per season: mean/median first-innings score and share of 200+ first innings."""
    s = _scored(m)
    g = s.groupby("season_year")["first_innings_runs"]
    out = pd.DataFrame(
        {
            "matches": g.size(),
            "mean_first_innings": g.mean(),
            "median_first_innings": g.median(),
            "share_200_plus": g.apply(lambda x: float((x >= 200).mean())),
            "max_first_innings": g.max(),
        }
    )
    return out.reset_index()


def era_scoring_test(m: pd.DataFrame) -> dict[str, Any]:
    """First-innings scores before vs after the Impact Player rule (Welch t and Mann-Whitney)."""
    s = _scored(m)
    pre = s.loc[~s["impact_era"], "first_innings_runs"]
    post = s.loc[s["impact_era"], "first_innings_runs"]
    welch = stats.ttest_ind(post, pre, equal_var=False)
    mw = stats.mannwhitneyu(post, pre, alternative="two-sided")
    diff = float(post.mean() - pre.mean())
    se = float(((post.var(ddof=1) / len(post)) + (pre.var(ddof=1) / len(pre))) ** 0.5)
    pooled_sd = float(((post.var(ddof=1) + pre.var(ddof=1)) / 2) ** 0.5)
    return {
        "n_pre": len(pre),
        "n_post": len(post),
        "mean_pre": float(pre.mean()),
        "mean_post": float(post.mean()),
        "diff": diff,
        "ci_low": diff - 1.96 * se,
        "ci_high": diff + 1.96 * se,
        "cohens_d": diff / pooled_sd if pooled_sd > 0 else float("nan"),
        "welch_t": float(welch.statistic),
        "welch_p": float(welch.pvalue),
        "mannwhitney_p": float(mw.pvalue),
        "share_200_pre": float((pre >= 200).mean()),
        "share_200_post": float((post >= 200).mean()),
    }


def margin_summary(m: pd.DataFrame) -> pd.DataFrame:
    """Distribution of winning margins by type (runs / wickets)."""
    d = m[m["is_decided"] & ~m["dls_flag"]]
    return d.groupby("margin_type")["margin_value"].describe().reset_index()


def closest_finishes(m: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Ties plus the narrowest wins by runs (ball-by-ball data would be needed to rank wicket wins)."""
    ties = m[m["result_type"] == "tie"].assign(closeness=0)
    runs = m[(m["margin_type"] == "runs") & ~m["dls_flag"]].assign(
        closeness=lambda x: x["margin_value"]
    )
    cols = [
        "date",
        "season_year",
        "team1",
        "team2",
        "winner",
        "super_over_winner",
        "result_type",
        "margin_type",
        "margin_value",
        "venue",
        "stage",
        "closeness",
    ]
    both = pd.concat([ties[cols], runs[cols]], ignore_index=True)
    return both.sort_values(["closeness", "date"]).head(n).reset_index(drop=True)
