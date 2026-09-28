"""Team analytics (FR-06): records, titles, season form, head-to-head and home advantage."""

from __future__ import annotations

from typing import Any

import pandas as pd

from creaseiq.analytics.common import team_long
from creaseiq.analytics.hypothesis_tests import binomial_test, wilson_ci


def team_table(m: pd.DataFrame) -> pd.DataFrame:
    """All-time record per franchise (voided matches excluded).

    Columns: team, seasons, matches, wins, losses, no_decision, win_pct, ci_low, ci_high,
    titles, finals, best_season, worst_season.
    """
    long = team_long(m[~m["voided"]])
    g = long.groupby("team")
    out = pd.DataFrame(
        {
            "seasons": g["season_year"].nunique(),
            "matches": g.size(),
            "wins": g["won"].apply(lambda s: int(s.fillna(False).sum())),
            "losses": g["won"].apply(lambda s: int((s == False).sum())),  # noqa: E712 - nullable boolean
        }
    )
    out["no_decision"] = out["matches"] - out["wins"] - out["losses"]
    out["win_pct"] = out["wins"] / (out["wins"] + out["losses"])
    ci = [wilson_ci(int(w), int(w + lo)) for w, lo in zip(out["wins"], out["losses"], strict=True)]
    out["ci_low"] = [c[0] for c in ci]
    out["ci_high"] = [c[1] for c in ci]
    finals = m[m["is_final"]]
    out["titles"] = finals["winner"].value_counts().reindex(out.index, fill_value=0)
    out["finals"] = (
        pd.concat([finals["team1"], finals["team2"]])
        .value_counts()
        .reindex(out.index, fill_value=0)
    )
    seasonal = season_win_pct(m)
    seasonal = seasonal[seasonal["decided"] >= 5]
    best = seasonal.loc[seasonal.groupby("team")["win_pct"].idxmax()].set_index("team")[
        "season_year"
    ]
    worst = seasonal.loc[seasonal.groupby("team")["win_pct"].idxmin()].set_index("team")[
        "season_year"
    ]
    out["best_season"] = best.reindex(out.index)
    out["worst_season"] = worst.reindex(out.index)
    return (
        out.reset_index().sort_values(["titles", "win_pct"], ascending=False).reset_index(drop=True)
    )


def season_win_pct(m: pd.DataFrame) -> pd.DataFrame:
    """Per team and season: matches, decided, wins, win_pct (voided excluded)."""
    long = team_long(m[~m["voided"]])
    g = long.groupby(["season_year", "team"])
    out = g.agg(matches=("match_id", "size"), decided=("is_decided", "sum"))
    out["wins"] = g["won"].apply(lambda s: int(s.fillna(False).sum()))
    out["win_pct"] = out["wins"] / out["decided"].where(out["decided"] > 0)
    return out.reset_index()


def head_to_head(m: pd.DataFrame, min_meetings: int = 1) -> pd.DataFrame:
    """Long head-to-head table: team, opponent, meetings (decided), wins, win_pct."""
    long = team_long(m[m["is_decided"]])
    g = long.groupby(["team", "opponent"])
    out = g.agg(meetings=("match_id", "size"))
    out["wins"] = g["won"].apply(lambda s: int(s.fillna(False).sum()))
    out["win_pct"] = out["wins"] / out["meetings"]
    out = out.reset_index()
    return out[out["meetings"] >= min_meetings].reset_index(drop=True)


def head_to_head_matrix(m: pd.DataFrame, min_meetings: int = 5) -> pd.DataFrame:
    """Square matrix of row-team win% against column-team (NaN below ``min_meetings``)."""
    h = head_to_head(m, min_meetings)
    return h.pivot(index="team", columns="opponent", values="win_pct")


def home_advantage(m: pd.DataFrame) -> dict[str, Any]:
    """Win rate of the home side in decided matches where exactly one side is at home."""
    d = m[m["is_decided"] & (m["team1_home"] != m["team2_home"])]
    home_team = d["team1"].where(d["team1_home"], d["team2"])
    home_won = (d["winner"] == home_team).astype(bool)
    res = binomial_test(int(home_won.sum()), len(d)).as_dict()
    by_season = (
        d.assign(hw=home_won)
        .groupby("season_year")["hw"]
        .agg(["mean", "size"])
        .rename(columns={"mean": "home_win_rate", "size": "n"})
        .reset_index()
    )
    return {"overall": res, "by_season": by_season}
