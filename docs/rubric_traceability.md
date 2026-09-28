# Rubric & requirements traceability

## A. Assignment checklist (BuildYourOwnProjectVITyarthi.pdf) → evidence

| PDF item | Evidence |
|---|---|
| Relevant to the course | `docs/course_mapping.md`, ADR-001, report §2 |
| ≥ 3 major functional modules | 5 modules, M1–M5 (`statement.md`, report §4) |
| Clear input/output structure | Module I/O table (report §4, §9); CLI `--help`; D2 pipeline |
| Logical user workflow | D3 user workflow; ≤ 3-click prediction |
| ≥ 4 non-functional requirements | 8 NFRs, each measured: `docs/nfr_verification.md`, report §5 |
| Architecture, correct concepts, modular code, docs and comments, validation and error handling, Git | `docs/architecture.md`; `src/creaseiq` (11 subpackages); docstrings with FR IDs; `exceptions.py`; git history (feature branches, tags) |
| 5–10+ modules/files, package structure, tests | 11 subpackages; 200+ tests in `tests/unit`, `integration` and `validation` |
| Problem statement, objectives, FR, NFR | `statement.md`, `PLAN.md` §3–4, report §3–5 |
| System architecture diagram | `docs/diagrams/D1_architecture.png` |
| Process flow / workflow diagram | `D2_data_pipeline.png`, `D3_user_workflow.png` |
| Use case diagram | `D4_use_case.png` |
| Class / component diagram | `D7_class.png`, `D8_components.png` |
| Sequence diagram | `D5_sequence_predict.png`, `D6_sequence_train.png` |
| ER diagram + schema | `D9_er.png`, `docs/schema.sql`, `src/creaseiq/db/models.py` |
| Dataset description | `docs/data_dictionary.md`, `docs/data_quality_report.md`, report §9.1 |
| Model selection rationale | ADR-006, report §9.4 |
| Evaluation methodology | ADR-006, `models/evaluate.py`, report §9.5 |
| README: title, overview, features, tech, install/run, testing, screenshots | `README.md` |
| statement.md: problem, scope, users, features | `statement.md` |
| Complete source, data, scripts, config | `src/`, `data/`, `scripts/`, `configs/` |
| PDF report with 15 sections | `report/CreaseIQ_Project_Report.pdf`, checked by `tests/validation/test_report_structure.py` |

## B. Rubric → evidence

| Criterion (weight) | Evidence |
|---|---|
| Problem understanding & requirements (10) | `statement.md`; FR-01…22 and NFR-01…08 with IDs cited in docstrings and tests; this matrix |
| Design & documentation (20) | D1–D12; ADR-001…006; architecture, data dictionary, quality report, model card, research notes, plan review, viva prep |
| Implementation quality (25) | Layered package (enforced); type hints (mypy clean); ruff clean; coverage in `reports/coverage.json` (see `docs/nfr_verification.md`); typed errors; CI matrix |
| Innovation, depth & complexity (15) | as-of engine with 5 leakage tests; hash-seeded orientation and exact antisymmetry; margin-aware tuned Elo; walk-forward + one-SE + time-ordered calibration + ledger-logged holdout; paired bootstrap and Diebold–Mariano; causal-vs-associational toss analysis with MDE; super-over and D/L data discoveries; k-means venues; what-if; Monte Carlo; PSI drift |
| GitHub & version control (10) | Conventional Commits on feature branches, `--no-ff` merges, tags v0.1.0…v1.0.0, `CHANGELOG.md`, CI workflow |
| Project report (20) | `report/CreaseIQ_Project_Report.pdf` (generated from `reports/*.json`, with real screenshots and figures) |

## C. Functional requirements → implementation → tests

| FR | Module | Priority | Implementation | Test |
|---|---|---|---|---|
| FR-01 | M1 | P0 | `data/source.py`, `data/ingest.py`, `data/schema.py` | `tests/unit/test_ingest.py` |
| FR-02 | M1 | P0 | `data/cleaning.py`, `data/canonical.py` | `tests/unit/test_cleaning.py`, `test_canonical.py` |
| FR-03 | M1 | P0 | `data/quality_report.py` | `tests/unit/test_quality_report.py` |
| FR-04 | M1 | P0 | `db/models.py`, `db/loader.py`, `db/repository.py` | `tests/unit/test_db.py` |
| FR-05 | M1 | P1 | `services/ingest_service.py`, `CombinedCsvSource` | `tests/unit/test_services.py::test_upload_flow` |
| FR-06 | M2 | P0 | `analytics/team_stats.py` | `tests/unit/test_analytics.py` |
| FR-07 | M2 | P0 | `analytics/venue_stats.py`, `venue_clusters.py` | `tests/unit/test_analytics.py` |
| FR-08 | M2 | P0 | `analytics/toss_analysis.py`, `hypothesis_tests.py` | `test_analytics.py`, `test_hypothesis_tests.py` |
| FR-09 | M2 | P1 | `analytics/season_trends.py` | `test_analytics.py::test_era_scoring` |
| FR-10 | M2 | P1 | `analytics/player_stats.py` | `test_analytics.py::test_player_stats` |
| FR-11 | M2 | P0 | `analytics/common.py`, `services/analytics_service.py`, `app/pages/1_Data_Explorer.py` | `test_services.py`, `test_app.py` |
| FR-12 | M3 | P0 | `features/builder.py` (+ form, H2H, venue, squad) | `tests/validation/test_leakage.py` |
| FR-13 | M3 | P0 | `features/elo.py`, `models/elo_tuning.py` | `tests/unit/test_features.py` |
| FR-14 | M3 | P0 | `models/train.py`, `models/baselines.py`, `models/splits.py` | `tests/unit/test_models.py` |
| FR-15 | M3 | P0 | `models/evaluate.py`, `models/calibrate.py` | `tests/unit/test_models.py` |
| FR-16 | M3 | P0 | `models/predict.py`, `models/explain.py`, `services/prediction_service.py` | `test_experiment.py::test_predictor_serves_symmetric_probabilities`, `test_services.py` |
| FR-17 | M3 | P1 | `models/score_regressor.py` | `test_experiment.py::test_reproducible_metrics` |
| FR-18 | M3 | P0 | `models/registry.py` | `test_models.py::test_registry_roundtrip_and_tamper_detection` |
| FR-19 | M4 | P1 | `simulation/what_if.py`, `services/scenario_service.py` | `test_services.py::test_what_if_and_simulation` |
| FR-20 | M4 | P2 | `simulation/season_monte_carlo.py` | `test_services.py::test_monte_carlo_logic` |
| FR-21 | M5 | P0 | `logging_setup.py`, `db` `prediction_log`, `reporting/drift.py` | `test_core.py`, `test_figures_logging.py` |
| FR-22 | M5 | P0 | `reporting/model_card.py`, `figures.py`, `assets.py`, `nfr.py` | `test_experiment.py::test_model_card_and_figures` |
