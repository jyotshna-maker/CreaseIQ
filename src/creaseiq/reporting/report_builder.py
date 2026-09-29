"""Project report builder (PLAN §11): Markdown sections + Jinja2 → HTML → PDF (Chromium).

Every number in the report is a template variable bound to ``reports/*.json``. The
sections live in ``report/sections/NN_*.md``, and figures and tables are numbered
automatically.
"""

from __future__ import annotations

import os
import re

# subprocess is used only to count collected tests, with a fixed argv.
import subprocess  # nosec B404
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jinja2
import markdown
import yaml
from markupsafe import Markup, escape

from creaseiq.config import Settings
from creaseiq.reporting.nfr import build_nfr_summary, core_coverage
from creaseiq.utils import read_json

REQUIRED_HEADINGS = (
    "Cover Page", "Introduction", "Problem Statement", "Functional Requirements",
    "Non-functional Requirements", "System Architecture", "Design Diagrams",
    "Design Decisions & Rationale", "Implementation Details", "Screenshots / Results",
    "Testing Approach", "Challenges Faced", "Learnings & Key Takeaways",
    "Future Enhancements", "References",
)  # fmt: skip


def _trusted(html: str) -> Markup:
    """Mark HTML as safe.

    Used only for markup this module generates itself (captions are escaped first) and for
    the project's own CSS. User and data values are always autoescaped.
    """
    return Markup(html)  # noqa: S704  # nosec B704


