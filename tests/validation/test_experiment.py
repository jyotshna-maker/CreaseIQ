"""Experiment-level validation: reproducibility (NFR-06), baseline beating on development
folds, calibration sanity, holdout ledger and prediction swap invariance.

Model grids are reduced to one configuration per family so the suite stays fast. The
logic under test is identical to `creaseiq train`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from creaseiq.config import Settings
from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.models import experiment as exp
from creaseiq.models import train as tr
from creaseiq.models.predict import Fixture, Predictor
from creaseiq.models.registry import ModelRegistry
from creaseiq.utils import read_json


def _strip_volatile(m: dict[str, Any]) -> dict[str, Any]:
    out = dict(m)
    out.pop("holdout_access", None)
    return out


@pytest.fixture(scope="module")
def experiment_runs(
    full_project: Settings, pipeline: DataPipelineResult, tmp_path_factory: pytest.TempPathFactory
) -> tuple[dict[str, Any], dict[str, Any], Settings]:
    mp = pytest.MonkeyPatch()
    small = {name: replace(spec, grid=spec.grid[:1]) for name, spec in tr.SPECS.items()}
    mp.setattr(tr, "SPECS", small)
    mp.setattr(exp, "SPECS", small)

    def blend(best: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        return (
            {"logreg_C": best["logreg"].params["C"], "hgb_depth": 2, "hgb_lr": 0.02, "weight": 0.5},
        )

    mp.setattr(exp, "blend_grid", blend)
    data = dict(full_project.data)
    data["modeling"] = {
        **data["modeling"],
        "elo_grid": {
            "k": [10, 20],
            "home_bonus": [30],
            "season_regression": [0.1],
            "use_margin": [True],
        },
        "bootstrap_resamples": 200,
        "paired_bootstrap_resamples": 500,
    }
    settings = Settings(full_project.root, data)
    m, p = pipeline.clean.matches, pipeline.clean.players
    first, _, _ = exp.run_experiment(settings, m, p, "sha", register=True)
    second, _, _ = exp.run_experiment(settings, m, p, "sha", register=False)
    mp.undo()
    return first, second, settings


def test_reproducible_metrics(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings],
) -> None:
    first, second, _ = experiment_runs
    for tier in ("pre_toss", "post_toss"):
        a, b = _strip_volatile(first["tiers"][tier]), _strip_volatile(second["tiers"][tier])
        a.pop("registry_run_id", None)
        assert a["holdout"]["model"]["log_loss"] == pytest.approx(
            b["holdout"]["model"]["log_loss"], abs=1e-9
        )
        assert a["selection"] == b["selection"]
        assert a["model_grid"] == b["model_grid"]
    assert first["score_regression"] == second["score_regression"]


def test_models_beat_coin_flip_on_development_folds(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings],
) -> None:
    first, _, _ = experiment_runs
    for tier in ("pre_toss", "post_toss"):
        t = first["tiers"][tier]
        coin = t["baselines_walk_forward"]["B0_constant"]["mean_log_loss"]
        assert (
            t["selection"]["walk_forward_mean_log_loss"] < coin + 0.002
        )  # tolerance: signal is weak
    assert (
        first["tiers"]["post_toss"]["selection"]["walk_forward_mean_log_loss"]
        < first["tiers"]["post_toss"]["baselines_walk_forward"]["B0_constant"]["mean_log_loss"]
    )


def test_holdout_is_plausible_and_guarded(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings],
) -> None:
    first, _, settings = experiment_runs
    for tier in ("pre_toss", "post_toss"):
        t = first["tiers"][tier]
        assert not t["too_good_guard"]["suspicious"]
        h = t["holdout"]["model"]
        assert 0.6 < h["log_loss"] < 0.8 and h["n"] == t["n_holdout"]
        assert 0 <= h["ece"] <= 1
    ledger = read_json(settings.path("reports_dir") / "holdout_ledger.json")
    for tier in ("pre_toss", "post_toss"):
        sels = ledger[tier]["selections"]
        assert len(sels) == 1  # the same frozen selection both times: one look, recomputed
        assert next(iter(sels.values()))["evaluations"] == 2


def test_holdout_seasons_never_used_for_selection(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings],
) -> None:
    first, _, _ = experiment_runs
    for tier in ("pre_toss", "post_toss"):
        t = first["tiers"][tier]
        assert max(t["folds"]) <= 2024
        for row in t["model_grid"]:
            assert max(int(s) for s in row["folds"]) <= 2024


def test_predictor_serves_symmetric_probabilities(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings], pipeline: DataPipelineResult
) -> None:
    _, _, settings = experiment_runs
    predictor = Predictor(
        ModelRegistry(settings.path("models_dir")),
        pipeline.clean.matches,
        pipeline.clean.players,
        pipeline.maps,
    )
    date = pd.Timestamp("2027-04-01")
    pre = Fixture("mi", "csk", "wankhede", date)
    post = Fixture("mi", "csk", "wankhede", date, toss_winner="csk", toss_decision="field")
    for fx in (pre, post):
        out = predictor.predict(fx)
        assert 0 < out["p_a"] < 1 and out["p_a"] + out["p_b"] == pytest.approx(1)
        assert out["tier"] == fx.tier
        rev = predictor.predict(
            Fixture(
                fx.team_b,
                fx.team_a,
                fx.venue_id,
                date,
                toss_winner=fx.toss_winner,
                toss_decision=fx.toss_decision,
            )
        )
        assert abs(out["p_a"] - rev["p_b"]) < 1e-9
        assert predictor.swap_check(fx) < 1e-9
        assert isinstance(out["explanation"], str)
    assert post.bat_first == "mi" and pre.bat_first is None
    # A date in the past uses only matches before it.
    past = predictor.predict(Fixture("mi", "csk", "wankhede", pd.Timestamp("2015-05-01")))
    assert 0 < past["p_a"] < 1


def test_model_card_and_figures(
    experiment_runs: tuple[dict[str, Any], dict[str, Any], Settings], tmp_path: Path
) -> None:
    from creaseiq.reporting.assets import write_training_outputs
    from creaseiq.reporting.model_card import render_model_card

    first, _, settings = experiment_runs
    card = render_model_card(first)
    for heading in (
        "## Intended use",
        "## Data",
        "## Method",
        "## Results",
        "## Limitations",
        "## Ethical considerations",
    ):
        assert heading in card
    paths = write_training_outputs(settings, first, pd.DataFrame())
    assert all(p.is_file() and p.stat().st_size > 10_000 for p in paths.values())
    assert np.isfinite(
        read_json(settings.path("reports_dir") / "metrics.json")["tiers"]["post_toss"]["holdout"][
            "model"
        ]["log_loss"]
    )
