# PROGRESS

Status format: phase · done · next · blockers.

## Phase status

| Phase | Tag | Status |
|---|---|---|
| 0 Research, review, scaffolding | v0.1.0 | ✅ done (CI is verified locally only until the first push) |
| 1 Data layer | v0.2.0 | ✅ done: 0 quarantined, 37 venues / 15 franchises, champions verified, 96% data coverage |
| 2 Database + analytics | v0.3.0 | ✅ done: idempotent DB (checksum test), analytics 1-10, findings generated, 96% coverage |
| 3 Features + Elo | v0.4.0 | next |
| 4 Modeling & evaluation | v0.5.0 | pending |
| 5 Services, CLI, app | v0.6.0 | pending |
| 6 Hardening | v0.7.0 | pending |
| 7 Documentation & diagrams | v0.8.0 | pending |
| 8 Report | v0.9.0 | pending |
| 9 Final QA & release | v1.0.0 | pending |

## Phase 0 checklist
- [x] Assignment PDF read. It has 7 pages and no course name; the student confirmed the course is Machine Learning.
- [x] Raw CSV copied and its SHA-256 recorded (`data/raw/README.md`, `configs/config.yaml`, checked by a test).
- [x] Git and the GitHub CLI installed (both were missing on the machine).
- [x] Research R1–R11 → `docs/research_notes.md`. Four parallel research subagents plus my own R1 work.
- [x] `docs/plan_review.md`: 13 findings; `PLAN.md` patched.
- [x] ADR-001 (course relevance), ADR-002 (stack), ADR-003 (franchise continuity).
- [x] Canonical configs: venues 60 → 37, teams 19 → 15, home grounds, neutral seasons.
- [x] Scaffold: pyproject, pinned requirements, CI, pre-commit, config, logging, exceptions, CLI skeleton, README skeleton, CHANGELOG.
- [x] Local gates: ruff, ruff format, mypy, import-linter, bandit and pytest are all green (19 tests).

## Next (Phase 1)
- pandera raw schema, strict and lenient validation modes, quarantine.
- `canonical.py` (fail-loud maps) and `cleaning.py`: derived columns, correcting ties with regulation scores, voided flag, `dls_flag`, stage by era, champion.
- Quality report (MD + JSON) and data dictionary.
- Validate champions against R10.

## Phase 1 notes
- The real CSV validates with 0 quarantined rows (strict mode passes). 4,547 fixes are counted in `docs/data_quality_report.md`.
- The D/L heuristic flags 14 rows, and every one in the years the external list covers is confirmed there. In total 19 rows are flagged (heuristic OR external).
- 2022 was added to the neutral seasons. Visakhapatnam in 2016 is home to three teams, and those flags cancel out in the home-difference feature.

## Phase 2 notes
- The DB loads 1,243 matches, 27,909 squad rows, 811 players and 152 officials in about 0.6 s. Rebuilding gives identical checksums.
- Findings (`docs/analytics_findings.md`):
  - Toss: no detectable causal effect (+1.6 pp, p = 0.29, CI 48.8–54.4%).
  - Chasing: a real advantage (54.7%, p = 0.001), with no change in the Impact Player era.
  - Home: 53.2%, borderline (p = 0.057).
  - Impact Player era: +27.1 first-innings runs (d = 0.82).
- The EDA notebook is committed in Phase 5, together with `viz.charts`.

## Blockers
- **GitHub push:** `gh` must be authenticated by the student (`gh auth login`). Work continues locally with full history until then.

## Challenges (feeds report §12)
1. **Toolchain gaps:** the development machine had no git or GitHub CLI; both were installed via winget before version control could start.
2. **Secret hygiene:** a GitHub token was pasted into the build plan. It was stripped before `PLAN.md` was committed, and authentication is delegated to `gh auth login`.
3. **The plan's Python target was stale:** current numpy and scipy dropped 3.11, so the floor moved to 3.12 (ADR-002).
4. **Super-over contamination:** all 16 tie rows add super-over runs and wickets to the innings totals. The "12 wickets" anomaly is 10 regulation wickets plus 2 in the super over, not a typo. This was found only by checking scorecards (R8).
5. **The D/L heuristic has low recall:** it finds 6 of 16 D/L results, so an externally sourced list is needed.
6. **A voided match looks like a washout:** 08-05-2025 was abandoned for security reasons and replayed elsewhere.
7. **Venue identity is subtle:** the same site was rebuilt (Motera), a new ground sits in the same district (Mullanpur vs Mohali), and naming rights changed (Sahara / MCA Pune).
8. **Research-tool reliability:** ESPNcricinfo blocks automated fetches, and the page summariser misreported some facts. The subagents fell back to raw Wikipedia wikitext, and one subagent's venue tally (40) disagreed with the mapping's own count (37). We trust the count derived from the mapping.
10. **Logging vs test runners:** a console log handler kept a reference to a stream that CliRunner had closed, and the second CLI test crashed. The fix is to resolve `sys.stderr` on every emit.
11. **pandas 3 defaults:** the Arrow-backed string dtype and Copy-on-Write needed explicit handling. For example, `np.select` with a `None` default was replaced.
9. **Baseline leakage in the plan:** the B1 prior of 54.7% was computed on data that includes the holdout seasons.