class _Numbering:
    """Sequential figure/table numbering shared by all sections."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.fig = 0
        self.tab = 0

    def figure(self, rel_path: str, caption: str, width: str = "100%") -> Markup:
        self.fig += 1
        uri = (self.root / rel_path).resolve().as_uri()
        return _trusted(
            f'\n<figure><img src="{uri}" style="width:{width}" alt="{escape(caption)}"/><figcaption>Figure {self.fig}: {escape(caption)}</figcaption></figure>\n'
        )

    def table(self, caption: str) -> Markup:
        self.tab += 1
        return _trusted(f'\n<p class="tabcap">Table {self.tab}: {escape(caption)}</p>\n')


def _count_tests(root: Path) -> dict[str, int]:
    """Collected test counts per suite (via ``pytest --collect-only``)."""
    counts: dict[str, int] = {}
    for suite in ("unit", "integration", "validation"):
        # Fixed argv (this interpreter + pytest); no user input.
        res = subprocess.run(  # noqa: S603  # nosec B603
            [sys.executable, "-m", "pytest", "--collect-only", "-q", f"tests/{suite}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        counts[suite] = sum(1 for line in res.stdout.splitlines() if "::" in line)
    counts["total"] = sum(counts.values())
    return counts


URL_RE = re.compile(r"https?://[^\s)<>\"]+[^\s)<>\".,;]")


_UA = {"User-Agent": "Mozilla/5.0 (CreaseIQ reference check)"}


def check_references(references_md: Path, timeout: float = 15.0) -> dict[str, Any]:
    """HTTP-check every URL cited in the references section (PLAN §13: re-verify before report)."""
    urls = sorted(set(URL_RE.findall(references_md.read_text(encoding="utf-8"))))
    ok: list[str] = []
    failed: list[str] = []
    for url in urls:
        if not url.startswith("https://"):
            failed.append(url)
            continue
        # Only https URLs taken from our own references file are opened.
        req = urllib.request.Request(url, headers=_UA)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
                (ok if resp.status < 400 else failed).append(url)
        except (urllib.error.URLError, TimeoutError, ValueError):
            failed.append(url)
    return {"total": len(urls), "ok": len(ok), "failed": failed, "checked": urls}


def find_chromium() -> str | None:
    """Chromium for Playwright: ``$CREASEIQ_CHROMIUM``, else Puppeteer's Chrome, else system Chrome/Edge, else Playwright's own."""
    env = os.environ.get("CREASEIQ_CHROMIUM")
    if env:
        return env
    base = Path.home() / ".cache" / "puppeteer" / "chrome"
    names = {"chrome.exe", "chrome", "Google Chrome for Testing"}
    for c in sorted(base.glob("*/chrome-*/**/*"), reverse=True):
        if c.is_file() and c.name in names:
            return str(c)
    for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(p).is_file():
            return p
    return None


def load_context(settings: Settings, count_tests: bool = True) -> dict[str, Any]:
    """Everything the templates may reference."""
    root = settings.root
    reports = settings.path("reports_dir")
    meta = yaml.safe_load((root / "report" / "report_config.yaml").read_text(encoding="utf-8"))
    cov = read_json(reports / "coverage.json") if (reports / "coverage.json").exists() else None
    return {
        "meta": meta,
        "m": read_json(reports / "metrics.json"),
        "a": read_json(reports / "analytics.json"),
        "q": read_json(reports / "data_quality.json"),
        "p": read_json(reports / "perf.json"),
        "nfr": build_nfr_summary(reports),
        "cov": core_coverage(cov) if cov else {},
        "tests": _count_tests(root)
        if count_tests
        else {"unit": 0, "integration": 0, "validation": 0, "total": 0},
        "ledger": read_json(reports / "holdout_ledger.json")
        if (reports / "holdout_ledger.json").exists()
        else {},
        "refcheck": read_json(reports / "reference_check.json")
        if (reports / "reference_check.json").exists()
        else {"total": 0, "ok": 0, "failed": []},
    }


_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def _fix_lists(text: str) -> str:
    """Insert the blank line Python-Markdown needs before a list that follows a paragraph line."""
    out: list[str] = []
    for line in text.splitlines():
        if (
            _LIST_ITEM.match(line)
            and out
            and out[-1].strip()
            and not _LIST_ITEM.match(out[-1])
            and not out[-1].startswith((" ", "|", "<"))
        ):
            out.append("")
        out.append(line)
    return "\n".join(out)


def _env() -> jinja2.Environment:
    # Autoescape every value; only HTML this module generates itself is marked safe (Markup).
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=True)
    env.filters["pct"] = lambda x, nd=1: f"{100 * float(x):.{nd}f}%"
    env.filters["f"] = lambda x, nd=3: f"{float(x):.{nd}f}"
    env.filters["signed"] = lambda x, nd=4: f"{float(x):+.{nd}f}"
    env.filters["int"] = lambda x: f"{int(x):,}"
    env.filters["kv"] = lambda d: ", ".join(f"{k}={v}" for k, v in dict(d).items())
    return env


def render_html(settings: Settings, context: dict[str, Any]) -> str:
    """Render all sections into one HTML document."""
    root = settings.root
    report_dir = root / "report"
    env = _env()
    numbering = _Numbering(root)
    ctx = {**context, "fig": numbering.figure, "tab": numbering.table}
    body_parts = []
    toc = []
    for path in sorted((report_dir / "sections").glob("*.md")):
        text = env.from_string(path.read_text(encoding="utf-8")).render(**ctx)
        html = markdown.markdown(
            _fix_lists(text), extensions=["tables", "attr_list", "md_in_html", "sane_lists"]
        )
        body_parts.append(f'<section class="sec" id="{path.stem}">{html}</section>')
        first = next((ln for ln in text.splitlines() if ln.startswith("# ")), None)
        if first:
            toc.append(first[2:].strip())
    template = env.from_string((report_dir / "template.html").read_text(encoding="utf-8"))
    css = (report_dir / "styles.css").read_text(encoding="utf-8")
    return template.render(
        css=_trusted(css), body=_trusted("\n".join(body_parts)), toc=toc, **context
    )


def build_pdf(html_path: Path, pdf_path: Path, chromium: str | None = None) -> Path:
    """Print the HTML to an A4 PDF with Chromium (Playwright)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium)
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
            display_header_footer=False,
            outline=True,
            tagged=True,
        )
        browser.close()
    return pdf_path


def build_report(
    settings: Settings, chromium: str | None = None, count_tests: bool = True
) -> tuple[Path, Path]:
    """Render HTML and PDF into ``report/``; returns (html, pdf) paths."""
    report_dir = settings.root / "report"
    build = report_dir / "build"
    build.mkdir(parents=True, exist_ok=True)
    html = render_html(settings, load_context(settings, count_tests=count_tests))
    html_path = build / "CreaseIQ_Project_Report.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = report_dir / "CreaseIQ_Project_Report.pdf"
    build_pdf(html_path, pdf_path, chromium)
    return html_path, pdf_path
