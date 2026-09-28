"""Documentation deliverables exist and meet the assignment's content requirements (PDF §4–5)."""

from __future__ import annotations

import re

import pytest

from creaseiq.utils import read_json
from tests.conftest import ROOT

DOCS = ROOT / "docs"
DIAGRAMS = [
    "D1_architecture",
    "D2_data_pipeline",
    "D3_user_workflow",
    "D4_use_case",
    "D5_sequence_predict",
    "D6_sequence_train",
    "D7_class",
    "D8_components",
    "D9_er",
    "D10_deployment",
    "D12_model_lifecycle",
]


@pytest.mark.parametrize("name", DIAGRAMS)
def test_diagram_sources_and_renders_exist(name: str) -> None:
    for ext in ("mmd", "svg", "png"):
        path = DIAGRAMS_DIR / f"{name}.{ext}"
        assert path.is_file() and path.stat().st_size > 500, path


DIAGRAMS_DIR = DOCS / "diagrams"


def test_readme_has_required_sections() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in (
        "# CreaseIQ",
        "## Overview",
        "## Features",
        "## Technologies",
        "## Install & run",
        "## Testing",
        "## Screenshots",
        "## Data attribution",
        "## Disclaimer",
    ):
        assert heading in text, heading
    for img in re.findall(r"\]\((docs/[^)]+\.png)\)", text):
        assert (ROOT / img).is_file(), img
    assert "RESULTS:START" in text and "_Run `creaseiq report`" not in text  # results injected


def test_statement_has_required_sections() -> None:
    text = (ROOT / "statement.md").read_text(encoding="utf-8")
    for heading in (
        "## Problem statement",
        "## Scope",
        "## Target users",
        "## High-level features",
    ):
        assert heading in text


def test_design_docs_exist() -> None:
    for rel in (
        "architecture.md",
        "course_mapping.md",
        "rubric_traceability.md",
        "viva_prep.md",
        "data_dictionary.md",
        "data_quality_report.md",
        "model_card.md",
        "research_notes.md",
        "plan_review.md",
        "nfr_verification.md",
        "schema.sql",
        "analytics_findings.md",
    ):
        assert (DOCS / rel).is_file(), rel
    adrs = sorted((DOCS / "decisions").glob("ADR-*.md"))
    assert len(adrs) >= 6


def test_viva_prep_has_30_questions() -> None:
    text = (DOCS / "viva_prep.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\s*\d+\. \*", text, flags=re.MULTILINE)) >= 30


def test_screenshots_are_real_captures() -> None:
    shots = sorted((DOCS / "screenshots").glob("*.png"))
    assert len(shots) >= 7 and all(s.stat().st_size > 50_000 for s in shots)


def test_every_fr_is_traced() -> None:
    text = (DOCS / "rubric_traceability.md").read_text(encoding="utf-8")
    for i in range(1, 23):
        assert f"| FR-{i:02d} |" in text


def test_metrics_referenced_by_docs_exist() -> None:
    metrics = read_json(ROOT / "reports" / "metrics.json")
    assert set(metrics["tiers"]) == {"pre_toss", "post_toss"}
