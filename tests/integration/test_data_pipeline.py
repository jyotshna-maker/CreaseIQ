"""Data pipeline end to end on an isolated project (FR-01..FR-03)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from creaseiq import cli
from creaseiq.config import Settings
from creaseiq.data.pipeline import load_processed, run_data_pipeline


def test_pipeline_writes_all_outputs(sample_project: Settings) -> None:
    result = run_data_pipeline(sample_project)
    root = sample_project.root
    for rel in (
        "data/processed/matches.parquet",
        "data/processed/match_players.parquet",
        "data/interim/quarantine.csv",
        "docs/data_quality_report.md",
        "docs/data_dictionary.md",
        "reports/data_quality.json",
    ):
        assert (root / rel).is_file(), rel
    matches, players = load_processed(sample_project)
    assert len(matches) == 60 == len(result.clean.matches)
    assert players["match_id"].nunique() == 60


def test_load_processed_builds_cache_on_demand(sample_project: Settings) -> None:
    matches, _ = load_processed(sample_project)
    assert len(matches) == 60


def test_pipeline_is_deterministic(sample_project: Settings) -> None:
    a = run_data_pipeline(sample_project, write_outputs=False).clean.matches
    b = run_data_pipeline(sample_project, write_outputs=False).clean.matches
    assert a.equals(b)


def test_cli_validate(sample_project: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: sample_project)
    result = CliRunner().invoke(cli.app, ["validate", "--strict"])
    assert result.exit_code == 0, result.output
    assert "60 matches" in result.output


def test_cli_reports_friendly_error(
    sample_project: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    (sample_project.root / "data" / "raw" / "ipl_matches.csv").write_text(
        "x\n1\n", encoding="utf-8"
    )
    monkeypatch.setattr(cli, "get_settings", lambda: sample_project)
    result = CliRunner().invoke(cli.app, ["validate"])
    assert result.exit_code == 1
    assert "Error:" in result.output and "Traceback" not in result.output
