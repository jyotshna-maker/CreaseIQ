"""`creaseiq build-db` and `creaseiq analyze` on an isolated full-data project."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from creaseiq import cli
from creaseiq.analytics.summary import build_analytics_summary, render_findings_markdown
from creaseiq.config import Settings
from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.utils import read_json


def test_findings_markdown(pipeline: DataPipelineResult) -> None:
    text = render_findings_markdown(
        build_analytics_summary(pipeline.clean.matches, pipeline.clean.players)
    )
    for section in (
        "Winning the toss",
        "Batting second",
        "Home advantage",
        "Impact Player era",
        "Teams and venues",
    ):
        assert section in text
    assert "not** a causal effect" in text


def test_build_db_and_analyze(full_project: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: full_project)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["build-db"])
    assert result.exit_code == 0, result.output
    assert "match" in result.output and "1243" in result.output
    assert (full_project.root / "data" / "creaseiq.db").is_file()
    result = runner.invoke(cli.app, ["analyze"])
    assert result.exit_code == 0, result.output
    summary = read_json(full_project.root / "reports" / "analytics.json")
    assert summary["toss"]["overall"]["n"] == 1218
    assert (full_project.root / "docs" / "analytics_findings.md").is_file()
