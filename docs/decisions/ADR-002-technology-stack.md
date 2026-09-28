# ADR-002: Technology stack and Python version

- **Status:** Accepted, 2026-09-28
- **Context:** The plan targets Python 3.11+ on macOS (M2) and Windows, using mainstream pip-installable libraries only and no GPU. Research R6 checked the latest stable releases on PyPI on 2026-09-28. numpy 2.5.3, scipy 1.18.1 and xgboost 3.4.1 all require Python ≥ 3.12. The development machine is Windows 11 running Python 3.12.10.

## Options

- **Python version**
  - (a) Keep 3.11 and pin older numpy and scipy.
  - (b) Move to ≥ 3.12.
- **Gradient boosting**
  - (a) xgboost or lightgbm. Both need `libomp` on macOS.
  - (b) scikit-learn `HistGradientBoostingClassifier`.
- **HTML to PDF**
  - (a) WeasyPrint. It needs the MSYS2 Pango libraries on Windows.
  - (b) Playwright Chromium `page.pdf()`.

## Decision

- **Python:** `requires-python >= 3.12`. CI runs 3.12 and 3.13 on Ubuntu, Windows and macOS. Pinning old numpy would cost security fixes, and Python 3.11 is security-only anyway.
- **Libraries**, pinned exactly in `requirements*.txt`: pandas 3.0.6, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0, scikit-learn 1.9.1, SQLAlchemy 2.1.1, pandera 0.33.1 (imported as `pandera.pandas`), Typer 0.27.2, Rich 15.0.0, Streamlit 1.64.0 (multipage `pages/` directory, `AppTest`), Plotly 7.1.0, PyYAML, Jinja2, joblib, pyarrow.
- **Models:** scikit-learn only. HistGradientBoosting covers the boosting family, so we avoid native OpenMP installation problems.
- **Report and screenshots:** Playwright Chromium, a pip install plus `playwright install chromium`, identical on all three operating systems.
- **Diagrams:** Mermaid sources rendered with `@mermaid-js/mermaid-cli` 12. Node 24 is installed locally; the CLI requires ≥ 22.13.
- **Storage:** SQLite through the SQLAlchemy 2 ORM. Switching to Postgres is a config change (NFR-08).

## Consequences

- pandas 3 turns on Copy-on-Write and the Arrow-backed `str` dtype by default. Code must not rely on chained assignment, and tests run on pandas 3.
- SQLAlchemy 2.1.1 was only three days old when pinned. If it causes a regression, fall back to 2.0.x and record it here.
- Pinned versions are refreshed only with a passing CI run and a CHANGELOG entry.
