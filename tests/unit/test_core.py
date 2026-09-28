"""Tests for config, exceptions, logging and utils (NFR-02, NFR-06, NFR-07)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from creaseiq import __version__
from creaseiq.cli import app
from creaseiq.config import Settings, find_project_root, load_settings, load_yaml
from creaseiq.exceptions import (
    ConfigError,
    CreaseIQError,
    DataValidationError,
    FeatureLeakageError,
    InputError,
    ModelIntegrityError,
)
from creaseiq.logging_setup import KeyValueFormatter, log_event, new_run_id, timed
from creaseiq.utils import read_json, seed_everything, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[2]


def test_project_root_found() -> None:
    assert find_project_root() == ROOT


def test_settings_resolve_paths_and_keys() -> None:
    s = load_settings(ROOT)
    assert s.seed == 42
    assert s.path("raw_csv") == ROOT / "data" / "raw" / "ipl_matches.csv"
    assert s.get("features.elo.initial") == 1500
    assert s.get("does.not.exist", "x") == "x"
    with pytest.raises(ConfigError):
        s.require("does.not.exist")


def test_raw_csv_hash_matches_config() -> None:
    s = load_settings(ROOT)
    assert sha256_file(s.path("raw_csv")) == s.require("paths.raw_sha256")


def test_db_url_anchored_at_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREASEIQ_DB_URL", raising=False)
    s = load_settings(ROOT)
    assert s.db_url.startswith("sqlite:///")
    assert s.db_url.endswith("data/creaseiq.db")
    assert Path(s.db_url.removeprefix("sqlite:///")).is_absolute()
    monkeypatch.setenv("CREASEIQ_DB_URL", "sqlite:///:memory:")
    assert s.db_url == "sqlite:///:memory:"


def test_env_log_level_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREASEIQ_LOG_LEVEL", "debug")
    assert load_settings(ROOT).log_level == "DEBUG"


def test_load_yaml_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_yaml(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_yaml(bad)
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("just a string", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_yaml(scalar)


def test_settings_is_immutable() -> None:
    s = Settings(root=ROOT, data={"project": {"seed": 1}})
    with pytest.raises(AttributeError):
        s.root = Path(".")  # type: ignore[misc]


@pytest.mark.parametrize(
    "exc", [ConfigError, DataValidationError, FeatureLeakageError, ModelIntegrityError, InputError]
)
def test_exception_hierarchy(exc: type[CreaseIQError]) -> None:
    assert issubclass(exc, CreaseIQError)


def test_data_validation_error_carries_rows() -> None:
    err = DataValidationError("bad rows", [3, 5])
    assert err.row_indices == [3, 5]
    assert DataValidationError("x").row_indices == []


def test_key_value_log_format() -> None:
    run_id = new_run_id()
    record = logging.LogRecord("creaseiq.test", logging.INFO, __file__, 1, "ingest", None, None)
    record.kv = {"event": "ingest", "rows": 1243, "note": "has space"}
    line = KeyValueFormatter().format(record)
    assert f"run_id={run_id}" in line
    assert "rows=1243" in line
    assert 'note="has space"' in line
    assert "level=INFO" in line


def test_timed_logs_duration(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("creaseiq.test_timed")
    logger.propagate = True
    with caplog.at_level(logging.INFO, logger="creaseiq.test_timed"):
        with timed(logger, "unit") as extra:
            extra["rows"] = 7
        log_event(logger, "custom", value=1)
    events = [getattr(r, "kv", {}).get("event") for r in caplog.records]
    assert events == ["stage_start", "stage_done", "custom"]
    assert caplog.records[1].kv["rows"] == 7
    assert caplog.records[1].kv["duration_s"] >= 0


def test_timed_logs_failure(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("creaseiq.test_timed_fail")
    logger.propagate = True
    with (
        caplog.at_level(logging.INFO, logger="creaseiq.test_timed_fail"),
        pytest.raises(ValueError),
        timed(logger, "boom"),
    ):
        raise ValueError("x")
    assert caplog.records[-1].kv["event"] == "stage_failed"


def test_seed_everything_is_deterministic() -> None:
    a = seed_everything(7).random(3)
    b = seed_everything(7).random(3)
    assert np.array_equal(a, b)


def test_json_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "out" / "x.json"
    write_json(p, {"b": np.float64(1.5), "a": np.int64(2), "c": np.array([1, 2]), "d": tmp_path})
    data = read_json(p)
    assert data["a"] == 2 and data["b"] == 1.5 and data["c"] == [1, 2]
    assert list(data) == ["a", "b", "c", "d"]


def test_cli_version_and_info() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0 and __version__ in result.output
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0 and "ipl_matches.csv" in result.output
