"""CLI commands on an isolated copy of the project with registered models (Typer CliRunner)."""

from __future__ import annotations

import shutil

import pandas as pd
import pytest
from typer.testing import CliRunner

from creaseiq import cli
from creaseiq.config import Settings, load_settings
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def served_project(full_project: Settings) -> Settings:
    shutil.copytree(ROOT / "models", full_project.root / "models", dirs_exist_ok=True)
    (full_project.root / "reports").mkdir(exist_ok=True)
    shutil.copy(ROOT / "reports" / "metrics.json", full_project.root / "reports" / "metrics.json")
    return load_settings(full_project.root)


@pytest.fixture()
def runner(served_project: Settings, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setattr(cli, "get_settings", lambda: served_project)
    return CliRunner()


def test_help_lists_all_commands(runner: CliRunner) -> None:
    out = runner.invoke(cli.app, ["--help"]).output
    for cmd in (
        "validate",
        "build-db",
        "analyze",
        "features",
        "train",
        "evaluate",
        "predict",
        "whatif",
        "simulate",
        "ingest",
        "benchmark",
        "all",
    ):
        assert cmd in out


def test_predict(runner: CliRunner) -> None:
    res = runner.invoke(cli.app, ["predict", "mi", "csk", "--venue", "wankhede"])
    assert res.exit_code == 0, res.output
    assert "Mumbai Indians" in res.output and "%" in res.output
    res = runner.invoke(
        cli.app,
        [
            "predict",
            "mi",
            "csk",
            "--venue",
            "wankhede",
            "--toss-winner",
            "csk",
            "--toss-decision",
            "field",
        ],
    )
    assert res.exit_code == 0 and "post_toss" in res.output


def test_predict_invalid_input_exit_code(runner: CliRunner) -> None:
    res = runner.invoke(cli.app, ["predict", "mi", "mi", "--venue", "wankhede"])
    assert res.exit_code == 1 and "Error:" in res.output and "Traceback" not in res.output
    res = runner.invoke(cli.app, ["predict", "mi", "csk", "--venue", "atlantis"])
    assert res.exit_code == 1


def test_whatif_simulate_evaluate(runner: CliRunner) -> None:
    res = runner.invoke(cli.app, ["whatif", "rcb", "gt", "--venue", "narendra_modi"])
    assert res.exit_code == 0 and "baseline" in res.output
    res = runner.invoke(cli.app, ["simulate", "--n-sims", "300"])
    assert res.exit_code == 0 and "title" in res.output
    res = runner.invoke(cli.app, ["evaluate"])
    assert res.exit_code == 0 and "Holdout" in res.output


def test_ingest_dry_run(
    runner: CliRunner, served_project: Settings, raw_df: pd.DataFrame, tmp_path
) -> None:
    path = tmp_path / "dups.csv"
    raw_df.head(2).to_csv(path, index=False)
    res = runner.invoke(cli.app, ["ingest", "--append", str(path)])
    assert res.exit_code == 0 and "duplicates 2" in res.output
    res = runner.invoke(cli.app, ["ingest", "--append", str(tmp_path / "missing.csv")])
    assert res.exit_code == 1


def test_benchmark_without_pages(runner: CliRunner, served_project: Settings) -> None:
    res = runner.invoke(cli.app, ["benchmark", "--no-pages"])
    assert res.exit_code == 0, res.output
    assert "pipeline_s" in res.output and (served_project.root / "reports" / "perf.json").is_file()


def test_evaluate_without_metrics(
    full_project: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    empty = load_settings(full_project.root)
    data = {**empty.data, "paths": {**empty.data["paths"], "reports_dir": str(tmp_path / "none")}}
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(empty.root, data))
    res = CliRunner().invoke(cli.app, ["evaluate"])
    assert res.exit_code == 1 and "train" in res.output
