"""Report figures render from analytics outputs; pipeline runs write structured file logs (FR-22, NFR-07)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from creaseiq.analytics.summary import build_analytics_summary
from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.features.builder import FeatureBuilder
from creaseiq.logging_setup import configure_logging, new_run_id
from creaseiq.reporting import figures as fig
from creaseiq.reporting.drift import drift_report, psi


def test_analytics_figures(pipeline: DataPipelineResult, tmp_path: Path) -> None:
    m, p = pipeline.clean.matches, pipeline.clean.players
    summary = build_analytics_summary(m, p)
    outs = [
        fig.scoring_trend(summary["scoring_by_season"], tmp_path / "s.png"),
        fig.chase_by_season(
            summary["chasing"]["by_season"],
            summary["chasing"]["overall"]["rate"],
            tmp_path / "c.png",
        ),
        fig.elo_timeline(
            FeatureBuilder().build(m, p).elo_history, ["mi", "csk"], tmp_path / "e.png"
        ),
    ]
    assert all(o.stat().st_size > 10_000 for o in outs)


def test_psi_properties() -> None:
    ref = pd.Series(range(1000)).to_numpy(dtype=float)
    assert psi(ref, ref) < 1e-6
    assert psi(ref, ref + 800) > 0.25
    assert psi(ref[:0], ref) != psi(ref[:0], ref)  # nan for empty reference
    assert psi([1.0, 1.0], [1.0]) == 0.0
    frame = pd.DataFrame({"x": ref, "y": ref})
    rep = drift_report(frame, ["x", "y"], frame["x"] < 500, frame["x"] >= 500)
    assert set(rep["status"]) == {"alert"}


def test_pipeline_writes_structured_log_file(sample_project, tmp_path: Path) -> None:
    from creaseiq.data.pipeline import run_data_pipeline

    log_file = tmp_path / "logs" / "creaseiq.log"
    # configure_logging only attaches handlers on its first call in a process; when an earlier
    # test already configured it, this test attaches its own file handler (directory first).
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = configure_logging("INFO", log_file)
    # configure_logging is idempotent; attach a file handler for this test explicitly if needed.
    if not any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file
        for h in logger.handlers
    ):
        handler = logging.FileHandler(log_file, encoding="utf-8")
        from creaseiq.logging_setup import KeyValueFormatter

        handler.setFormatter(KeyValueFormatter())
        logger.addHandler(handler)
    else:
        handler = None
    run_id = new_run_id()
    run_data_pipeline(sample_project, write_outputs=False)
    for h in logger.handlers:
        h.flush()
    text = log_file.read_text(encoding="utf-8")
    assert f"run_id={run_id}" in text
    for stage in ("stage=ingest", "stage=validate", "stage=clean", "duration_s="):
        assert stage in text
    if handler is not None:
        logger.removeHandler(handler)
        handler.close()
