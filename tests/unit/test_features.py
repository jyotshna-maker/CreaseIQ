"""Feature engineering: Elo properties, state components, symmetry declarations (FR-12, FR-13)."""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from creaseiq.exceptions import InputError
from creaseiq.features.builder import (
    ANTISYMMETRIC_POST_EXTRA,
    ANTISYMMETRIC_PRE,
    FEATURE_GROUPS,
    SYMMETRIC_PRE,
    FeatureBuilder,
    FeatureParams,
    MatchState,
    feature_columns,
    orientation_flip,
    swap_orientation,
)
from creaseiq.features.elo import (
    EloParams,
    EloRatingSystem,
    expected_score,
    margin_multiplier,
    margin_units,
)
from creaseiq.features.form import FormState
from creaseiq.features.head_to_head import HeadToHeadState
from creaseiq.features.squad import SquadState
from creaseiq.features.venue_effects import VenueState

ratings = st.floats(1000, 2000)


@given(ra=ratings, rb=ratings, h=st.floats(-100, 100))
def test_expected_scores_are_complementary(ra: float, rb: float, h: float) -> None:
    assert expected_score(ra, rb, 400, h) + expected_score(rb, ra, 400, -h) == pytest.approx(1.0)


@given(ra=ratings, rb=ratings, delta=st.floats(1, 300))
def test_expected_score_monotone(ra: float, rb: float, delta: float) -> None:
    assert expected_score(ra + delta, rb) > expected_score(ra, rb)


@given(
    ra=ratings,
    rb=ratings,
    score=st.sampled_from([0.0, 0.5, 1.0]),
    mtype=st.sampled_from(["runs", "wickets", None]),
    mval=st.floats(1, 140),
    dls=st.booleans(),
    use_margin=st.booleans(),
)
def test_elo_update_is_zero_sum_and_directional(
    ra: float, rb: float, score: float, mtype: str | None, mval: float, dls: bool, use_margin: bool
) -> None:
    elo = EloRatingSystem(EloParams(use_margin=use_margin), ratings={"a": ra, "b": rb})
    da, db = elo.compute_update("a", "b", score, margin_type=mtype, margin_value=mval, dls=dls)
    assert da + db == pytest.approx(0.0, abs=1e-9)
    if score == 1.0:
        assert da > 0
    if score == 0.0:
        assert da < 0


@given(units=st.floats(0.1, 20), diff=st.floats(-400, 400))
def test_margin_multiplier_positive_and_increasing(units: float, diff: float) -> None:
    assert margin_multiplier(units, diff) > 0
    assert margin_multiplier(units + 1, diff) > margin_multiplier(units, diff)


def test_margin_units() -> None:
    assert margin_units("runs", 20) == 2.0
    assert margin_units("wickets", 6) == 3.0
    assert margin_units(None, None) == 0.0


def test_season_regression_and_early_k() -> None:
    elo = EloRatingSystem(EloParams(season_regression=0.5, early_season_k_boost=1.0))
    elo.start_season(2020)
    elo.ratings = {"a": 1600.0, "b": 1400.0}
    elo.start_season(2020)  # idempotent within a season
    assert elo.rating("a") == 1600.0
    elo.start_season(2021)
    assert elo.rating("a") == 1550.0 and elo.rating("b") == 1450.0
    fresh_k = elo._k("a")
    elo.apply({}, ["a"] * 7)
    assert fresh_k == pytest.approx(2 * elo._k("a"))
    assert elo.win_probability("a", "b", a_home=True) > elo.win_probability("a", "b")


def test_form_state() -> None:
    fs = FormState(prior_m=2)
    d0 = pd.Timestamp("2020-01-01")
    empty = fs.features("x", d0, 2020, 160.0)
    assert empty["form10"] == 0.5 and empty["runs_for10"] == 160.0 and empty["rest_days"] == 30.0
    fs.update("x", d0, 2020, 1.0, 180.0, 150.0)
    fs.update("x", d0 + pd.Timedelta(days=2), 2020, None, None, None)  # no result: no form change
    f = fs.features("x", d0 + pd.Timedelta(days=5), 2020, 160.0)
    assert (
        f["form10"] == pytest.approx(2 / 3) and f["runs_for10"] == 180.0 and f["rest_days"] == 3.0
    )
    assert f["season_games"] == 1.0
    assert fs.features("x", d0 + pd.Timedelta(days=400), 2021, 160.0)["season_games"] == 0.0


