"""Typed exception hierarchy for CreaseIQ (NFR-02).

Every error the application raises on purpose derives from :class:`CreaseIQError`, so the
CLI and the dashboard can catch one base class and show a friendly message instead of a
stack trace.
"""

from __future__ import annotations


class CreaseIQError(Exception):
    """Base class for all expected CreaseIQ failures."""


class ConfigError(CreaseIQError):
    """A configuration file is missing, malformed or inconsistent."""


class DataValidationError(CreaseIQError):
    """Input data violates the schema or a data-quality rule (FR-01).

    Attributes:
        row_indices: Offending row indices in the input frame, when known.
    """

    def __init__(self, message: str, row_indices: list[int] | None = None) -> None:
        super().__init__(message)
        self.row_indices: list[int] = list(row_indices or [])


class FeatureLeakageError(CreaseIQError):
    """A feature matrix contains a column that is not on the pre-match allow-list (FR-12)."""


class ModelIntegrityError(CreaseIQError):
    """A model artifact is missing or its SHA-256 does not match the registry (FR-18, NFR-03)."""


class InputError(CreaseIQError):
    """A user-supplied value (team, venue, date, file) failed allow-list validation (NFR-03)."""
