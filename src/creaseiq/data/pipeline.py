"""Data-layer orchestration: source → validate → clean → Parquet and quality report (M1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from creaseiq.config import Settings
from creaseiq.data.canonical import CanonicalMaps, load_canonical_maps
from creaseiq.data.cleaning import CleanResult, clean_matches, load_external_facts
from creaseiq.data.ingest import Mode, ValidationResult, validate_raw, write_quarantine
from creaseiq.data.quality_report import (
    build_quality_summary,
    render_data_dictionary,
    write_quality_outputs,
)
from creaseiq.data.source import CombinedCsvSource, CsvMatchSource, MatchSource
from creaseiq.logging_setup import get_logger, timed

logger = get_logger(__name__)

MATCHES_PARQUET = "matches.parquet"
PLAYERS_PARQUET = "match_players.parquet"


@dataclass
class DataPipelineResult:
    """Everything the data layer produced in one run."""

    raw: pd.DataFrame
    validation: ValidationResult
    clean: CleanResult
    maps: CanonicalMaps
    summary: dict[str, Any]
    fingerprint: str


def default_source(settings: Settings) -> MatchSource:
    """The hash-verified raw CSV plus any validated appended matches (FR-05)."""
    raw = CsvMatchSource(settings.path("raw_csv"), expected_sha256=settings.get("paths.raw_sha256"))
    return CombinedCsvSource(raw, settings.path("appended_csv"))


def run_data_pipeline(
    settings: Settings,
    source: MatchSource | None = None,
    mode: Mode = "lenient",
    write_outputs: bool = True,
) -> DataPipelineResult:
    """Run ingest → validate → clean, then write Parquet, quarantine and quality reports.

    Args:
        settings: Loaded settings.
        source: Match source (defaults to the configured raw CSV).
        mode: Validation mode.
        write_outputs: If False, compute only (used by tests).
    """
    src = source or default_source(settings)
    with timed(logger, "ingest", source=src.name) as ctx:
        raw = src.load()
        ctx["rows"] = len(raw)
    fingerprint = src.fingerprint()
    with timed(logger, "validate", mode=mode) as ctx:
        validation = validate_raw(raw, mode=mode)
        ctx["quarantined"] = validation.n_quarantined
    maps = load_canonical_maps(settings)
    facts = load_external_facts(
        settings.path("external_dir"), settings.get("data.voided_matches", [])
    )
    with timed(logger, "clean") as ctx:
        clean = clean_matches(validation.valid, maps, facts)
        ctx["rows"] = len(clean.matches)
    summary = build_quality_summary(raw, validation, clean, fingerprint)
    if write_outputs:
        write_data_outputs(settings, validation, clean, summary)
    return DataPipelineResult(raw, validation, clean, maps, summary, fingerprint)


def write_data_outputs(
    settings: Settings, validation: ValidationResult, clean: CleanResult, summary: dict[str, Any]
) -> None:
    """Persist processed tables, quarantine and the generated docs."""
    processed = settings.path("processed_dir")
    processed.mkdir(parents=True, exist_ok=True)
    clean.matches.to_parquet(processed / MATCHES_PARQUET, index=False)
    clean.players.to_parquet(processed / PLAYERS_PARQUET, index=False)
    write_quarantine(validation, settings.path("interim_dir") / "quarantine.csv")
    docs = settings.path("docs_dir")
    write_quality_outputs(
        summary, docs / "data_quality_report.md", settings.path("reports_dir") / "data_quality.json"
    )
    (docs / "data_dictionary.md").write_text(
        render_data_dictionary(clean.matches, clean.players), encoding="utf-8"
    )


def load_processed(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the processed Parquet cache, building it first if absent."""
    processed: Path = settings.path("processed_dir")
    mpath, ppath = processed / MATCHES_PARQUET, processed / PLAYERS_PARQUET
    if not (mpath.exists() and ppath.exists()):
        run_data_pipeline(settings)
    return pd.read_parquet(mpath), pd.read_parquet(ppath)