def test_head_to_head_antisymmetry() -> None:
    h = HeadToHeadState(recent_seasons=2)
    for season, w in [(2010, "a"), (2011, "a"), (2019, "b")]:
        h.update("a", "b", season, w)
    h.update("a", "b", 2019, None)
    fa, fb = h.features("a", "b", 2020), h.features("b", "a", 2020)
    assert fa["h2h_edge"] == -fb["h2h_edge"] > 0
    assert fa["h2h_recent_edge"] < 0 and fa["h2h_meetings"] == 3.0


def test_venue_state_shrinks_to_global() -> None:
    v = VenueState(prior_m=10)
    assert v.features("x", "a", "b")["venue_first_innings"] == 160.0
    v.update("y", 200.0, True, "a", "b", "a")
    f = v.features("x", "a", "b")  # unseen venue -> global so far
    assert f["venue_first_innings"] == 200.0 and f["venue_bat_first_rate"] == 1.0
    g = v.features("y", "a", "b")
    assert g["venue_team_edge"] > 0


def test_squad_state() -> None:
    s = SquadState()
    xi = frozenset({"p1", "p2"})
    assert s.features("t", xi)["xi_debutants"] == 2.0
    s.update("t", xi, "p1")
    f = s.features("t", frozenset({"p1", "p3"}))
    assert (
        f["xi_potm"] == 1.0
        and f["xi_debutants"] == 1.0
        and f["xi_continuity"] == pytest.approx(1 / 3)
    )


def test_declarations_are_consistent() -> None:
    pre, post = feature_columns("pre_toss"), feature_columns("post_toss")
    assert len(set(post)) == len(post) and set(pre) < set(post)
    assert set(pre) == set(ANTISYMMETRIC_PRE) | set(SYMMETRIC_PRE)
    assert set(post) - set(pre) == set(ANTISYMMETRIC_POST_EXTRA)
    assert {c for g in FEATURE_GROUPS.values() for c in g} == set(post)
    with pytest.raises(InputError):
        feature_columns("in_play")  # type: ignore[arg-type]


def test_pair_features_respect_declared_symmetry(pipeline) -> None:
    """Computing (B, A) must equal the declared swap of (A, B), for every feature."""
    m, p = pipeline.clean.matches, pipeline.clean.players
    state = FeatureBuilder().state_as_of(m, p, pd.Timestamp("2019-04-01"))
    kw = {
        "venue_id": "wankhede",
        "date": pd.Timestamp("2019-04-01"),
        "season_year": 2019,
        "is_playoff": False,
    }
    ab = state.pair_features(
        "mi", "csk", a_home=True, b_home=False, toss_winner="csk", bat_first="mi", **kw
    )
    ba = state.pair_features(
        "csk", "mi", a_home=False, b_home=True, toss_winner="csk", bat_first="mi", **kw
    )
    swapped = swap_orientation(pd.DataFrame([ab]), "post_toss").iloc[0]
    for col in feature_columns("post_toss"):
        assert ba[col] == pytest.approx(swapped[col], abs=1e-12), col


def test_orientation_flip_is_deterministic_and_balanced() -> None:
    assert orientation_flip("01-01-2020", "a", "b", 1) == orientation_flip(
        "01-01-2020", "b", "a", 1
    )
    flips = [orientation_flip(f"{d:02d}-01-2020", "a", "b", 7) for d in range(1, 29)]
    assert 5 < sum(flips) < 23


def test_build_outputs(pipeline) -> None:
    fs = FeatureBuilder(FeatureParams(seed=3)).build(
        pipeline.clean.matches.head(80), pipeline.clean.players
    )
    assert len(fs.frame) == 80 and len(fs.team_state) == 160
    assert fs.frame["a_wins"].isna().sum() == (~fs.frame["is_decided"]).sum()
    assert set(fs.elo_history.columns) >= {"team", "rating_before", "delta"}
    assert isinstance(fs.state, MatchState)
