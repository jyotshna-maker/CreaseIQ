"""Ingestion and validation (FR-01).

``validate_raw`` has two modes:

* ``strict``: any violation raises :class:`DataValidationError` with the offending row indices.
* ``lenient``: violating rows are removed and returned in a quarantine frame, each with a
  ``reason`` naming the failed checks. Everything else is kept.

Column-level problems (missing or unexpected columns) always raise: no row-level fix exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd
import pandera.errors as pa_errors

from creaseiq.data.schema import RAW_COLUMNS, RAW_SCHEMA, ROW_RULES
from creaseiq.exceptions import DataValidationError
from creaseiq.logging_setup import get_logger, log_event

Mode = Literal["strict", "lenient"]
logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Output of :func:`validate_raw`."""

    valid: pd.DataFrame
    quarantine: pd.DataFrame
    reasons: dict[int, list[str]] = field(default_factory=dict)

    @property
    def n_quarantined(self) -> int:
        """Number of quarantined rows."""
        return len(self.quarantine)


def _check_columns(df: pd.DataFrame) -> None:
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in RAW_COLUMNS]
    if missing or extra:
        raise DataValidationError(f"Column mismatch. Missing: {missing}; unexpected: {extra}")


def _schema_failures(df: pd.DataFrame) -> dict[int, list[str]]:
    """Run the pandera schema lazily and return {row_index: [reasons]}."""
    reasons: dict[int, list[str]] = {}
    try:
        RAW_SCHEMA.validate(df, lazy=True)
    except pa_errors.SchemaErrors as exc:
        cases = exc.failure_cases
        for _, case in cases.iterrows():
            idx = case.get("index")
            if idx is None or pd.isna(idx):
                raise DataValidationError(
                    f"Schema failure without row index: {case.get('check')} on {case.get('column')}"
                ) from exc
            reasons.setdefault(int(idx), []).append(f"schema:{case['column']}:{case['check']}")
    return reasons


def validate_raw(df: pd.DataFrame, mode: Mode = "lenient") -> ValidationResult:
    """Validate a raw match frame against the schema and the row rules.

    Args:
        df: Raw frame, as returned by a :class:`~creaseiq.data.source.MatchSource`.
        mode: ``"strict"`` or ``"lenient"``.

    Returns:
        ValidationResult with typed valid rows and the quarantined rows plus reasons.

    Raises:
        DataValidationError: Column mismatch (both modes) or any violation (strict mode).
    """
    _check_columns(df)
    df = df.reset_index(drop=True)
    reasons = _schema_failures(df)

    # Row rules need typed columns. Coerce only the rows that passed the schema.
    candidate = df.drop(index=list(reasons))
    typed = RAW_SCHEMA.validate(candidate) if len(candidate) else candidate
    for rule in ROW_RULES:
        mask = rule.violations(typed).fillna(True).astype(bool)
        for idx in typed.index[mask]:
            reasons.setdefault(int(idx), []).append(f"rule:{rule.name}")

    bad = sorted(reasons)
    if bad and mode == "strict":
        raise DataValidationError(
            f"{len(bad)} row(s) failed validation (first: {reasons[bad[0]]})", bad
        )
    quarantine = df.loc[bad].copy()
    quarantine["reason"] = ["; ".join(reasons[i]) for i in bad]
    valid = typed.drop(index=[i for i in bad if i in typed.index])
    log_event(
        logger, "validate", rows_in=len(df), rows_valid=len(valid), quarantined=len(bad), mode=mode
    )
    return ValidationResult(valid=valid, quarantine=quarantine, reasons=reasons)


def write_quarantine(result: ValidationResult, path: Path) -> None:
    """Persist quarantined rows (with reasons) for review."""
    path.parent.mkdir(parents=True, exist_ok=True)
    result.quarantine.to_csv(path, index=False)
