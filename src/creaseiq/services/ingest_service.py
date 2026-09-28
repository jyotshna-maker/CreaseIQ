"""Validated CSV upload / append of new matches (FR-05, NFR-03).

The raw file is immutable, so accepted rows go to a separate **appended** file that every
pipeline run reads after the raw CSV (``CombinedCsvSource``). The flow:

1. Guard the upload: ``.csv`` only, at most 5 MB, decodable UTF-8, and the exact raw column set.
2. Validate the new rows **strictly** (a single bad row rejects the whole upload).
3. Drop duplicates of existing matches (natural key: date, team1, team2).
4. Dry-run clean the combined data (canonical names, validity windows, stages...).
5. Unless this is a dry run, write the appended file atomically, rebuild the processed cache
   and reload the database in one transaction. On failure the appended file is restored.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from creaseiq.config import Settings
from creaseiq.data.canonical import load_canonical_maps
from creaseiq.data.cleaning import clean_matches, load_external_facts
from creaseiq.data.ingest import validate_raw
from creaseiq.data.pipeline import default_source, run_data_pipeline
from creaseiq.db.loader import load_database
from creaseiq.db.session import make_engine
from creaseiq.exceptions import DataValidationError, InputError
from creaseiq.logging_setup import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class UploadReport:
    """Outcome of an upload attempt."""

    rows_received: int
    rows_new: int
    rows_duplicate: int
    applied: bool
    messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form."""
        return dict(self.__dict__)


def read_upload(content: bytes, filename: str, max_bytes: int) -> pd.DataFrame:
    """Parse uploaded bytes after the type and size guards."""
    if not filename.lower().endswith(".csv"):
        raise InputError("Only .csv files can be uploaded.")
    if len(content) > max_bytes:
        raise InputError(f"File is {len(content):,} bytes; the limit is {max_bytes:,} bytes.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("The file is not valid UTF-8 text.") from exc
    try:
        return pd.read_csv(io.StringIO(text), dtype=str)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError(f"Could not parse the CSV: {exc}") from exc


def _natural_key(df: pd.DataFrame) -> pd.Series:
    return df["date"].astype(str) + "|" + df["team1"].astype(str) + "|" + df["team2"].astype(str)


def process_upload(
    settings: Settings, content: bytes, filename: str, dry_run: bool = True
) -> UploadReport:
    """Validate, deduplicate and (unless ``dry_run``) append uploaded matches.

    Raises:
        InputError: Wrong type, size, encoding or unparseable CSV.
        DataValidationError: Rows fail the schema/rules or cannot be canonicalised.
    """
    max_bytes = int(settings.get("data.upload_max_bytes", 5_000_000))
    upload = read_upload(content, filename, max_bytes)
    validate_raw(upload, mode="strict")  # all-or-nothing
    existing = default_source(settings).load()
    keys = _natural_key(upload)
    dup = keys.isin(set(_natural_key(existing))) | keys.duplicated()
    new = upload[~dup.to_numpy()]
    report = UploadReport(len(upload), len(new), int(dup.sum()), applied=False)
    if new.empty:
        report.messages.append("Nothing new: every row already exists.")
        return report
    combined = pd.concat([existing, new], ignore_index=True)
    facts = load_external_facts(
        settings.path("external_dir"), settings.get("data.voided_matches", [])
    )
    clean_matches(validate_raw(combined, "strict").valid, load_canonical_maps(settings), facts)
    report.messages.append(f"{len(new)} new match(es) validated and canonicalised successfully.")
    if dry_run:
        report.messages.append("Dry run: nothing was written.")
        return report

    app_path = settings.path("appended_csv")
    previous = app_path.read_bytes() if app_path.exists() else None
    appended_all = (
        pd.concat([pd.read_csv(app_path, dtype=str), new]) if previous is not None else new
    )
    app_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = app_path.with_suffix(".tmp")
    appended_all.to_csv(tmp, index=False)
    os.replace(tmp, app_path)  # atomic replace on the same filesystem
    try:
        result = run_data_pipeline(settings)
        if result.validation.n_quarantined:
            raise DataValidationError("Combined data produced quarantined rows; upload rejected.")
        load_database(
            make_engine(settings.db_url), result.clean.matches, result.clean.players, result.maps
        )
    except Exception:
        if previous is None:
            app_path.unlink(missing_ok=True)
        else:
            app_path.write_bytes(previous)
        run_data_pipeline(settings)  # restore the processed cache to the previous state
        raise
    report.applied = True
    report.messages.append("Appended; processed cache and database rebuilt.")
    log_event(logger, "upload_applied", rows=len(new))
    return report
