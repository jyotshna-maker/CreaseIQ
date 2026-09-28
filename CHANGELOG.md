# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-09-29
### Added
- Modelling (FR-14..FR-18): Elo grid search, five model families, walk-forward CV, one-SE selection, time-ordered calibration, fold-trained baselines B0–B4, ablations, a one-shot holdout with a ledger, bootstrap CIs, paired bootstrap and Diebold–Mariano tests, and a too-good guard.
- Hash-verified model registry, a symmetric `Predictor` with plain-English drivers, and a first-innings score regressor.
- PSI drift monitor, generated model card and 10 report figures. `creaseiq train` and `creaseiq evaluate`.

## [0.4.0] - 2026-09-29
### Added
- Margin-aware Elo engine with season carry-over and an optional early-season K boost (FR-13).
- Form, head-to-head, venue and squad state components, plus an as-of `FeatureBuilder` with date-batch processing, hash-seeded orientation, a declared symmetry and a column allow-list (FR-12, ADR-005).
- Leakage test suite: future deletion and mutation, same day, label shuffle, allow-list, orientation signal.
- `creaseiq features`.

## [0.3.0] - 2026-09-29
### Added
- Normalized SQLite schema (3NF) with FK/CHECK/UNIQUE constraints and two views, an idempotent loader and a parameterised repository (FR-04).
- Analytics (FR-06..FR-10): a causal toss test with MDE, chasing advantage with an era z-test, a shrunk venue profile table, head-to-head records, home advantage, scoring trends, POTM leaderboards, squad continuity and an umpire table.
- Unsupervised k-means venue profiling (ADR-001).
- `creaseiq build-db` and `creaseiq analyze`, which generate `reports/analytics.json` and `docs/analytics_findings.md`.

## [0.2.0] - 2026-09-29
### Added
- Data layer (M1): pandera schema plus row rules, strict and lenient validation with quarantine, a hash-verified CSV source, fail-loud canonical maps and the cleaning pipeline (FR-01..FR-03).
- Corrections for tie rows (super-over runs removed), the voided-match flag, dls_flag, era-aware stages and derived champions (ADR-004).
- Generated data-quality report, data dictionary and `creaseiq validate`.

## [0.1.0] - 2026-09-28
### Added
- Phase 0 research notes (R1–R11) with sources, confidence and the decisions each one drives.
- Plan review with 13 findings. ADR-001 (course relevance), ADR-002 (stack), ADR-003 (franchise continuity).
- Canonical venue map (60 → 37), franchise lineage (19 → 15) and home-ground configs.
- Verified external data: super-over winners for all 16 ties and the D/L match list.
- Project scaffold: src layout, pinned dependencies (Python ≥ 3.12), CI matrix, pre-commit.
- Core package: typed exception hierarchy, config loader, structured key=value logging with run ids, utilities, and a Typer CLI skeleton.
