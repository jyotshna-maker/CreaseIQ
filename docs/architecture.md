# Architecture

## 1. Style: layered, with dependencies pointing downward only

| Layer | Packages | Responsibility | May import |
|---|---|---|---|
| 4 Presentation | `app` (Streamlit), `cli` (Typer) | Input widgets and commands, rendering, friendly errors | everything below |
| 3 Services | `services` | Use cases: validate input, orchestrate, log, time | 2, 1, 0 |
| 2 Domain | `analytics`, `features`, `models`, `simulation`, `reporting`, `viz` | Statistics, feature engineering, ML, simulation, figures | siblings, 1, 0 |
| 1 Data access | `data`, `db` | Sources, validation, cleaning, canonical maps, ORM, repositories | 0 |
| 0 Core | `config`, `logging_setup`, `exceptions`, `utils` | Cross-cutting concerns | nothing internal |

The rule is enforced twice. The `import-linter` contract in `pyproject.toml` runs in CI, and `tests/unit/test_architecture.py` is an AST test that pytest runs.

Keeping the layering strict pays off in three ways:
- The dashboard and the CLI share one implementation of every use case.
- The domain code can be tested without Streamlit.
- A new front end, such as a REST API, would only need a new layer-4 module.

Diagrams:
- D1 system architecture: `diagrams/D1_architecture.png`
- D8 component/package: `diagrams/D8_components.png`
- D10 deployment: `diagrams/D10_deployment.png`

## 2. Data flow
D2 (`diagrams/D2_data_pipeline.png`) shows the end-to-end process that `creaseiq all` runs:

1. The immutable raw CSV is hash-checked.
2. It is validated. Invalid rows go to quarantine in lenient mode; strict mode raises.
3. It is cleaned against the YAML knowledge base and the verified external facts.
4. The clean data goes to the Parquet cache and the 3NF SQLite database.
5. Elo is tuned.
6. As-of features are built.
7. Model selection runs as walk-forward CV.
8. The selection is frozen and hashed.
9. The holdout is evaluated for the frozen selection only, and every evaluation is logged.
10. The selected configuration is refit and registered.
11. Predictions are served.

## 3. Key design patterns

| Pattern | Where | Why |
|---|---|---|
| Protocol / Strategy | `data/source.py` `MatchSource` (`CsvMatchSource`, `CombinedCsvSource`) | Future sources, such as Cricsheet JSON or an API, plug in without touching downstream code (NFR-08) |
| Repository | `db/repository.py` | All SQL in one place, parameterised (NFR-03) |
| Declarative knowledge base | `configs/*.yaml` + `data/canonical.py` | Identity rules live in data, not code; lookups fail loudly |
| Incremental state machine | `features/builder.py` `MatchState` | O(n) as-of features; date batches guarantee no look-ahead |
| Wrapper / Decorator | `models/train.py` `SymmetricModel` | Any sklearn estimator becomes orientation-invariant |
| Registry with integrity check | `models/registry.py` | Reproducible, tamper-evident model artifacts |
| Facade / service layer | `services/*` | One entry point per use case for both UIs |
| Context object | `services/context.py` `AppContext` | Lazily loaded, shared resources (data, DB, models) |

## 4. Storage
- **Files:**
  - `data/raw` is immutable.
  - `data/external` holds verified facts with sources.
  - `data/appended` holds validated uploads.
  - `data/processed` is a Parquet cache and can be rebuilt.
- **Relational:** SQLite (`data/creaseiq.db`) through the SQLAlchemy 2 ORM. The schema is in 3NF with FK, CHECK and UNIQUE constraints and two views (D9 `diagrams/D9_er.png`). Foreign keys are enforced with `PRAGMA foreign_keys=ON`. Changing `CREASEIQ_DB_URL` moves the store to PostgreSQL, and the dialect-aware upsert already supports it.
- **Artifacts:**
  - `models/registry.json` plus joblib bundles, with SHA-256 recorded.
  - `reports/*.json` and `reports/figures/*.png`, all generated.

## 5. Cross-cutting concerns
- **Errors (NFR-02):** everything inherits from `CreaseIQError`. The CLI's `_guard` turns expected errors into an exit code 1 and a one-line message. The dashboard's `friendly_errors()` context manager shows a message, never a stack trace.
- **Logging (NFR-07):** key=value lines with a per-run `run_id` and stage durations, sent to the console and a rotating file. Predictions are also written to the `prediction_log` table.
- **Security (NFR-03):**
  - Input validated against allow-lists.
  - Only parameterised SQL.
  - Model artifacts verified by hash before loading.
  - Uploads restricted to CSV of at most 5 MB and all-or-nothing.
  - CSV-injection escaping on export.
  - Secrets scan in tests.
- **Reproducibility (NFR-06):** a global seed, pinned dependencies, config-driven parameters and hash-seeded orientation. Tests check that two runs give identical metrics.

## 6. Why these technologies
Summarised from ADR-002:
- **scikit-learn only:** no native OpenMP dependencies.
- **Streamlit:** a Python-only UI that fits a data-science course.
- **SQLite:** zero administration, with Postgres one URL away.
- **Playwright:** the same Chromium renders on Windows and macOS for screenshots and the PDF.
- **Mermaid:** diagrams are kept as text, next to the code.
