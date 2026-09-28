# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-28
### Added
- Phase 0 research notes (R1–R11) with sources, confidence and the decisions each one drives.
- Plan review with 13 findings. ADR-001 (course relevance), ADR-002 (stack), ADR-003 (franchise continuity).
- Canonical venue map (60 → 37), franchise lineage (19 → 15) and home-ground configs.
- Verified external data: super-over winners for all 16 ties and the D/L match list.
- Project scaffold: src layout, pinned dependencies (Python ≥ 3.12), CI matrix, pre-commit.
- Core package: typed exception hierarchy, config loader, structured key=value logging with run ids, utilities, and a Typer CLI skeleton.
