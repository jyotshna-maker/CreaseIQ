# 6. System Architecture

To avoid tight coupling between user interface logic and mathematical calculations, CreaseIQ adopts a **strict downward-dependency layered architecture**. High-level presentation components (such as our Streamlit web interface and Typer command-line entry points) never touch database drivers or raw machine-learning algorithms directly. Instead, they interact exclusively with an intermediate services layer that coordinates domain modules: analytics routines, feature builders, probabilistic models, simulation engines, and reporting generators. In turn, domain modules rely on low-level data access packages for schema ingestion, anomaly filtering, and database access, supported by foundational utilities for logging, configuration, and exception types.

{{ fig("docs/diagrams/D1_architecture.png", "System architecture (D1): layers, stores and CI") }}

{{ tab("Layers and responsibilities") }}

| Layer | Packages | Responsibility |
|---|---|---|
| 4 Presentation | `app`, `cli` | Widgets and commands, rendering, friendly errors |
| 3 Services | `services` | Use cases: validate, orchestrate, log, time |
| 2 Domain | `analytics`, `features`, `models`, `simulation`, `reporting`, `viz` | Statistics, feature engineering, machine learning, simulation, figures |
| 1 Data access | `data`, `db` | Sources, schema, cleaning, canonical maps, ORM, repositories |
| 0 Core | `config`, `logging_setup`, `exceptions`, `utils` | Cross-cutting concerns |

**Enforcement mechanisms:** Architectural boundaries often erode without automated enforcement. We protect this layering using an `import-linter` contract within continuous integration alongside an explicit AST inspection test (`tests/unit/test_architecture.py`). If a low-level data module attempts to import from an analytical or presentation layer, the build fails immediately. This separation yields three concrete engineering benefits:

- Core business logic and inference pipelines remain completely agnostic of whether they are invoked from a web browser or a headless terminal.
- Mathematical and statistical calculations can be unit-tested thoroughly without instantiating UI runtimes or spinning up browser drivers.
- Introducing an alternate front-end (such as a future FastAPI web service) requires adding a layer-4 adapter without modifying underlying domain services.

**Persistence design and artifacts:**

- **Immutable raw scorecards:** The original CSV matches file is kept unchanged, with SHA-256 fingerprint verification on startup.
- **Audited domain ground truth:** Structured external records documenting super-over winners and Duckworth-Lewis revisions alongside citation sources.
- **Declarative YAML mappings:** Centralized rule sets handling franchise lineage history, stadium aliases, and designated home grounds.
- **Optimized Parquet stores:** Intermediate columnar storage for rapid feature engineering.
- **Relational database:** Third-normal-form SQLite repository, fully compatible with PostgreSQL via URL configuration.
- **Cryptographic model registry:** Serialized joblib artifacts paired with manifest hashes, hyperparameters, and dataset versions.
- **Operational telemetry:** Run-scoped structured logs and dynamic evaluation metrics.

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
