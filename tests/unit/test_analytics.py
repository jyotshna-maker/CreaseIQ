"""Analytics on the real dataset, checked against golden values (FR-06..FR-10)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from creaseiq.analytics import (
    player_stats,
    season_trends,
    team_stats,
    toss_analysis,
    venue_clusters,
    venue_stats,
)
from creaseiq.analytics.common import filter_matches, team_long
from creaseiq.analytics.summary import build_analytics_summary
from creaseiq.data.pipeline import DataPipelineResult

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden"


@pytest.fixture(scope="module")
def players(pipeline: DataPipelineResult) -> pd.DataFrame:
    return pipeline.clean.players


def test_team_long_has_two_rows_per_match(matches: pd.DataFrame) -> None:
    long = team_long(matches)
    assert len(long) == 2 * len(matches)
    dec = long[long["is_decided"]]
    assert dec.groupby("match_id")["won"].sum().eq(1).all()


def test_filters(matches: pd.DataFrame) -> None:
    assert len(filter_matches(matches, 2025, 2025)) == 74
    assert len(filter_matches(matches, stage="playoff")) == 74
    assert len(filter_matches(matches, stage="final")) == 19
    rcb = filter_matches(matches, team="rcb", venue_id="chinnaswamy")
    assert ((rcb["team1"] == "rcb") | (rcb["team2"] == "rcb")).all()


def test_toss_golden(matches: pd.DataFrame) -> None:
    t = toss_analysis.toss_effect(matches)
    assert t["overall"]["successes"] == 628 and t["overall"]["n"] == 1218
    assert t["overall"]["p_value"] > 0.05  # no detectable causal toss effect
    by = t["by_decision"].set_index("toss_decision")
    assert by.loc["field", "n"] == 810 and by.loc["bat", "n"] == 408
    assert t["decision_outcome_chi2_associational"]["p_value"] < 0.01


def test_chasing_golden(matches: pd.DataFrame) -> None:
    c = toss_analysis.chasing_advantage(matches)
    assert c["overall"]["successes"] == 666
    assert c["overall"]["p_value"] < 0.01
    assert len(c["by_season"]) == 19
    assert set(toss_analysis.field_first_share(matches)["season_year"]) == set(range(2008, 2027))


def test_toss_by_venue_holm(matches: pd.DataFrame) -> None:
    v = toss_analysis.toss_by_venue(matches, min_matches=20)
    assert (v["n"] >= 20).all()
    assert (v["p_holm"] >= v["p_value"] - 1e-12).all()


def test_team_table_matches_golden(matches: pd.DataFrame) -> None:
    table = team_stats.team_table(matches)
    golden = pd.read_csv(GOLDEN / "team_table.csv")
    cols = ["team", "matches", "wins", "losses", "titles", "finals"]
    got = table[cols].sort_values("team").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        got, golden[cols].sort_values("team").reset_index(drop=True), check_dtype=False
    )
    assert table["titles"].sum() == 19


def test_head_to_head_is_consistent(matches: pd.DataFrame) -> None:
    h = team_stats.head_to_head(matches).set_index(["team", "opponent"])
    for (a, b), row in h.iterrows():
        assert row["wins"] + h.loc[(b, a), "wins"] == row["meetings"]
    mat = team_stats.head_to_head_matrix(matches, 5)
    assert mat.shape[0] == mat.shape[1]


def test_home_advantage(matches: pd.DataFrame) -> None:
    h = team_stats.home_advantage(matches)
    assert h["overall"]["n"] == 900
    assert 0.5 < h["overall"]["rate"] < 0.56
    assert set(h["by_season"]["season_year"]).isdisjoint({2009, 2020, 2021, 2022})


def test_venue_profiles_shrinkage(matches: pd.DataFrame) -> None:
    v = venue_stats.venue_profiles(matches, prior_strength=10)
    assert len(v) == 37 and v["matches"].sum() == 1243
    small = v[v["decided"] <= 5]
    global_bf = matches.loc[matches["is_decided"], "bat_first_won"].astype(bool).mean()
    # Shrunk estimates of small venues sit closer to the global rate than raw ones.
    raw_gap = (small["bat_first_win_rate"] - global_bf).abs()
    shrunk_gap = (small["bat_first_win_rate_shrunk"] - global_bf).abs()
    assert (shrunk_gap <= raw_gap + 1e-12).all()


def test_venue_clusters_are_deterministic(matches: pd.DataFrame) -> None:
    profiles = venue_stats.venue_profiles(matches)
    a = venue_clusters.cluster_venues(profiles, seed=1)
    b = venue_clusters.cluster_venues(profiles, seed=1)
    assert a.k == b.k and a.assignments.equals(b.assignments)
    assert 2 <= a.k <= 5 and (a.assignments["matches"] >= 10).all()
    assert venue_clusters.silhouette_is_meaningful(a)


def test_era_scoring(matches: pd.DataFrame) -> None:
    e = season_trends.era_scoring_test(matches)
    assert e["n_pre"] + e["n_post"] == int(
        (matches["scores_usable"] & matches["first_innings_runs"].notna()).sum()
    )
    assert e["diff"] > 20 and e["welch_p"] < 1e-10
    assert e["ci_low"] < e["diff"] < e["ci_high"]
    s = season_trends.scoring_by_season(matches)
    assert s["share_200_plus"].between(0, 1).all()


def test_margins_and_close_finishes(matches: pd.DataFrame) -> None:
    ms = season_trends.margin_summary(matches)
    assert set(ms["margin_type"]) == {"runs", "wickets"}
    close = season_trends.closest_finishes(matches, 20)
    assert (close["closeness"].diff().dropna() >= 0).all()
    assert (close.head(16)["result_type"] == "tie").all()


def test_player_stats(matches: pd.DataFrame, players: pd.DataFrame) -> None:
    potm = player_stats.potm_leaderboard(matches, players, 5)
    assert (
        potm.iloc[0]["player"] == "AB de Villiers" and potm.iloc[0]["awards"] == 25
    )  # includes awards in tied matches
    kohli = player_stats.potm_leaderboard(matches, players, 50).set_index("player").loc["V Kohli"]
    assert kohli["teams"] == "rcb"  # award team comes from the squad, not the winner
    app = player_stats.appearances(players, matches, 3)
    assert app.iloc[0]["matches"] >= 270
    cont = player_stats.squad_continuity(players, matches)
    assert cont["mean_jaccard"].between(0, 1).all()
    off = player_stats.officials_table(matches)
    assert (off["matches"] >= 20).all()


def test_summary_is_serialisable(
    matches: pd.DataFrame, players: pd.DataFrame, tmp_path: Path
) -> None:
    from creaseiq.utils import read_json, write_json

    summary = build_analytics_summary(matches, players)
    write_json(tmp_path / "a.json", summary)
    back = read_json(tmp_path / "a.json")
    assert back["toss"]["overall"]["n"] == 1218
    assert back["venue_clusters"]["k"] >= 2
