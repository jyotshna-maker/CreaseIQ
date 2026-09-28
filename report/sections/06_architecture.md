# 6. System Architecture

CreaseIQ uses a **layered architecture in which dependencies point downward only**. The presentation layer (Streamlit dashboard and Typer CLI) calls a services layer. Services orchestrate the domain packages: analytics, features, models, simulation, reporting and visualisation. The domain packages sit on a data-access layer (sources, validation, cleaning, ORM, repositories), which in turn uses a small core of configuration, logging and exception utilities.

{{ fig("docs/diagrams/D1_architecture.png", "System architecture (D1): layers, stores and CI") }}

{{ tab("Layers and responsibilities") }}

| Layer | Packages | Responsibility |
|---|---|---|
| 4 Presentation | `app`, `cli` | Widgets and commands, rendering, friendly errors |
| 3 Services | `services` | Use cases: validate, orchestrate, log, time |
| 2 Domain | `analytics`, `features`, `models`, `simulation`, `reporting`, `viz` | Statistics, feature engineering, machine learning, simulation, figures |
| 1 Data access | `data`, `db` | Sources, schema, cleaning, canonical maps, ORM, repositories |
| 0 Core | `config`, `logging_setup`, `exceptions`, `utils` | Cross-cutting concerns |

**How the layering is enforced.** An `import-linter` contract runs in CI, and an AST test (`tests/unit/test_architecture.py`) fails if any module imports a higher layer. The benefits:

- The dashboard and the CLI share one implementation of every use case.
- Domain code is testable without the UI.
- A new front end (for example a REST API) would only add a layer-4 module.

**Data stores:**

- **Raw CSV.** Immutable; its SHA-256 is checked on every run.
- **Verified external facts.** Super-over winners and the D/L list, with their sources.
- **YAML knowledge base.** Franchise lineage, venues and home grounds.
- **Parquet cache.**
- **SQLite database.** Switchable to PostgreSQL by URL.
- **Hash-verified model registry.**
- **Generated reports and figures.**

{{ fig("docs/diagrams/D10_deployment.png", "Deployment and environment (D10)", "88%") }}

## 6.1 Technology stack
{{ tab("Technology choices") }}

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 / 3.13 | Current numpy and scipy require ≥ 3.12 (ADR-002) |
| Data | pandas 3, NumPy, pyarrow | Standard; columnar cache |
| Validation | pandera | Declarative schemas with lazy failure collection |
| Statistics | SciPy, statsmodels | Exact tests; cross-checked results |
| ML | scikit-learn | All model families without native OpenMP dependencies |
| Storage | SQLAlchemy 2 + SQLite | Zero administration; Postgres available by URL |
| UI | Streamlit + Plotly | Python-only interactive dashboard, testable with `AppTest` |
| CLI | Typer + Rich | Typed commands with `--help` |
| Quality | pytest, Hypothesis, ruff, mypy, import-linter, bandit, pip-audit | Automated gates in CI |
| Docs | Mermaid, matplotlib, Playwright/Chromium | Diagrams as code; the same renderer on all operating systems |
