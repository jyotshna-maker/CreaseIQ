"""Quality report and data dictionary are generated from real outputs (FR-03)."""

from __future__ import annotations

from pathlib import Path

from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.data.quality_report import (
    render_data_dictionary,
    render_quality_markdown,
    write_quality_outputs,
)
from creaseiq.utils import read_json


def test_summary_numbers(pipeline: DataPipelineResult) -> None:
    s = pipeline.summary
    assert s["raw"]["rows"] == 1243 and s["raw"]["columns"] == 31
    assert s["validation"]["quarantined"] == 0
    assert s["results"]["decided"] == 1218
    assert s["identity"]["venues"] == 37
    assert s["fixes"]["tie_innings_corrected_super_over_removed"] == 16
    assert len(s["seasons"]) == 19


def test_markdown_and_json_written(pipeline: DataPipelineResult, tmp_path: Path) -> None:
    md, js = tmp_path / "q.md", tmp_path / "q.json"
    write_quality_outputs(pipeline.summary, md, js)
    text = md.read_text(encoding="utf-8")
    for heading in ("## Fixes applied", "## Seasons", "## Ties", "## D/L", "## Voided"):
        assert heading in text
    assert read_json(js)["results"]["matches"] == 1243
    assert render_quality_markdown(pipeline.summary).count("|") > 100


def test_data_dictionary_covers_every_column(pipeline: DataPipelineResult) -> None:
    text = render_data_dictionary(pipeline.clean.matches, pipeline.clean.players)
    for col in pipeline.clean.matches.columns:
        assert f"`{col}`" in text
