# PROGRESS

Status format: phase · done · next · blockers.

## Phase status

| Phase | Tag | Status |
|---|---|---|
| 0 Research, review, scaffolding | v0.1.0 | in progress |
| 1 Data layer | v0.2.0 | pending |
| 2 Database + analytics | v0.3.0 | pending |
| 3 Features + Elo | v0.4.0 | pending |
| 4 Modeling & evaluation | v0.5.0 | pending |
| 5 Services, CLI, app | v0.6.0 | pending |
| 6 Hardening | v0.7.0 | pending |
| 7 Documentation & diagrams | v0.8.0 | pending |
| 8 Report | v0.9.0 | pending |
| 9 Final QA & release | v1.0.0 | pending |

## Phase 0 checklist
- [x] Assignment PDF read (7 pages; no course name inside; course confirmed by student: Machine Learning)
- [x] Raw CSV copied and SHA-256 recorded (`data/raw/README.md`)
- [x] Git + GitHub CLI installed (were missing on the machine)
- [ ] Research R1, R2, R5, R6, R10 (minimum), R3/R4/R7/R8/R9/R11 started
- [ ] `docs/research_notes.md`, `docs/plan_review.md` committed
- [ ] ADR-001 (course relevance/scope), ADR-002 (stack)
- [ ] Scaffold: pyproject, config, logging, exceptions, CI, pre-commit, README skeleton

## Blockers
- GitHub push: `gh` must be authenticated by the student (`gh auth login`). Work continues locally meanwhile.

## Challenges (feeds report §12)
1. **Toolchain gaps:** the dev machine had no git or GitHub CLI; installed via winget before any version control could start.
2. **Secret hygiene:** a GitHub token was pasted into the build plan; it was stripped before `PLAN.md` was committed, and auth is delegated to `gh auth login`.
