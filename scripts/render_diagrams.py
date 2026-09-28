"""Render docs/diagrams/*.mmd to SVG and high-resolution PNG with mermaid-cli (cross-platform).

Usage:  python scripts/render_diagrams.py
Needs Node.js >= 22.13; `npx` downloads @mermaid-js/mermaid-cli 12.0.0 on first run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "docs" / "diagrams"
CONFIG = DIAGRAMS / "mermaid-config.json"
MMDC = ["@mermaid-js/mermaid-cli@12.0.0"]


def main() -> int:
    npx = shutil.which("npx")
    if npx is None:
        print("npx not found: install Node.js >= 22.13")
        return 1
    failures = 0
    for src in sorted(DIAGRAMS.glob("*.mmd")):
        for ext, extra in (("svg", []), ("png", ["-s", "3", "-b", "white"])):
            out = src.with_suffix(f".{ext}")
            cmd = [npx, "--yes", *MMDC, "-i", str(src), "-o", str(out), "-c", str(CONFIG), *extra]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
            status = "ok" if res.returncode == 0 else "FAILED"
            failures += res.returncode != 0
            print(f"{status:6} {out.relative_to(ROOT)}")
            if res.returncode:
                print(res.stderr[-800:])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
