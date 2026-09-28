"""Locate a Chromium binary for Playwright (screenshots and PDF).

Order: ``$CREASEIQ_CHROMIUM`` → Playwright's own browser (``playwright install chromium``) →
the Chrome that mermaid-cli/Puppeteer already downloaded (avoids a second 150 MB download).
"""

from __future__ import annotations

import os
from pathlib import Path


def chromium_executable() -> str | None:
    """Path to a Chromium executable, or None to let Playwright use its bundled browser."""
    env = os.environ.get("CREASEIQ_CHROMIUM")
    if env:
        return env
    home = Path.home()
    candidates = sorted(
        (home / ".cache" / "puppeteer" / "chrome").glob("*/chrome-*/chrome*"), reverse=True
    )
    candidates += sorted(
        (home / ".cache" / "puppeteer" / "chrome").glob(
            "*/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        ),
        reverse=True,
    )
    for c in candidates:
        if c.is_file() and c.name in {"chrome.exe", "chrome", "Google Chrome for Testing"}:
            return str(c)
    return None
