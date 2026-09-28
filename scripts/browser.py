"""Locate a Chromium binary for Playwright (screenshots and PDF). See ``find_chromium``."""

from __future__ import annotations

from creaseiq.reporting.report_builder import find_chromium


def chromium_executable() -> str | None:
    """Path to a Chromium executable, or None to let Playwright use its bundled browser."""
    return find_chromium()
