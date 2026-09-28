# 4. Functional Requirements

The assignment requires at least three major functional modules. CreaseIQ has five (M1–M5), with 22 functional requirements. Their IDs are cited in code docstrings and tests, and the full trace is in `docs/rubric_traceability.md`.

{{ tab("Functional requirements with priority, implementation and verifying tests") }}

| ID | Module | Requirement | Pri. | Implementation | Test |
|---|---|---|---|---|---|
| FR-01 | M1 | Ingest CSV; schema and type enforcement; quarantine bad rows with reasons | P0 | `data/source.py`, `ingest.py`, `schema.py` | `test_ingest.py` |
| FR-02 | M1 | Clean and canonicalise teams, venues, cities, seasons; derive batting order, stage, champion, D/L, era | P0 | `data/cleaning.py`, `canonical.py` | `test_cleaning.py`, `test_canonical.py` |
| FR-03 | M1 | Data-quality report (MD + JSON) and data dictionary | P0 | `data/quality_report.py` | `test_quality_report.py` |
| FR-04 | M1 | Normalised SQLite store and Parquet cache; idempotent rebuild | P0 | `db/models.py`, `loader.py`, `repository.py` | `test_db.py` |
| FR-05 | M1 | Validated CSV append (dry run, dedup, size and type limits) | P1 | `services/ingest_service.py` | `test_services.py` |
| FR-06 | M2 | Team records, titles, season form, head-to-head, rating timeline | P0 | `analytics/team_stats.py` | `test_analytics.py` |
| FR-07 | M2 | Venue analytics with shrinkage; toss habits; clustering | P0 | `analytics/venue_stats.py`, `venue_clusters.py` | `test_analytics.py` |
| FR-08 | M2 | Toss analysis with hypothesis tests and CIs; era comparison | P0 | `analytics/toss_analysis.py`, `hypothesis_tests.py` | `test_hypothesis_tests.py` |
| FR-09 | M2 | Scoring and margin trends; closest finishes | P1 | `analytics/season_trends.py` | `test_analytics.py` |
| FR-10 | M2 | Player-of-the-match leaderboard; appearances; squad continuity | P1 | `analytics/player_stats.py` | `test_analytics.py` |
| FR-11 | M2 | Interactive filters and sanitised CSV export | P0 | `services/analytics_service.py`, app page 1 | `test_services.py`, `test_app.py` |
| FR-12 | M3 | Leakage-safe feature builder with an `as_of` contract | P0 | `features/builder.py` (+ 4 state modules) | `test_leakage.py` |
| FR-13 | M3 | Margin-aware Elo with season carry-over and history | P0 | `features/elo.py`, `models/elo_tuning.py` | `test_features.py` |
| FR-14 | M3 | ≥ 4 model families and ≥ 4 baselines under walk-forward validation | P0 | `models/train.py`, `baselines.py`, `splits.py` | `test_models.py` |
| FR-15 | M3 | Calibration and evaluation report with CIs and a reliability diagram | P0 | `models/evaluate.py`, `calibrate.py` | `test_models.py` |
| FR-16 | M3 | Predict via CLI, API and UI; two tiers; explanation | P0 | `models/predict.py`, `explain.py`, `services/prediction_service.py` | `test_experiment.py`, `test_services.py` |
| FR-17 | M3 | First-innings score regressor vs baselines | P1 | `models/score_regressor.py` | `test_experiment.py` |
| FR-18 | M3 | Model registry with SHA-256, params, data hash and commit | P0 | `models/registry.py` | `test_models.py` |
| FR-19 | M4 | What-if: toss, venue, opponent → Δ probability | P1 | `simulation/what_if.py`, `services/scenario_service.py` | `test_services.py` |
| FR-20 | M4 | Monte Carlo season simulation | P2 | `simulation/season_monte_carlo.py` | `test_services.py` |
| FR-21 | M5 | Structured logging, prediction log, PSI drift monitor | P0 | `logging_setup.py`, `db` `prediction_log`, `reporting/drift.py` | `test_core.py`, `test_figures_logging.py` |
| FR-22 | M5 | Generated model card and report assets | P0 | `reporting/model_card.py`, `figures.py`, `assets.py` | `test_experiment.py` |

## 4.1 Input / output structure of each module
{{ tab("Module inputs and outputs") }}

| Module | Input | Output |
|---|---|---|
| M1 Data engineering | `data/raw/ipl_matches.csv` (+ appended uploads), `configs/*.yaml`, `data/external/*.csv` | `matches.parquet`, `match_players.parquet`, SQLite DB, `quarantine.csv`, quality report, data dictionary |
| M2 Analytics | Canonical match table, filter values | DataFrames, Plotly charts, `reports/analytics.json`, `docs/analytics_findings.md`, safe CSV |
| M3 Prediction | Canonical matches + squads; config (seeds, grids, splits) | `reports/metrics.json`, registered models, figures, model card; at serving time: probability, drivers, log row |
| M4 Scenarios | A fixture (teams, venue, date, optional toss) | What-if table (Δ probability), title/top-4 odds |
| M5 Ops & reporting | Pipeline events, predictions, feature frame | Log file, `prediction_log` table, PSI table, NFR evidence, this report |

## 4.2 User workflow
A user opens the dashboard, sees KPIs and data and model status on Home, and then follows one of three paths (workflow diagram D3, Section 7.2):

- **Explore:** filter, inspect and export.
- **Predict:** choose two teams and a venue (all preselected), optionally add the toss, and click *Predict*. That is at most three clicks.
- **Maintain:** upload, dry run, then apply.
