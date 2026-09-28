"""Capture real dashboard screenshots with Playwright (README and report, section 10).

Starts ``streamlit run`` headless on a free port, visits every page, drives the Predict and
What-If pages, and saves full-page PNGs to ``docs/screenshots/``.

Usage:  python scripts/capture_screenshots.py
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser import chromium_executable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
APP = ROOT / "src" / "creaseiq" / "app" / "Home.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait(url: str, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as r:  # noqa: S310 - localhost only
                if r.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise TimeoutError("Streamlit did not start")


def _settle(page: Page, extra: float = 2.5) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=120_000
    )
    time.sleep(extra)


def crop_trailing_blank(path: Path, margin: int = 40) -> None:
    """Trim the empty area below the last content row (the sidebar column is ignored)."""
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    arr = np.asarray(img).astype(int)
    main = arr[:, int(arr.shape[1] * 0.25) :, :]
    background = main[-1, -1, :]
    rows = np.where(np.abs(main - background).sum(axis=2).max(axis=1) > 30)[0]
    if len(rows):
        bottom = min(arr.shape[0], int(rows.max()) + margin)
        img.crop((0, 0, arr.shape[1], bottom)).save(path)


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    crop_trailing_blank(path)
    print("saved", name)


def main() -> int:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
            "--theme.base",
            "light",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait(url)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chromium_executable())
            page = browser.new_page(
                viewport={"width": 1440, "height": 1700}, device_scale_factor=1.25
            )
            for path, name in [
                ("", "01_home"),
                ("Data_Explorer", "02_data_explorer"),
                ("Team_Analytics", "03_team_analytics"),
                ("Venue_and_Toss", "04_venue_and_toss"),
                ("Model_Lab", "06_model_lab"),
            ]:
                page.goto(f"{url}/{path}")
                _settle(page, 4)
                _shot(page, name)
            page.goto(f"{url}/Predict_Match")
            _settle(page)
            page.get_by_role("button", name="Predict").click()
            _settle(page, 4)
            _shot(page, "05_predict_match")
            page.goto(f"{url}/What_If")
            _settle(page)
            page.get_by_role("button", name="Run what-if").click()
            _settle(page, 4)
            _shot(page, "07_what_if")
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
