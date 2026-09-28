"""Toss and batting-order analysis (FR-08; test design from research R4).

* **Primary causal question:** does winning the toss help? The toss is randomised, so an
  exact binomial test of "toss winner wins" against 50% is a valid causal test. It needs
  no adjustment for confounders.
* **Chasing advantage** is a different question: does the side batting second win more
  often? It is tested separately and compared across eras (before and after the 2023
  Impact Player rule).
* The bat/field **decision** is chosen after the toss and depends on conditions and team
  strength (post-treatment). Tests that condition on it are labelled *associational*.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from creaseiq.analytics.common import decided
from creaseiq.analytics.hypothesis_tests import (
    binomial_test,
    chi_square,
    holm_adjust,
    two_proportion_ztest,
    wilson_ci,
)


def _rate_table(df: pd.DataFrame, by: str, flag: str) -> pd.DataFrame:
    g = (
        df.groupby(by)[flag]
        .agg(successes=lambda s: int(s.astype(bool).sum()), n="size")
        .reset_index()
    )
    ci = [wilson_ci(int(s), int(n)) for s, n in zip(g["successes"], g["n"], strict=True)]
    g["rate"] = g["successes"] / g["n"]
    g["ci_low"] = [c[0] for c in ci]
    g["ci_high"] = [c[1] for c in ci]
    return g


def toss_effect(m: pd.DataFrame) -> dict[str, Any]:
    """Toss-winner win rate: overall (binomial and Wilson), by decision, by era, and the
    associational decision-by-outcome chi-square."""
    d = decided(m)
    won = d["toss_winner_won"].astype(bool)
    overall = binomial_test(int(won.sum()), len(d))
    by_decision = _rate_table(d.assign(tw=won), "toss_decision", "tw")
    era = d.assign(tw=won, era=np.where(d["impact_era"], "impact_2023+", "pre_2023"))
    by_era = _rate_table(era, "era", "tw")
    pre, post = era[era["era"] == "pre_2023"], era[era["era"] == "impact_2023+"]
    era_test = two_proportion_ztest(
        int(post["tw"].sum()), len(post), int(pre["tw"].sum()), len(pre)
    )
    table = (
        pd.crosstab(d["toss_decision"], won).reindex(columns=[False, True], fill_value=0).to_numpy()
    )
    return {
        "overall": overall.as_dict(),
        "by_decision": by_decision,
        "by_era": by_era,
        "era_test_impact_minus_pre": era_test.as_dict(),
        "decision_outcome_chi2_associational": chi_square(table).as_dict(),
    }


def chasing_advantage(m: pd.DataFrame) -> dict[str, Any]:
    """Win rate of the side batting second: overall, by season, and before vs after 2023."""
    d = decided(m)
    chase_won = ~d["bat_first_won"].astype(bool)
    overall = binomial_test(int(chase_won.sum()), len(d))
    by_season = _rate_table(d.assign(cw=chase_won), "season_year", "cw")
    pre, post = d[~d["impact_era"]], d[d["impact_era"]]
    pre_cw, post_cw = ~pre["bat_first_won"].astype(bool), ~post["bat_first_won"].astype(bool)
    era_test = two_proportion_ztest(int(post_cw.sum()), len(post), int(pre_cw.sum()), len(pre))
    return {
        "overall": overall.as_dict(),
        "by_season": by_season,
        "era_test_impact_minus_pre": era_test.as_dict(),
    }


def field_first_share(m: pd.DataFrame) -> pd.DataFrame:
    """Share of toss winners choosing to field first, per season (captains' revealed preference)."""
    g = m.assign(field=m["toss_decision"] == "field")
    return _rate_table(g, "season_year", "field")


def toss_by_venue(m: pd.DataFrame, min_matches: int = 20) -> pd.DataFrame:
    """Toss-winner win rate per venue, with Holm-adjusted p-values across venues."""
    d = decided(m).assign(tw=lambda x: x["toss_winner_won"].astype(bool))
    rows = []
    for venue, g in d.groupby("venue_id"):
        if len(g) < min_matches:
            continue
        t = binomial_test(int(g["tw"].sum()), len(g))
        rows.append(
            {
                "venue_id": venue,
                "n": t.n,
                "rate": t.rate,
                "ci_low": t.ci_low,
                "ci_high": t.ci_high,
                "p_value": t.p_value,
            }
        )
    out = pd.DataFrame(rows, columns=["venue_id", "n", "rate", "ci_low", "ci_high", "p_value"])
    out["p_holm"] = holm_adjust(out["p_value"].tolist()) if len(out) else []
    return out.sort_values("rate", ascending=False).reset_index(drop=True)
