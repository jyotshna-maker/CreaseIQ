"""Structured logging (NFR-07).

Log lines are ``key=value`` pairs so they stay readable in a terminal and parse cleanly::

    ts=2026-09-28T10:00:00 level=INFO logger=creaseiq.data.ingest run_id=ab12 event=ingest rows=1243

Every pipeline run gets a ``run_id``. :func:`log_event` attaches it automatically, and
:func:`timed` records how long a stage takes.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_RUN_ID: ContextVar[str] = ContextVar("creaseiq_run_id", default="-")
_CONFIGURED_FLAG = "_creaseiq_configured"


def new_run_id() -> str:
    """Create and activate a short run id for the current pipeline run."""
    run_id = uuid.uuid4().hex[:12]
    _RUN_ID.set(run_id)
    return run_id


def current_run_id() -> str:
    """Return the active run id (``-`` if none)."""
    return _RUN_ID.get()


def _fmt_value(value: Any) -> str:
    text = str(value)
    if any(ch.isspace() for ch in text) or "=" in text or text == "":
        text = '"' + text.replace('"', "'") + '"'
    return text


class KeyValueFormatter(logging.Formatter):
    """Render records as ``key=value`` pairs, including any ``extra={"kv": {...}}`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Format one record."""
        parts = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "run_id": current_run_id(),
            "msg": record.getMessage(),
        }
        kv = getattr(record, "kv", None)
        if isinstance(kv, dict):
            parts.update({str(k): v for k, v in kv.items()})
        line = " ".join(f"{k}={_fmt_value(v)}" for k, v in parts.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _StderrHandler(logging.StreamHandler):
    """Console handler that looks up ``sys.stderr`` on every emit.

    A plain StreamHandler keeps the stream object it was created with. Test runners and
    Streamlit swap ``sys.stderr``, so a stale reference would write to a closed stream.
    """

    @property
    def stream(self) -> Any:
        return sys.stderr

    @stream.setter
    def stream(self, _value: Any) -> None:
        pass


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure the ``creaseiq`` logger once: console plus an optional rotating file.

    Args:
        level: Logging level name.
        log_file: Path of the rotating log file; ``None`` logs to the console only.
        max_bytes: Rotation threshold.
        backup_count: Number of rotated files kept.

    Returns:
        The configured package logger.
    """
    logger = logging.getLogger("creaseiq")
    logger.setLevel(level.upper())
    if getattr(logger, _CONFIGURED_FLAG, False):
        return logger
    formatter = KeyValueFormatter()
    console = _StderrHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.propagate = False
    setattr(logger, _CONFIGURED_FLAG, True)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of ``creaseiq``."""
    return logging.getLogger(name if name.startswith("creaseiq") else f"creaseiq.{name}")


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a structured event with arbitrary key/value fields."""
    logger.log(level, event, extra={"kv": {"event": event, **fields}})


@contextmanager
def timed(logger: logging.Logger, stage: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Time a pipeline stage and log ``stage_done`` with ``duration_s``.

    The yielded dict can be filled with extra metrics (e.g. row counts) by the caller.
    """
    extra: dict[str, Any] = {}
    start = time.perf_counter()
    log_event(logger, "stage_start", stage=stage, **fields)
    try:
        yield extra
    except Exception:
        log_event(logger, "stage_failed", logging.ERROR, stage=stage, **fields)
        raise
    duration = round(time.perf_counter() - start, 4)
    log_event(logger, "stage_done", stage=stage, duration_s=duration, **fields, **extra)
