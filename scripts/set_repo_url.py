"""Point README badges and the report cover at the real GitHub repository.

Usage (after `gh repo create`):  python scripts/set_repo_url.py <github-owner> [repo-name]
Then run `creaseiq report` to rebuild the PDF with the new URL.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if not argv or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", argv[0]):
        print("usage: python scripts/set_repo_url.py <github-owner> [repo-name]")
        return 2
    owner = argv[0]
    repo = argv[1] if len(argv) > 1 else "creaseiq"
    url = f"https://github.com/{owner}/{repo}"
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"https://github\.com/[^/\s)]+/creaseiq", url, text)
    readme.write_text(text, encoding="utf-8")
    cfg = ROOT / "report" / "report_config.yaml"
    lines = [f'repository_url: "{url}"' if ln.startswith("repository_url:") else ln for ln in cfg.read_text(encoding="utf-8").splitlines()]
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Repository URL set to {url}. Now run: creaseiq report")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
