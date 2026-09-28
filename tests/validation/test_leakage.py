"""Leakage defenses (PLAN §7). Written before any model code (Phase 3 exit criterion).

1. Future perturbation: deleting or mutating later matches never changes earlier features.
2. Label shuffle: with shuffled labels, a trained model's AUC collapses to about 0.5.
3. Same day: double-headers never see each other.
4. Column allow-list: post-match columns raise FeatureLeakageError.
5. The "too good" guard is tested with evaluation in tests/validation/test_evaluation.py.
Also: the orientation flag carries no signal, and the raw team1 order would carry signal
(the trap this design avoids).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.exceptions import FeatureLeakageError
from creaseiq.features.builder import (
    FeatureBuilder,
    FeatureSet,
    assert_no_leakage,
    feature_columns,
)

CUTOFF = pd.Timestamp("2016-05-01")


@pytest.fixture(scope="module")
def full(pipeline: DataPipelineResult) -> FeatureSet:
    return FeatureBuilder().build(pipeline.clean.matches, pipeline.clean.players)


def _features_upto(fs: FeatureSet, cutoff: pd.Timestamp) -> pd.DataFrame:
    f = fs.frame[fs.frame["date"] <= cutoff]
    return f.drop(columns=["a_wins"]).sort_values("match_id").reset_index(drop=True)


def test_future_deletion_does_not_change_past(
    pipeline: DataPipelineResult, full: FeatureSet
) -> None:
    m, p = pipeline.clean.matches, pipeline.clean.players
    truncated = FeatureBuilder().build(
        m[m["date"] <= CUTOFF], p[p["match_id"].isin(m.loc[m["date"] <= CUTOFF, "match_id"])]
    )
    pd.testing.assert_frame_equal(
        _features_upto(full, CUTOFF), _features_upto(truncated, CUTOFF), check_exact=True
    )


def test_future_mutation_does_not_change_past(
    pipeline: DataPipelineResult, full: FeatureSet
) -> None:
    m = pipeline.clean.matches.copy()
    later = m["date"] > CUTOFF
    # Flip every later result and inflate its scores: a maximal "future" perturbation.
    m.loc[later & m["is_decided"], "winner"] = np.where(
        m.loc[later & m["is_decided"], "winner"] == m.loc[later & m["is_decided"], "team1"],
        m.loc[later & m["is_decided"], "team2"],
        m.loc[later & m["is_decided"], "team1"],
    )
    m.loc[later, ["team1_runs", "team2_runs", "first_innings_runs"]] += 50
    m.loc[later, "player_of_match"] = "Nobody"
    mutated = FeatureBuilder().build(m, pipeline.clean.players)
    pd.testing.assert_frame_equal(
        _features_upto(full, CUTOFF), _features_upto(mutated, CUTOFF), check_exact=True
    )


def test_same_day_matches_do_not_see_each_other(
    pipeline: DataPipelineResult, full: FeatureSet
) -> None:
    m = pipeline.clean.matches
    dup_dates = m["date"][m["date"].duplicated()].unique()
    assert len(dup_dates) > 100
    day = pd.Timestamp(dup_dates[len(dup_dates) // 2])
    same_day = m[m["date"] == day].sort_values("match_id")
    first, second = same_day.iloc[0], same_day.iloc[1]
    # Remove the first match of the day: the second match's features must not change.
    without = FeatureBuilder().build(m[m["match_id"] != first["match_id"]], pipeline.clean.players)
    a = (
        full.frame[full.frame["match_id"] == second["match_id"]]
        .drop(columns=["a_wins"])
        .reset_index(drop=True)
    )
    b = (
        without.frame[without.frame["match_id"] == second["match_id"]]
        .drop(columns=["a_wins"])
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_first_match_has_no_history(full: FeatureSet) -> None:
    first = full.frame.sort_values("match_id").iloc[0]
    assert first["elo_diff"] == 0.0 and first["h2h_meetings"] == 0.0 and first["form10_diff"] == 0.0


def test_as_of_state_matches_build(pipeline: DataPipelineResult, full: FeatureSet) -> None:
    m, p = pipeline.clean.matches, pipeline.clean.players
    state = FeatureBuilder().state_as_of(m, p, CUTOFF)
    assert state.last_date is not None and state.last_date < CUTOFF
    assert FeatureBuilder().state_as_of(m, p, pd.Timestamp("2000-01-01")).last_date is None


def test_label_shuffle_collapses_auc(full: FeatureSet) -> None:
    x, y = full.xy("post_toss")
    seasons = full.frame.loc[x.index, "season_year"]
    rng = np.random.default_rng(0)
    aucs = []
    for _ in range(20):
        y_shuf = pd.Series(rng.permutation(y.to_numpy()), index=y.index)
        tr, te = seasons <= 2019, seasons > 2019
        model = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)).fit(
            x[tr], y_shuf[tr]
        )
        aucs.append(roc_auc_score(y_shuf[te], model.predict_proba(x[te])[:, 1]))
    assert abs(float(np.mean(aucs)) - 0.5) < 0.03


def test_allow_list_enforced(full: FeatureSet) -> None:
    for tier in ("pre_toss", "post_toss"):
        x, _ = full.xy(tier)
        assert list(x.columns) == feature_columns(tier)
        assert_no_leakage(x.columns, tier)
    with pytest.raises(FeatureLeakageError, match="Post-match"):
        assert_no_leakage([*feature_columns("pre_toss"), "winner"], "pre_toss")
    with pytest.raises(FeatureLeakageError, match="allow-list"):
        assert_no_leakage([*feature_columns("pre_toss"), "a_bats_first"], "pre_toss")
    assert not set(feature_columns("pre_toss")) & {"a_bats_first", "a_won_toss"}


def _bootstrap_auc_ci(
    y: np.ndarray, s: np.ndarray, n: int = 1000, seed: int = 0
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    vals = []
    for _ in range(n):
        b = rng.choice(idx, len(idx))
        if len(np.unique(y[b])) == 2:
            vals.append(roc_auc_score(y[b], s[b]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def test_orientation_flag_carries_no_signal(full: FeatureSet) -> None:
    f = full.frame[full.frame["is_decided"]]
    lo, hi = _bootstrap_auc_ci(
        f["a_wins"].to_numpy(), f["orientation_flip"].astype(float).to_numpy()
    )
    assert lo <= 0.5 <= hi


def test_raw_team1_order_would_leak_batting_order(pipeline: DataPipelineResult) -> None:
    """Documents the trap: from 2018, being raw team1 means batting first, which predicts losing."""
    m = pipeline.clean.matches
    d = m[m["is_decided"] & (m["season_year"] >= 2018)]
    team1_win_rate = float((d["winner"] == d["team1"]).mean())
    assert (d["team1_bats_first"]).all()
    assert team1_win_rate < 0.48  # a model keyed on raw order would learn this artefact
