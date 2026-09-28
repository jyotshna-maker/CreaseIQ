# PROGRESS

Status format: phase · done · next · blockers.

## Phase status

| Phase | Tag | Status |
|---|---|---|
| 0 Research, review, scaffolding | v0.1.0 | ✅ done (CI is verified locally only until the first push) |
| 1 Data layer | v0.2.0 | ✅ done: 0 quarantined, 37 venues / 15 franchises, champions verified, 96% data coverage |
| 2 Database + analytics | v0.3.0 | ✅ done: idempotent DB (checksum test), analytics 1-10, findings generated, 96% coverage |
| 3 Features + Elo | v0.4.0 | ✅ done: leakage tests (5 kinds) pass, symmetry verified per feature, build 0.33 s |
| 4 Modeling & evaluation | v0.5.0 | ✅ done: metrics.json with CIs, model card, figures, registry; holdout reported honestly |
| 5 Services, CLI, app | v0.6.0 | ✅ done: 7 pages pass AppTest, 12 CLI commands, NFR-01 met (6.6 s / 8.8 ms / 0.51 s / 40 MB) |
| 6 Hardening | v0.7.0 | ✅ done: 8/8 NFRs verified with evidence (docs/nfr_verification.md), coverage 96.3%, bandit 0, pip-audit 0 |
| 7 Documentation & diagrams | v0.8.0 | ✅ done: D1–D12, 7 real screenshots, README/statement, architecture, course mapping, traceability, viva prep (40 Q&A) |
| 8 Report | v0.9.0 | ✅ done: 49-page PDF (15 sections in order, 26 figures, 23 tables), references verified (14/14) |
| 9 Final QA & release | v1.0.0 | ✅ done: independent review fixed; clean clone passes 393/393; checklist in docs/acceptance_checklist.md. Push is pending the student's `gh auth login`. |

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

## Phase 3 notes
- Univariate AUCs are weak, as expected: elo_diff 0.536 overall and 0.512 on 2023+. The best single features are xi_experience_diff and xi_potm_diff at 0.545. Several features invert on 2023+ (home_diff 0.473). The honest expectation is a modest gain over baselines at best.
- The per-season elo_diff AUC ranges from 0.41 (2022) to 0.68 (2014). Season-to-season variance is large, so walk-forward std must be reported.

## Phase 4 notes
- The tuned Elo parameters (K=5, home 75, regression 0.1, margin on) sit on the grid edge for K and home. Differences between candidates are about 0.001 log-loss, which is noise level.
- Selected models: pre-toss elo_logit (one-SE rule), post-toss logreg C=0.003, calibration none for both (time-ordered comparison).
- The walk-forward log-loss of the chosen models is below a coin flip. **On the 2025–26 holdout, neither tier beats the coin**, and the ledger shows one frozen selection per tier. The home side won only 40% in 2023 and in 2025, versus 53% historically, so the pre-2023 patterns broke down.
- Score regression: ridge holdout MAE of about 30 runs against 30.1 for the recent-league-mean baseline, a negligible gain. The venue-level baseline has a -22 run bias because it lags the Impact Player scoring jump.
- **Integrity disclosure:** an exploratory smoke run evaluated the holdout for the same frozen selection. Its ledger file was deleted before the official run, and this is disclosed in ADR-006. The results were identical.

## Phase 9 notes
- The independent review found no leakage or holdout misuse. Its formatting, wording and consistency findings were fixed.
- A clean clone first failed the raw-CSV hash check (line-ending conversion by Git for Windows). `.gitattributes` fixed it. A second clean clone then showed a wrapped-path CLI test failure, which was also fixed. The final clean clone passes all 393 tests.

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
12. **Slow feature builds:** in pandas 3, `itertuples` over roughly 950 date groups took 7 s per build, which made grid search and the leakage tests impractical. Profiling showed 117k indexer calls. Converting to plain records once cut this to 0.33 s.
13. **Weak signal:** pre-match features carry little signal, especially since 2023, when the Impact Player rule and auction churn arrived. This had to be reported honestly rather than tuned away.
14. **A holdout that is worse than a coin flip:** the tempting move was to re-tune until 2025–26 looked good. Instead the selection was frozen and hashed before evaluation, and the negative result is reported as a finding about regime change.
15. **A bug caught by tests:** the asset writer assumed `docs/` existed, which failed in an isolated project. A loop-variable shadowing bug in the registry code was caught by mypy.
16. **Appending future seasons:** alias validity windows ended in 2026, which would have rejected any 2027 upload. Current names are now open-ended. Appends go to a separate file, so the raw file stays immutable.
9. **Baseline leakage in the plan:** the B1 prior of 54.7% was computed on data that includes the holdout seasons.
