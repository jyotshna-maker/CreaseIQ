"""Performance benchmark (NFR-01, NFR-08) → ``reports/perf.json``.

Measured on the machine it runs on (CPU and OS are recorded):

* the full pipeline: ingest → validate → clean → DB load → features → fit the registered
  model configuration for both tiers;
* warm single-prediction latency (median and p95 over many fixtures);
* warm dashboard page render time (Streamlit ``AppTest``);
* peak Python memory during the pipeline (``tracemalloc``).
"""

from __future__ import annotations

import os
import platform
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

import pandas as pd

from creaseiq.config import Settings
from creaseiq.data.pipeline import run_data_pipeline
from creaseiq.db.loader import load_database
from creaseiq.db.session import make_engine
from creaseiq.features.builder import FeatureBuilder
from creaseiq.models.predict import Fixture, Predictor
from creaseiq.models.registry import ModelRegistry
from creaseiq.models.train import make_model
from creaseiq.utils import write_json

TARGETS = {
    "pipeline_s": 90.0,
    "prediction_ms": 200.0,
    "page_render_s": 2.0,
    "peak_memory_mb": 1024.0,
}


def time_pipeline(settings: Settings) -> dict[str, Any]:
    """Wall time and peak memory of the end-to-end pipeline with the registered configuration."""
    registry = ModelRegistry(settings.path("models_dir"))
    tracemalloc.start()
    t0 = time.perf_counter()
    stages: dict[str, float] = {}
    res = run_data_pipeline(settings, write_outputs=False)
    stages["data"] = time.perf_counter() - t0
    t = time.perf_counter()
    load_database(make_engine("sqlite:///:memory:"), res.clean.matches, res.clean.players, res.maps)
    stages["db"] = time.perf_counter() - t
    t = time.perf_counter()
    bundle, _ = registry.load("post_toss")
    fs = FeatureBuilder(bundle.feature_params).build(res.clean.matches, res.clean.players)
    stages["features"] = time.perf_counter() - t
    t = time.perf_counter()
    for tier in ("pre_toss", "post_toss"):
        b, _ = registry.load(tier)
        x, y = fs.xy(tier)
        make_model(b.model_name, b.params, tier, settings.seed).fit(x, y)
    stages["train_best"] = time.perf_counter() - t
    total = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"pipeline_s": total, "stages_s": stages, "peak_memory_mb": peak / 1e6}


def time_predictions(settings: Settings, n: int = 60) -> dict[str, Any]:
    """Warm prediction latency over ``n`` fixtures (alternating pre- and post-toss)."""
    from creaseiq.data.canonical import load_canonical_maps
    from creaseiq.data.pipeline import load_processed

    matches, players = load_processed(settings)
    predictor = Predictor(
        ModelRegistry(settings.path("models_dir")), matches, players, load_canonical_maps(settings)
    )
    date = matches["date"].max() + pd.Timedelta(days=1)
    teams = sorted(
        set(matches.loc[matches["season_year"] == matches["season_year"].max(), "team1"])
    )
    predictor.predict(Fixture(teams[0], teams[1], "wankhede", date))  # warm-up (state build)
    predictor.predict(
        Fixture(teams[0], teams[1], "wankhede", date, toss_winner=teams[0], toss_decision="bat")
    )
    times = []
    for i in range(n):
        a, b = teams[i % len(teams)], teams[(i + 1) % len(teams)]
        fx = Fixture(
            a,
            b,
            "wankhede",
            date,
            toss_winner=a if i % 2 else None,
            toss_decision="field" if i % 2 else None,
        )
        t = time.perf_counter()
        predictor.predict(fx)
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    return {
        "prediction_ms": statistics.median(times),
        "prediction_p95_ms": times[int(0.95 * (len(times) - 1))],
        "n": n,
    }


def time_pages(app_dir: Path) -> dict[str, Any]:
    """Warm render time of every dashboard page (second run of each AppTest)."""
    from streamlit.testing.v1 import AppTest

    results = {}
    for page in [app_dir / "Home.py", *sorted((app_dir / "pages").glob("*.py"))]:
        at = AppTest.from_file(str(page), default_timeout=120)
        at.run()
        t = time.perf_counter()
        at.run()
        results[page.stem] = time.perf_counter() - t
    return {"page_render_s": max(results.values()), "pages_s": results}


def run_benchmark(settings: Settings, include_pages: bool = True) -> dict[str, Any]:
    """Run everything, compare against the NFR targets and write ``reports/perf.json``."""
    out: dict[str, Any] = {
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "targets": TARGETS,
    }
    out.update(time_pipeline(settings))
    out.update(time_predictions(settings))
    if include_pages:
        out.update(time_pages(Path(__file__).resolve().parents[1] / "app"))
    out["passed"] = {k: bool(out[k] <= v) for k, v in TARGETS.items() if k in out}
    write_json(settings.path("reports_dir") / "perf.json", out)
    return out
