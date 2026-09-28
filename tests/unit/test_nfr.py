"""NFR evidence summary (reporting/nfr.py)."""

from __future__ import annotations

from pathlib import Path

from creaseiq.reporting.nfr import build_nfr_summary, core_coverage, render_nfr_markdown
from creaseiq.utils import write_json
from tests.conftest import ROOT


def test_summary_from_real_reports() -> None:
    s = build_nfr_summary(ROOT / "reports")
    ids = [r["id"] for r in s["rows"]]
    assert ids[:2] == ["NFR-01", "NFR-02"] and "NFR-07" in ids
    md = render_nfr_markdown(s)
    assert md.count("| NFR-") == len(s["rows"])


def test_summary_without_evidence(tmp_path: Path) -> None:
    s = build_nfr_summary(tmp_path)
    assert {r["id"] for r in s["rows"]} == {"NFR-02", "NFR-04", "NFR-06", "NFR-07"}
    assert "Measured on" not in render_nfr_markdown(s)


def test_core_coverage_math(tmp_path: Path) -> None:
    cov = {
        "files": {
            "src/creaseiq/data/a.py": {"summary": {"num_statements": 10, "missing_lines": 1}},
            "src\\creaseiq\\models\\b.py": {"summary": {"num_statements": 20, "missing_lines": 0}},
        },
        "totals": {"percent_covered": 96.7},
    }
    write_json(tmp_path / "c.json", cov)
    cc = core_coverage(cov)
    assert cc["data"] == 90.0 and cc["models"] == 100.0 and cc["total"] == 96.7
    assert cc["features"] != cc["features"]  # nan when a package has no files
