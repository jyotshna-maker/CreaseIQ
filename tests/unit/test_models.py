"""Models: splits, metrics, calibration, baselines, symmetric models, registry (FR-14..FR-18)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.metrics import log_loss as sk_log_loss

from creaseiq.exceptions import InputError, ModelIntegrityError
from creaseiq.features.builder import FeatureBuilder, FeatureSet, feature_columns, swap_orientation
from creaseiq.models import baselines as bl
from creaseiq.models import evaluate as ev
from creaseiq.models.calibrate import Calibrator, choose_method, time_ordered_calibration
from creaseiq.models.registry import ModelBundle, ModelRegistry
from creaseiq.models.splits import assert_chronological, dev_holdout_masks, walk_forward_folds
from creaseiq.models.train import (
    COMPLEXITY_ORDER,
    SPECS,
    CVResult,
    make_model,
    select_model,
    walk_forward,
)

rng = np.random.default_rng(0)
Y = rng.integers(0, 2, 400).astype(float)
P = np.clip(0.5 + 0.2 * (Y - 0.5) + rng.normal(0, 0.1, 400), 0.01, 0.99)


@pytest.fixture(scope="module")
def fs(pipeline) -> FeatureSet:
    return FeatureBuilder().build(pipeline.clean.matches, pipeline.clean.players)


def test_folds_are_chronological() -> None:
    seasons = pd.Series([2008] * 5 + [2009] * 5 + [2010] * 5 + [2011] * 5)
    folds = walk_forward_folds(seasons, 2009, 2011)
    assert [f.season for f in folds] == [2009, 2010, 2011]
    for f in folds:
        assert seasons[f.train].max() < seasons[f.valid].min()
    with pytest.raises(InputError):
        assert_chronological(np.array([2010]), np.array([2010]))
    with pytest.raises(InputError):
        assert_chronological(np.array([]), np.array([2010]))
    dev, hold = dev_holdout_masks(seasons, 2010, [2011])
    assert dev.sum() == 15 and hold.sum() == 5
    with pytest.raises(InputError):
        dev_holdout_masks(seasons, 2011, [2011])


def test_metrics_match_sklearn() -> None:
    assert ev.log_loss(Y, P) == pytest.approx(sk_log_loss(Y, P))
    assert ev.brier(Y, P) == pytest.approx(brier_score_loss(Y, P))
    assert ev.auc(Y, P) == pytest.approx(roc_auc_score(Y, P))
    assert ev.log_loss(Y, np.full(400, 0.5)) == pytest.approx(math.log(2))
    assert math.isnan(ev.auc(np.ones(5), np.full(5, 0.5)))


def test_calibration_metrics() -> None:
    table = ev.reliability_table(Y, P, 10)
    assert sum(r["n"] for r in table) == 400 and len(table) == 10
    # Well-calibrated synthetic data (y ~ Bernoulli(p)) has small ECE; under-confident P has large ECE.
    pc = rng.uniform(0.05, 0.95, 5000)
    yc = (rng.uniform(size=5000) < pc).astype(float)
    assert ev.ece(yc, pc) < 0.03 < ev.ece(Y, P)
    d = ev.brier_decomposition(Y, P)
    assert d["reliability"] - d["resolution"] + d["uncertainty"] == pytest.approx(
        ev.brier(Y, P), abs=0.02
    )
    suite = ev.metric_suite(Y, P)
    assert set(suite) >= {"log_loss", "brier", "accuracy", "auc", "ece", "brier_decomposition"}


def test_bootstrap_and_paired_tests() -> None:
    ci = ev.bootstrap_ci(Y, P, 300, 1)
    assert ci["log_loss"]["low"] < ev.log_loss(Y, P) < ci["log_loss"]["high"]
    better = ev.paired_bootstrap(Y, P, np.full(400, 0.5), 2000, 1)
    assert better["diff"] < 0 and better["ci_high"] < 0 and better["p_not_better"] < 0.01
    dm = ev.diebold_mariano(Y, P, np.full(400, 0.5))
    assert dm["dm_stat"] < 0 and dm["p_value"] < 0.01
    assert math.isnan(ev.diebold_mariano(Y[:2], P[:2], P[:2])["dm_stat"])


def test_too_good_guard() -> None:
    assert ev.too_good_check({"auc": 0.8, "accuracy": 0.6}, 0.72, 0.68)["suspicious"]
    assert ev.too_good_check({"auc": 0.6, "accuracy": 0.7}, 0.72, 0.68)["suspicious"]
    assert not ev.too_good_check({"auc": 0.55, "accuracy": 0.55}, 0.72, 0.68)["suspicious"]


def test_calibrators() -> None:
    seasons = pd.Series(np.repeat(np.arange(2010, 2018), 50))
    oof = pd.Series(P)
    cmp = time_ordered_calibration(oof, pd.Series(Y), seasons)
    assert set(cmp) == {"none", "sigmoid", "isotonic"} and "mean" in cmp["none"]
    assert choose_method(cmp) in {"none", "sigmoid", "isotonic"}
    for method in ("none", "sigmoid", "isotonic"):
        cal = Calibrator(method).fit(P, Y)  # type: ignore[arg-type]
        out = cal.symmetric_transform(P)
        assert ((out >= 0) & (out <= 1)).all()
        assert cal.symmetric_transform(1 - P) == pytest.approx(1 - out)
    assert (
        choose_method(
            {"none": {"mean": 0.69}, "sigmoid": {"mean": 0.6895}, "isotonic": {"mean": 0.60}}
        )
        == "isotonic"
    )


def test_baselines_use_training_fold_only(fs: FeatureSet) -> None:
    x, y = fs.xy("post_toss")
    train, valid = x.iloc[:500], x.iloc[500:]
    fns = bl.baselines_for("post_toss", 30.0)
    assert set(fns) == {
        "B0_constant",
        "B3_elo",
        "B1_chase_prior",
        "B2_toss_winner",
        "B4_venue_chase",
    }
    assert set(bl.baselines_for("pre_toss", 30.0)) == {"B0_constant", "B3_elo"}
    p1 = fns["B1_chase_prior"](train, valid, y.iloc[:500])
    flipped = fns["B1_chase_prior"](train, valid, 1 - y.iloc[:500])
    assert np.allclose(p1, 1 - flipped)  # depends only on the training labels
    for fn in fns.values():
        p = fn(train, valid, y.iloc[:500])
        assert len(p) == len(valid) and ((p > 0) & (p < 1)).all()


@pytest.mark.parametrize("name", ["elo_logit", "logreg", "random_forest", "hist_gb", "blend"])
def test_models_are_swap_invariant(fs: FeatureSet, name: str) -> None:
    x, y = fs.xy("post_toss")
    params = (
        {"logreg_C": 0.01, "hgb_depth": 2, "hgb_lr": 0.05, "weight": 0.5}
        if name == "blend"
        else SPECS[name].grid[0]
    )
    model = make_model(name, params, "post_toss", 0).fit(x.iloc[:800], y.iloc[:800])
    xv = x.iloc[800:900]
    p_ab = model.predict_proba(xv)
    p_ba = model.predict_proba(swap_orientation(xv, "post_toss"))
    assert np.max(np.abs(p_ab - (1 - p_ba))) < 1e-9


def test_logreg_is_exactly_antisymmetric_without_symmetrising(fs: FeatureSet) -> None:
    x, y = fs.xy("post_toss")
    model = make_model("logreg", {"C": 0.1}, "post_toss", 0).fit(x.iloc[:800], y.iloc[:800])
    xv = x.iloc[800:850]
    assert np.allclose(model.raw_proba(xv), 1 - model.raw_proba(swap_orientation(xv, "post_toss")))


def test_walk_forward_and_selection(fs: FeatureSet) -> None:
    x, y = fs.xy("pre_toss")
    seasons = fs.frame.loc[x.index, "season_year"]
    folds = walk_forward_folds(seasons.reset_index(drop=True), 2018, 2020)
    res = walk_forward(
        "logreg",
        {"C": 0.1},
        x.reset_index(drop=True),
        y.reset_index(drop=True),
        folds,
        "pre_toss",
        0,
    )
    assert set(res.fold_log_loss) == {2018, 2019, 2020} and len(res.oof) == sum(
        f.valid.sum() for f in folds
    )
    assert res.summary()["mean_log_loss"] == pytest.approx(res.mean)
    fake = {
        n: CVResult(n, {}, {1: v, 2: v + 0.002}, pd.Series(dtype=float))
        for n, v in [("hist_gb", 0.680), ("logreg", 0.6795), ("blend", 0.679)]
    }
    chosen, rule = select_model(fake)
    assert (
        chosen == "logreg" and rule["best_by_mean"] == "blend"
    )  # one-SE rule prefers the simpler model
    assert COMPLEXITY_ORDER[0] == "elo_logit"


def _bundle(fs: FeatureSet) -> ModelBundle:
    x, y = fs.xy("pre_toss")
    model = make_model("logreg", {"C": 0.1}, "pre_toss", 0).fit(x, y)
    return ModelBundle(
        "pre_toss",
        model,
        Calibrator("none"),
        feature_columns("pre_toss"),
        fs.state.params,
        2026,
        "logreg",
        {"C": 0.1},
    )


def test_registry_roundtrip_and_tamper_detection(fs: FeatureSet, tmp_path: Path) -> None:
    reg = ModelRegistry(tmp_path)
    with pytest.raises(ModelIntegrityError, match="train"):
        reg.load("pre_toss")
    entry = reg.register(_bundle(fs), data_sha256="d" * 64, git_commit="abc", metrics={"x": 1})
    bundle, loaded = reg.load("pre_toss")
    assert loaded["run_id"] == entry["run_id"] and bundle.model_name == "logreg"
    assert len(reg.runs()) == 1
    artifact = tmp_path / entry["artifact_path"]
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(ModelIntegrityError, match="integrity"):
        reg.load("pre_toss")
    artifact.unlink()
    with pytest.raises(ModelIntegrityError, match="missing"):
        reg.load("pre_toss")
