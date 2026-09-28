"""Streamlit AppTest smoke tests for every dashboard page, including invalid input (NFR-02, NFR-04)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "src" / "creaseiq" / "app"
PAGES = [APP / "Home.py", *sorted((APP / "pages").glob("*.py"))]
pytestmark = pytest.mark.app


@pytest.fixture(autouse=True)
def _temp_db(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CREASEIQ_DB_URL", f"sqlite:///{(tmp_path_factory.getbasetemp() / 'app.db').as_posix()}"
    )


def _run(page: Path) -> AppTest:
    at = AppTest.from_file(str(page), default_timeout=180)
    at.run()
    return at


def _text(at: AppTest) -> str:
    parts = (
        [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    )
    return " ".join(str(p) for p in parts)


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_renders_without_errors(page: Path) -> None:
    at = _run(page)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert "Not betting" in _text(at)  # disclaimer on every page


def test_predict_page_happy_path() -> None:
    at = _run(APP / "pages" / "4_Predict_Match.py")
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert "%" in _text(at) and "Model" in _text(at)


def test_predict_page_same_team_shows_friendly_error() -> None:
    at = _run(APP / "pages" / "4_Predict_Match.py")
    at.selectbox[1].set_value(at.selectbox[0].value).run()
    at.button[0].click().run()
    assert not at.exception
    assert any("cannot play itself" in e.value for e in at.error)


def test_predict_page_post_toss() -> None:
    at = _run(APP / "pages" / "4_Predict_Match.py")
    at.checkbox[0].check().run()
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert "post-toss" in _text(at)


def test_what_if_page_runs() -> None:
    at = _run(APP / "pages" / "6_What_If.py")
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert len(at.dataframe) >= 1


def test_explorer_empty_state() -> None:
    at = _run(APP / "pages" / "1_Data_Explorer.py")
    at.sidebar.slider[0].set_value((2008, 2008)).run()
    at.sidebar.selectbox[0].set_value("Gujarat Titans").run()
    assert not at.exception
    assert any("No matches" in i.value for i in at.info)
