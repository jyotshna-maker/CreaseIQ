"""Venue analytics (FR-07) with shrinkage toward league-wide values.

Venues hosting few matches have noisy raw averages: a ground with 3 matches can show a
100% chase rate. Shrinkage pulls each estimate toward the global value with a pseudo-count
``m``, so small venues are treated conservatively. Large venues keep their own signal.
"""

from __future__ import annotations

import pandas as pd

from creaseiq.analytics.hypothesis_tests import shrunk_mean, shrunk_rate


def venue_profiles(m: pd.DataFrame, prior_strength: float = 10.0) -> pd.DataFrame:
    """One row per venue: volume, raw and shrunk scoring, bat-first win rate, toss habits.

    Args:
        m: Canonical match table.
        prior_strength: Shrinkage pseudo-count ``m`` (matches' worth of prior belief).
    """
    scored = m[m["scores_usable"] & m["first_innings_runs"].notna()]
    dec = m[m["is_decided"]]
    g_score = scored.groupby("venue_id")["first_innings_runs"].agg(["sum", "count", "mean"])
    g_dec = dec.groupby("venue_id")["bat_first_won"].agg(
        bf_wins=lambda s: int(s.astype(bool).sum()), decided="size"
    )
    g_all = m.groupby("venue_id").agg(
        venue=("venue", "first"),
        city=("city", "first"),
        country=("country", "first"),
        matches=("match_id", "size"),
        first_season=("season_year", "min"),
        last_season=("season_year", "max"),
        field_share=("toss_decision", lambda s: float((s == "field").mean())),
    )
    out = (
        g_all.join(g_score, how="left")
        .join(g_dec, how="left")
        .fillna({"sum": 0, "count": 0, "bf_wins": 0, "decided": 0})
    )
    global_mean = float(scored["first_innings_runs"].mean())
    global_bf = float(dec["bat_first_won"].astype(bool).mean())
    out["avg_first_innings"] = out["mean"]
    out["avg_first_innings_shrunk"] = [
        shrunk_mean(s, n, global_mean, prior_strength)
        for s, n in zip(out["sum"], out["count"], strict=True)
    ]
    out["bat_first_win_rate"] = out["bf_wins"] / out["decided"].where(out["decided"] > 0)
    out["bat_first_win_rate_shrunk"] = [
        shrunk_rate(w, n, global_bf, prior_strength)
        for w, n in zip(out["bf_wins"], out["decided"], strict=True)
    ]
    out["chase_win_rate_shrunk"] = 1 - out["bat_first_win_rate_shrunk"]
    keep = [
        "venue",
        "city",
        "country",
        "matches",
        "decided",
        "first_season",
        "last_season",
        "avg_first_innings",
        "avg_first_innings_shrunk",
        "bat_first_win_rate",
        "bat_first_win_rate_shrunk",
        "chase_win_rate_shrunk",
        "field_share",
    ]
    return out[keep].reset_index().sort_values("matches", ascending=False).reset_index(drop=True)
