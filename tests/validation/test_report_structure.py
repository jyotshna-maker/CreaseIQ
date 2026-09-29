"""The PDF report has the 15 required sections in order, captions and figures, and no unrendered
template markers (PLAN §11; assignment PDF §6)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfReader

from creaseiq.config import load_settings
from creaseiq.reporting.report_builder import (
    REQUIRED_HEADINGS,
    _fix_lists,
    check_references,
    load_context,
    render_html,
)
from tests.conftest import ROOT

PDF = ROOT / "report" / "CreaseIQ_Project_Report.pdf"


@pytest.fixture(scope="module")
def pdf_text() -> str:
    if not PDF.exists():
        pytest.skip("Report not built yet (run `creaseiq report`).")
    raw = "\n".join(p.extract_text() for p in PdfReader(str(PDF)).pages)
    return raw.replace("\xa0", " ")


def test_fifteen_sections_in_order(pdf_text: str) -> None:
    assert re.search(r"(?:1\s*·\s*Cover Page|PROJECT REPORT)", pdf_text)
    toc = pdf_text.split("Contents", 1)[1][:1500]
    body_positions = []
    for i, heading in enumerate(REQUIRED_HEADINGS, 1):
        pattern = rf"(?:^|\n){i}\.\s*{re.escape(heading)}\s*\n"
        assert re.search(pattern, toc), f"TOC missing {heading}"
        if i > 1:
            matches = list(re.finditer(pattern, pdf_text))
            assert len(matches) >= 2, (
                f"section heading missing: {heading}"
            )  # TOC entry + body heading
            body_positions.append(matches[-1].start())
    assert body_positions == sorted(body_positions)


def test_page_count_and_captions(pdf_text: str) -> None:
    assert len(PdfReader(str(PDF)).pages) >= 30
    for caption in (
        "Use case diagram",
        "User workflow",
        "Sequence: serving one prediction",
        "Class diagram",
        "Component / package diagram",
        "Entity-relationship diagram",
        "System architecture",
    ):
        assert caption in pdf_text, caption
    assert len(re.findall(r"Figure \d+:", pdf_text)) >= 20


def test_no_unrendered_template_markers(pdf_text: str) -> None:
    assert "{{" not in pdf_text and "{%" not in pdf_text
    assert "nan%" not in pdf_text.lower()


def test_render_html_uses_generated_numbers() -> None:
    settings = load_settings(ROOT)
    ctx = load_context(settings, count_tests=False)
    html = render_html(settings, ctx)
    assert f"{ctx['m']['tiers']['post_toss']['holdout']['model']['log_loss']:.4f}" in html
    assert html.count("<figure>") >= 20


def test_fix_lists_and_link_check(tmp_path: Path) -> None:
    assert _fix_lists("Intro:\n- a\n- b") == "Intro:\n\n- a\n- b"
    assert _fix_lists("| t |\n- x") == "| t |\n- x"
    refs = tmp_path / "r.md"
    refs.write_text("no links here", encoding="utf-8")
    assert check_references(refs)["total"] == 0
