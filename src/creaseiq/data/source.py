"""Match data sources (NFR-08: extensible ingestion).

The pipeline depends only on the :class:`MatchSource` protocol. Today there is one
implementation, :class:`CsvMatchSource`. A future source plugs in without touching
downstream code if it yields the same raw columns (``schema.RAW_COLUMNS``). Examples:

* ``CricsheetJsonSource``: read Cricsheet match JSON files and flatten the ``info``
  section, which is exactly how the current CSV was produced (research R5). Its
  ball-by-ball ``innings`` data would feed a separate deliveries table.
* ``ApiMatchSource``: pull recent fixtures and results from an HTTP API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd

from creaseiq.exceptions import DataValidationError, InputError
from creaseiq.utils import sha256_file


@runtime_checkable
class MatchSource(Protocol):
    """Anything that can produce a raw match DataFrame."""

    name: str

    def load(self) -> pd.DataFrame:
        """Return raw matches with the columns in ``schema.RAW_COLUMNS``."""
        ...

    def fingerprint(self) -> str:
        """Return a content hash that identifies this exact input (for provenance)."""
        ...


class CsvMatchSource:
    """Read matches from a CSV file, optionally verifying its SHA-256 first.

    Args:
        path: CSV location.
        expected_sha256: If given, a mismatch raises :class:`DataValidationError`.
        max_bytes: Optional size cap, for user uploads (NFR-03).
    """

    def __init__(
        self, path: Path, expected_sha256: str | None = None, max_bytes: int | None = None
    ) -> None:
        self.path = Path(path)
        self.expected_sha256 = expected_sha256
        self.max_bytes = max_bytes
        self.name = f"csv:{self.path.name}"

    def fingerprint(self) -> str:
        """SHA-256 of the file."""
        return sha256_file(self.path)

    def load(self) -> pd.DataFrame:
        """Load the CSV. Every column is read as text first; typing happens in validation.

        Raises:
            InputError: Missing file, wrong extension or oversize file.
            DataValidationError: Hash mismatch or unreadable CSV.
        """
        if not self.path.is_file():
            raise InputError(f"CSV not found: {self.path}")
        if self.path.suffix.lower() != ".csv":
            raise InputError(f"Only .csv files are accepted, got {self.path.suffix!r}")
        if self.max_bytes is not None and self.path.stat().st_size > self.max_bytes:
            raise InputError(
                f"File is {self.path.stat().st_size} bytes; the limit is {self.max_bytes}"
            )
        if self.expected_sha256 is not None:
            actual = self.fingerprint()
            if actual != self.expected_sha256:
                raise DataValidationError(
                    f"Raw CSV hash mismatch: expected {self.expected_sha256[:12]}..., "
                    f"got {actual[:12]}... The raw file must be immutable."
                )
        try:
            return pd.read_csv(self.path, dtype=str, keep_default_na=True)
        except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
            raise DataValidationError(f"Could not parse CSV {self.path.name}: {exc}") from exc
