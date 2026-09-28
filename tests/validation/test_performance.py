"""NFR-01 performance checks with generous margins (CI runners are slower than a laptop).

The authoritative numbers come from `creaseiq benchmark` in reports/perf.json.
"""

from __future__ import annotations

import time

from creaseiq.config import Settings, load_settings
from creaseiq.data.pipeline import run_data_pipeline
from creaseiq.features.builder import FeatureBuilder
from creaseiq.services.benchmark_service import TARGETS, time_predictions
from tests.conftest import ROOT


def test_warm_prediction_latency() -> None:
    res = time_predictions(load_settings(ROOT), n=10)
    assert res["prediction_ms"] < TARGETS["prediction_ms"] * 5


def test_data_and_feature_pipeline_fast(full_project: Settings) -> None:
    t = time.perf_counter()
    res = run_data_pipeline(full_project, write_outputs=False)
    FeatureBuilder().build(res.clean.matches, res.clean.players)
    assert time.perf_counter() - t < TARGETS["pipeline_s"] / 3
