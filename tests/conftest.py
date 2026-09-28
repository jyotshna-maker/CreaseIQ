"""Shared fixtures. The real dataset is small (1,243 rows), so session fixtures build it once."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from creaseiq.config import Settings, load_settings
from creaseiq.data.canonical import CanonicalMaps, load_canonical_maps
from creaseiq.data.pipeline import DataPipelineResult, run_data_pipeline
from creaseiq.data.source import CsvMatchSource
from creaseiq.utils import sha256_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings(ROOT)


@pytest.fixture(scope="session")
def maps(settings: Settings) -> CanonicalMaps:
    return load_canonical_maps(settings)


@pytest.fixture(scope="session")
def raw_df(settings: Settings) -> pd.DataFrame:
    return CsvMatchSource(settings.path("raw_csv")).load()


@pytest.fixture(scope="session")
def pipeline(settings: Settings) -> DataPipelineResult:
    return run_data_pipeline(settings, write_outputs=False)


@pytest.fixture(scope="session")
def matches(pipeline: DataPipelineResult) -> pd.DataFrame:
    return pipeline.clean.matches


@pytest.fixture()
def sample_raw() -> pd.DataFrame:
    return CsvMatchSource(FIXTURES / "sample_60.csv").load()


def make_project(tmp: Path, raw_csv: Path) -> Settings:
    """Create an isolated project root (configs + external data + a raw CSV) under ``tmp``."""
    shutil.copytree(ROOT / "configs", tmp / "configs")
    shutil.copytree(ROOT / "data" / "external", tmp / "data" / "external")
    (tmp / "data" / "raw").mkdir(parents=True)
    shutil.copy(raw_csv, tmp / "data" / "raw" / "ipl_matches.csv")
    (tmp / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    cfg_path = tmp / "configs" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["paths"]["raw_sha256"] = sha256_file(tmp / "data" / "raw" / "ipl_matches.csv")
    cfg["database"]["url"] = "sqlite:///data/creaseiq.db"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return load_settings(tmp)


@pytest.fixture()
def sample_project(tmp_path: Path) -> Settings:
    """Isolated project whose raw CSV is the 60-row fixture."""
    return make_project(tmp_path, FIXTURES / "sample_60.csv")


@pytest.fixture(scope="session")
def full_project(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Isolated project with the real CSV (outputs never touch the repository)."""
    return make_project(tmp_path_factory.mktemp("full"), ROOT / "data" / "raw" / "ipl_matches.csv")
