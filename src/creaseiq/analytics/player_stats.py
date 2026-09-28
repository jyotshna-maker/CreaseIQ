"""Player-of-the-match, appearances, squad continuity and officials (FR-10, P2)."""

from __future__ import annotations

import pandas as pd


def potm_leaderboard(m: pd.DataFrame, players: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Most Player-of-the-Match awards, with the franchise(s) the player was listed for.

    The award can go to a player on the losing side, so the player's team comes from the
    squad lists, not from the match winner.
    """
    d = m.loc[m["player_of_match"].notna(), ["match_id", "season_year", "player_of_match"]]
    d = d.merge(
        players[["match_id", "player", "team"]],
        left_on=["match_id", "player_of_match"],
        right_on=["match_id", "player"],
        how="left",
    )
    counts = d.groupby("player_of_match").agg(
        awards=("match_id", "size"),
        first=("season_year", "min"),
        last=("season_year", "max"),
        teams=("team", lambda s: ", ".join(sorted(set(s.dropna())))),
    )
    return (
        counts.sort_values(["awards", "last"], ascending=[False, False])
        .head(top)
        .reset_index()
        .rename(columns={"player_of_match": "player"})
    )


def appearances(players: pd.DataFrame, m: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Most matches listed in a squad (exact-name identity)."""
    seasons = m.set_index("match_id")["season_year"]
    p = players.assign(season_year=players["match_id"].map(seasons))
    g = p.groupby("player").agg(
        matches=("match_id", "nunique"),
        seasons=("season_year", "nunique"),
        teams=("team", lambda s: ", ".join(sorted(set(s)))),
    )
    return g.sort_values("matches", ascending=False).head(top).reset_index()


def squad_continuity(players: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """Mean Jaccard similarity between each team's consecutive squads, per team-season.

    1.0 means the same XI every match; lower values mean more rotation.
    """
    order = m[["match_id", "date", "season_year"]]
    squads = (
        players.groupby(["match_id", "team"])["player"]
        .apply(frozenset)
        .reset_index()
        .merge(order, on="match_id")
        .sort_values(["team", "date", "match_id"])
    )
    rows = []
    for team, g in squads.groupby("team"):
        prev: frozenset[str] | None = None
        prev_season: int | None = None
        for r in g.itertuples():
            if prev is not None and prev_season == r.season_year:
                rows.append(
                    {
                        "team": team,
                        "season_year": r.season_year,
                        "jaccard": len(prev & r.player) / len(prev | r.player),
                    }
                )
            prev, prev_season = r.player, r.season_year
    out = pd.DataFrame(rows)
    return (
        out.groupby(["team", "season_year"])["jaccard"]
        .agg(["mean", "size"])
        .rename(columns={"mean": "mean_jaccard", "size": "transitions"})
        .reset_index()
    )


def officials_table(m: pd.DataFrame, min_matches: int = 20) -> pd.DataFrame:
    """Descriptive umpire table (P2). **No causal claim**: umpires are not randomly assigned,
    and bat-first win rates under an umpire mostly reflect venues and eras."""
    long = pd.concat(
        [
            m[["match_id", "season_year", "is_decided", "bat_first_won"]].assign(official=m[c])
            for c in ("umpire1", "umpire2")
        ],
        ignore_index=True,
    ).dropna(subset=["official"])
    g = long.groupby("official")
    out = g.agg(
        matches=("match_id", "nunique"), first=("season_year", "min"), last=("season_year", "max")
    )
    out["bat_first_win_rate"] = g.apply(
        lambda x: float(x.loc[x["is_decided"], "bat_first_won"].astype(bool).mean())
    )
    return out[out["matches"] >= min_matches].sort_values("matches", ascending=False).reset_index()
