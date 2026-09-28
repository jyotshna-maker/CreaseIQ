# CreaseIQ — Build Plan for Claude Code (Opus 5.5)

> **COURSE_NAME:** Machine Learning (confirmed by the student on 2026-09-28)
> **Student:** Jyotshna Payasi · Reg. No. 26BCE10651 · Vellore Institute of Technology Bhopal
> **Target GitHub repo:** `creaseiq` (public) under the student's GitHub account
> **Plan date:** 2026-09-28 (all "latest version" questions must be answered by web research, not memory)
> **Credentials:** never stored in this repository. Authenticate with `gh auth login` on the local machine.

---

## 0. Pre-flight (human, 5 minutes) and launch prompt

1. `mkdir creaseiq && cd creaseiq && git init`
2. Copy the CSV to `data/raw/ipl_matches.csv` (rename it). Copy the assignment PDF to `docs/assignment/BuildYourOwnProjectVITyarthi.pdf`. Save this file as `PLAN.md` in the repo root.
3. Fill in `COURSE_NAME` above. Optional but strongly recommended: paste the official syllabus / unit list into `docs/assignment/syllabus.txt`.
4. Need on the machine: Python 3.11+, Node 18+ (Mermaid CLI), git, and `gh auth login` done (for repo creation + push).
5. Start Claude Code in the repo root, select Opus 5.5, paste the launch prompt below.

**Launch prompt (paste verbatim):**

~~~
You are the sole engineer on "CreaseIQ", a university project that will be graded against the rubric in docs/assignment/BuildYourOwnProjectVITyarthi.pdf.
Read PLAN.md completely, then read the PDF and the CSV header. PLAN.md is binding except where your research proves it wrong; record any deviation as an ADR in docs/decisions/.

Execution rules:
1. Start with Phase 0 (research + plan review). Do not write application code until docs/research_notes.md and docs/plan_review.md exist and are committed.
2. Work autonomously end to end. Do not ask me questions unless you are blocked on something only I can provide (credentials, push access). When ambiguous, choose a sensible default, state the assumption in an ADR, keep moving.
3. Maintain PROGRESS.md (checklist + phase status + real challenges hit) and CLAUDE.md (conventions) so work survives context compaction. Update PROGRESS.md at the end of every phase.
4. Commit early and often with Conventional Commits on feature branches, merge with --no-ff, tag milestones. Never one giant commit. Never force-push.
5. Never fabricate: every number in docs/report comes from code output (reports/metrics.json), every reference was actually opened, every screenshot is a real capture.
6. Use subagents (if available) for parallel research, test writing, and a final independent code/doc review.
7. Finish with the Final Acceptance Checklist (PLAN.md section 15) and report which items pass, with evidence paths.
~~~

---

## 1. Mission, constraints, working agreements

**Mission.** Build a complete, rubric-maximizing project around the uploaded IPL dataset: a reproducible data pipeline, a normalized SQLite store, an analytics layer, a leakage-safe ML win-probability engine, an interactive Streamlit dashboard + CLI, tests, CI, full design documentation, a GitHub repo (README.md, statement.md), and a detailed PDF report.

**Hard constraints from the assignment PDF (treat as pass/fail):**
- Project must be **relevant to the course** (irrelevant = 0 marks). See section 13, R1, and `docs/course_mapping.md`.
- **≥ 3 major functional modules**, clear input/output structure, logical user workflow.
- **≥ 4 non-functional requirements** (we specify 8, each measurable).
- **5–10+ meaningful modules/files**, proper package structure, tests, validation and error handling, Git usage.
- Design artefacts: problem statement, objectives, FR, NFR, architecture diagram, workflow diagram, UML (use case, class/component, sequence), ER diagram + schema (storage is used).
- ML-course extras: **dataset description, model selection rationale, evaluation methodology**.
- Repo: `README.md` (title, overview, features, tech, install/run, testing, screenshots), `statement.md` (problem statement, scope, target users, high-level features), complete source.
- PDF report with the **exact 15 sections** listed in section 11.
- Rubric weights: Requirements 10 · Design & Docs 20 · Implementation 25 · Innovation/Depth 15 · GitHub/VC 10 · Report 20.

**Working agreements.**
- Python **3.12+** (R6: numpy 2.5/scipy 1.18 require ≥3.12; ADR-002), macOS Apple Silicon primary, **must also run on Windows** (avoid bash-only tooling in the core path; CLI is the single cross-platform entrypoint, Makefile is a convenience wrapper).
- No GPU, no PyTorch. Keep dependencies mainstream and installable via `pip` on M2 and Windows.
- Every script/notebook deterministic: fixed seeds, config-driven, no hidden state.
- The raw CSV is **immutable**. Record its SHA-256 in `data/raw/README.md` and in every model run.
- Cricket betting disclaimer in README and app footer: educational analytics, not betting advice.
- Honesty over flash: pre-match T20 outcomes are intrinsically noisy. Expect modest accuracy (roughly mid-50s to low-60s % on a temporal holdout; verify in R3). **If holdout accuracy > ~68% or AUC > ~0.72, assume leakage and hunt for it before celebrating.** Grades reward rigor, not inflated numbers.

---

## 2. Ground truth about the dataset (profiled; re-verify in Phase 1)

File: 1,243 rows × 31 columns. Dates `dd-mm-yyyy`, 2008-04-18 → 2026-05-31 (IPL 2026 season is complete in the file). 19 season labels. **One row per match, no ball-by-ball.**

Columns: `event_name, season, match_number, date, city, venue, team1, team2, toss_winner, toss_decision, team1_runs, team1_wickets, team2_runs, team2_wickets, winner, result_type, win_by_runs, win_by_wickets, player_of_match, match_referee, umpire1, umpire2, tv_umpire, reserve_umpire, match_type, overs_limit, balls_per_over, gender, team_type, team1_players, team2_players`.

| # | Finding | Handling |
|---|---|---|
| 1 | **CRITICAL — `team1`/`team2` semantics drift.** From 2018 onward `team1` is *always* the team batting first (100% of matches, verified via toss). Before 2018 the order is ~random (batting-first = team1 in 43–63% of matches per year). | **Never use raw team1/team2 order as a feature or target orientation.** Derive `bat_first` from toss (`toss_winner` if `toss_decision=='bat'`, else the other team). Build the modeling table in a canonical, order-blind orientation (see section 7). Add a test proving orientation carries no signal. |
| 2 | `result_type`: 1,218 complete, 16 tie, 9 no result. `winner` is null for all 25 non-complete. Super-over winners for ties are **not recorded**. | Classification target uses the 1,218 decided matches only. Keep all 1,243 for analytics. R8: optionally source verified super-over winners into `data/external/super_over_winners.csv` (≥2 sources each) — otherwise document exclusion. |
| 3 | Constant columns: `event_name, match_type, overs_limit, balls_per_over, gender, team_type`. | Validate constant, drop from model tables, keep in raw. |
| 4 | Season labels are messy: `2007/08`(=2008), `2009` (South Africa), `2009/10`(=2010), `2020/21`(=2020, UAE), `2021`. | Derive `season_year` = year of the season's first match; unit-test the mapping. |
| 5 | Franchise renames/duplicate spellings: Delhi Daredevils→Delhi Capitals; Kings XI Punjab→Punjab Kings; Royal Challengers Bangalore→Bengaluru; `Rising Pune Supergiant` vs `Supergiants`. Also **distinct** franchises that must not be merged blindly: Deccan Chargers vs Sunrisers Hyderabad; Gujarat Lions vs Gujarat Titans; Pune Warriors; Kochi Tuskers Kerala. | `configs/team_lineage.yaml` (alias → franchise_id, valid_from/to). Franchise continuity choices go in an ADR after R2. |
| 6 | 60 raw venue strings for far fewer stadiums (e.g. `Wankhede Stadium` / `Wankhede Stadium, Mumbai`; `M Chinnaswamy`/`M.Chinnaswamy`; Feroz Shah Kotla → Arun Jaitley Stadium; Sardar Patel Stadium, Motera → Narendra Modi Stadium; multiple Mohali/Chandigarh/New Chandigarh variants; Sheikh Zayed vs Zayed Cricket Stadium). `city` has Bangalore/Bengaluru duplicates and 51 `Unknown` (all Dubai/Sharjah venues). | `configs/venue_canonical.yaml` built via research (R2); impute city/country from canonical venue; assert 0 unmapped venues. |
| 7 | `match_number` null for 74 rows = playoff matches (4 per season; 3 in 2008 and 2009). | Derive `stage` (league/qualifier/eliminator/final) by order within season; `champion` per season = winner of the season's last match; cross-check against sources (R10). |
| 8 | Player lists: 811 unique names in `INITIALS Surname` format; 11 players per side through 2022, **12 from 2023** (Impact Player era, ~97–99% of matches). Impact player not identifiable. | Normalize names; `impact_era` flag (season_year ≥ 2023). Squad features must tolerate 11 or 12. Name-alias check (R2). |
| 9 | Anomalies: one row with `team2_wickets = 12` (2017-04-29 Gujarat Lions v MI, no winner); no-result rows with tiny scores (e.g. 2, 25/2 with 0). Six decided matches are inconsistent with "winner bat-first ⇔ win_by_runs>0" — all pre-2017, likely Duckworth-Lewis outcomes. **[Revised after R8]** All 16 tie rows add super-over runs/wickets to the innings totals (the "12 wickets" = 10 + 2 super-over wickets); 08-05-2025 was voided and replayed. | Correct ties with regulation scores from `data/external/super_over_winners.csv` (ADR-004); `voided` flag; `dls_flag` = heuristic OR `data/external/dls_matches.csv`. Exclude no-result/voided run totals from scoring stats. See `docs/plan_review.md`. |
| 10 | Base rates (decided matches): **bat-first wins 45.3%** (chasing 54.7%); **toss winner wins 51.6%**; toss decision `field` 825 vs `bat` 418. | These are baselines B1/B2 in section 7 and headline EDA facts. |

`team1_players`/`team2_players` are the XIs of *that* match → known only at toss time (post-toss tier). `player_of_match`, runs, wickets, margins, `result_type` are **post-match** and forbidden as features.

---

## 3. Project definition

**Name:** CreaseIQ — IPL Match Intelligence Platform.

**Problem statement (refine, don't dilute).** IPL data is rich but scattered across inconsistent labels (renamed franchises, duplicated venues, era-dependent field semantics). Students, analysts and fans lack a clean, reproducible, validated dataset and a principled, honest way to quantify factors like toss, venue and team form — and ML "predictors" found online commonly leak post-match information or ignore time ordering. CreaseIQ delivers a validated data pipeline, statistically sound analytics, and a leakage-safe, calibrated pre-match win-probability engine with explanations.

**Objectives.**
1. Ingest, validate, clean and canonicalize the raw dataset with an auditable quality report.
2. Store it in a normalized relational schema with reproducible rebuilds.
3. Provide statistically sound analytics (toss, venue, team, era effects) with uncertainty.
4. Predict match outcomes with leakage-safe features, walk-forward validation, calibrated probabilities and explanations.
5. Offer an accessible dashboard and CLI, with logging, monitoring and full test coverage of the core.
6. Document everything to the assignment's artefact list and submit a rubric-mapped report.

**Scope in:** the uploaded dataset, pre-match win probability (two tiers), first-innings score regression, analytics, what-if scenarios, validated CSV upload for new matches.
**Scope out:** ball-by-ball/live in-match prediction, betting odds, player-level batting/bowling stats (not in the data), auth/multi-user accounts (single-user local app; state this in the report and explain why).

**Target users:** (a) students/analysts exploring IPL data, (b) cricket fans wanting evidence-based match previews, (c) maintainers/data engineers extending the pipeline.

---

## 4. Requirements

### 4.1 Functional (give these IDs in code docstrings, tests, docs, and the traceability matrix)

**Module M1 — Data Engineering**
- FR-01 Ingest CSV from configurable path with schema + dtype enforcement; bad rows quarantined with reasons.
- FR-02 Clean & canonicalize teams (lineage), venues, cities, seasons; derive `bat_first`, `chasing_team`, `stage`, `champion`, `dls_flag`, `impact_era`, normalized margins.
- FR-03 Emit a data-quality report (MD/HTML + JSON) counting every fix, plus a data dictionary.
- FR-04 Persist to normalized SQLite + Parquet cache; rebuild is idempotent.
- FR-05 Validated CSV upload/append of new matches (dry-run mode, dedup, size/type limits).

**Module M2 — Analytics & Visualization**
- FR-06 Team analytics: all-time and per-season win%, titles, head-to-head matrix, rating timeline.
- FR-07 Venue analytics: avg first-innings score, bat-first win%, shrinkage-adjusted estimates, toss-decision habits.
- FR-08 Toss analysis with hypothesis tests + confidence intervals; era comparison (pre/post Impact Player).
- FR-09 Scoring & margin trends; closest finishes; 200+ totals frequency.
- FR-10 Player-of-match leaderboards, appearances, squad continuity.
- FR-11 Interactive filters (season range, team, venue, stage) + sanitized CSV export.

**Module M3 — Prediction Engine**
- FR-12 Leakage-safe feature builder with an `as_of(date)` contract.
- FR-13 Elo rating engine (margin-aware, season carry-over) with full history exposed.
- FR-14 Train and compare ≥ 4 model families + ≥ 4 baselines under walk-forward validation; tune only on dev seasons.
- FR-15 Probability calibration + evaluation report (log-loss, Brier, accuracy, AUC, ECE, bootstrap CIs, reliability diagram).
- FR-16 Predict win probability via CLI, Python API and UI; two tiers (pre-toss, post-toss); per-prediction explanation.
- FR-17 First-innings score regressor (P1) with MAE/RMSE vs baselines.
- FR-18 Model registry with SHA-256, params, data hash, git commit; reproducible training.

**Module M4 — Scenarios**
- FR-19 What-if: change toss outcome/decision, venue, or opponent and show Δ win probability.
- FR-20 Season Monte Carlo simulation using model probabilities (P2).

**Module M5 — Ops & Reporting**
- FR-21 Structured logging, prediction log table, feature-drift monitor (PSI).
- FR-22 Auto-generated model card and report assets (`reports/metrics.json`, figures).

Priorities: **P0** = FR-01–04, 06–08, 11–16, 18, 21–22 · **P1** = FR-05, 09, 10, 17, 19 · **P2** = FR-20 and umpire/referee descriptive analytics.

### 4.2 Non-functional (each has a target and a verification method — put this table in the report)

| ID | Category | Requirement | Verified by |
|---|---|---|---|
| NFR-01 | Performance | Full pipeline (ingest → DB → features → train best model) ≤ 90 s on Apple M2; single prediction ≤ 200 ms warm; dashboard page render ≤ 2 s warm | `scripts/benchmark.py` → `reports/perf.json`; test asserts thresholds with generous CI margin |
| NFR-02 | Reliability & error handling | Typed exception hierarchy (`DataValidationError`, `FeatureLeakageError`, `ModelIntegrityError`, `InputError`); idempotent pipeline; UI shows friendly errors, never stack traces | Unit + app smoke tests with bad inputs |
| NFR-03 | Security | Allow-list input validation; parameterized SQL only; model artifacts SHA-256-verified before `joblib` load; upload = CSV only, size-capped, schema-validated; CSV-injection sanitization on export; no secrets in repo | `bandit`, `pip-audit` reports + dedicated security tests |
| NFR-04 | Usability | ≤ 3 clicks to a prediction; consistent colorblind-safe team palette with WCAG AA text contrast; tooltips; meaningful empty states; responsible-use disclaimer | Manual checklist + screenshots + AppTest |
| NFR-05 | Maintainability | Type hints on public APIs, Google-style docstrings, `ruff` check+format clean, `mypy` clean on core, layer import rules enforced, ≥ 85% coverage on `data/ features/ models/ analytics/` | CI + coverage report |
| NFR-06 | Reproducibility | Seeds fixed, deps pinned, config-driven; same inputs → identical metrics (tol 1e-9) | `tests/validation/test_repro.py` |
| NFR-07 | Logging & monitoring | Structured logs (console + rotating file), run_id per pipeline run, data-quality counters, timings, metrics; prediction log; PSI drift panel | Log-format test + Model Lab page |
| NFR-08 | Scalability & resource efficiency | SQLAlchemy backend switchable SQLite→Postgres via config; incremental O(n) feature state; `MatchSource` interface for future ball-by-ball ingestion; RAM < 1 GB; Parquet caching | Memory check in benchmark; interface test |

---

## 5. Architecture & repository layout

Layered architecture, dependencies point downward only (enforce with `import-linter` or an AST test):

```
app (Streamlit) / cli (Typer)
        ↓
services  (PredictionService, AnalyticsService, ScenarioService, ReportService)
        ↓
analytics | features | models | simulation | reporting
        ↓
data (ingest/clean/canonical) | db (SQLAlchemy repos)
        ↓
config | logging | exceptions | utils
```

```
creaseiq/
├── CLAUDE.md  PROGRESS.md  PLAN.md  README.md  statement.md  CHANGELOG.md  LICENSE
├── pyproject.toml  requirements.txt  requirements-dev.txt  Makefile
├── .github/workflows/ci.yml   .gitignore  .env.example  .pre-commit-config.yaml
├── configs/  config.yaml  team_lineage.yaml  venue_canonical.yaml  home_grounds.yaml
├── data/  raw/ipl_matches.csv  raw/README.md  interim/  processed/  external/
├── src/creaseiq/
│   ├── config.py  exceptions.py  logging_setup.py  cli.py  __main__.py
│   ├── data/       ingest.py schema.py cleaning.py canonical.py quality_report.py source.py
│   ├── db/         models.py session.py loader.py repository.py
│   ├── analytics/  team_stats.py venue_stats.py toss_analysis.py season_trends.py player_stats.py hypothesis_tests.py
│   ├── features/   elo.py form.py head_to_head.py venue_effects.py squad.py builder.py
│   ├── models/     splits.py baselines.py train.py evaluate.py calibrate.py explain.py registry.py predict.py score_regressor.py
│   ├── simulation/ what_if.py season_monte_carlo.py
│   ├── services/   prediction_service.py analytics_service.py scenario_service.py
│   ├── viz/        theme.py charts.py
│   ├── reporting/  model_card.py drift.py
│   └── app/        Home.py  pages/1_Data_Explorer.py 2_Team_Analytics.py 3_Venue_and_Toss.py 4_Predict_Match.py 5_Model_Lab.py 6_What_If.py  components.py
├── tests/  unit/  integration/  validation/  fixtures/ (60-row sample CSV + golden files)
├── notebooks/  01_eda.ipynb  02_modeling.ipynb   (thin, import from src, outputs cleared)
├── docs/  research_notes.md  plan_review.md  course_mapping.md  rubric_traceability.md
│         architecture.md  data_dictionary.md  data_quality_report.md  model_card.md  viva_prep.md
│         decisions/ADR-001….md   diagrams/*.mmd|*.puml + rendered .svg/.png   screenshots/   assignment/
├── models/  registry.json + artifacts   reports/  metrics.json perf.json coverage.json figures/
└── report/  build_report.py  sections/*.md  template.html  styles.css  CreaseIQ_Project_Report.pdf
```

Stack (verify current versions and Python 3.12/3.13 compatibility via research before pinning): pandas, numpy, scipy, statsmodels, scikit-learn (HistGradientBoosting default; XGBoost/LightGBM only if they install cleanly on M2 + Windows), SQLAlchemy 2.x, pandera (or pydantic), Typer + Rich, Streamlit, Plotly, PyYAML, Jinja2, joblib; dev: pytest, pytest-cov, hypothesis, ruff, mypy, bandit, pip-audit, import-linter, Playwright (screenshots + PDF), mermaid-cli (`npx @mermaid-js/mermaid-cli`), PlantUML or Graphviz for the use-case diagram.

---

## 6. Module specifications

### M1 — Data Engineering (`data/`, `db/`)
- **Input:** raw CSV path (config). **Output:** `data/processed/matches.parquet`, SQLite `data/creaseiq.db`, `docs/data_quality_report.md/.json`.
- `schema.py`: pandera schema for raw (types, ranges, allowed values, constants) and processed tables. Validation failures raise `DataValidationError` with row indices; `--strict/--lenient` modes; lenient quarantines to `data/interim/quarantine.csv` with `reason`.
- `canonical.py`: loads the YAML lineage/venue maps; **fails loudly on any unmapped team/venue**; unit tests for every alias.
- `cleaning.py` derived columns: `season_year`, `bat_first`, `chasing_team`, `bat_first_won`, `toss_winner_won`, `stage`, `is_final`, `champion`, `dls_flag`, `impact_era`, `winning_margin_type/value`, `first_innings_runs`, `second_innings_runs`, `n_players_t1/t2`. Every transformation appends to a `fixes` counter that feeds the quality report.
- `db/models.py`: schema in section 8. `loader.py` idempotent (upsert by natural key `(date, team1_id, team2_id)`); `repository.py` read API returning DataFrames; **no raw f-string SQL anywhere**.
- `source.py`: `MatchSource` protocol (CSV implementation now; docstring shows how Cricsheet ball-by-ball or an API would plug in).
- **Upload (FR-05):** validated append via CLI `creaseiq ingest --append new.csv --dry-run` and a Streamlit uploader (CSV only, ≤ 5 MB, schema-checked, dedup report, no partial writes — wrap in a transaction).

### M2 — Analytics & Visualization (`analytics/`, `viz/`, `app/`)
Analytics are **pure functions returning DataFrames** (unit-tested with golden files); `viz/charts.py` turns them into Plotly figures; pages only call services. Required outputs:
1. Toss: toss-winner win% (overall / by decision / by era / by venue); exact binomial test vs 50%; chi-square of decision × outcome; Wilson CIs; conclusion stated with the effect size, not just p-values.
2. Bat-first vs chase win% by venue and season; two-proportion z-test pre vs post Impact Player era (2023+).
3. Team table: matches, wins, win%, titles, best/worst seasons; season-by-season win% lines with era markers.
4. Head-to-head heatmap (min-meetings filter).
5. Scoring trends: mean/median first-innings score per season, 200+ frequency, distribution by era.
6. Venue profiles: matches, avg 1st-inn score (shrunk to global mean with prior strength `m`), bat-first win rate (shrunk), toss-decision share.
7. Margins: distributions; closest finishes; ties.
8. POTM leaderboards; appearances; squad continuity (Jaccard of consecutive XIs).
9. Home advantage (needs `home_grounds.yaml`, R2).
10. P2: umpire/referee descriptive table with an explicit "no causal claim" note.

Dashboard pages: Home (KPIs, data freshness, quality status) · Data Explorer · Team Analytics · Venue & Toss · Predict Match · Model Lab · What-If. Use `st.cache_data` / `st.cache_resource`; footer disclaimer; every chart has a caption stating what it shows and its sample size.

### M3 — Prediction Engine (`features/`, `models/`) — see section 7 for methodology
- `builder.FeatureBuilder.build(matches, tier)` returns features computed strictly **as of the day before each match**; internally keeps incremental state (Elo table, rolling windows, venue/H2H counters) updated in date order in daily batches (same-day double-headers must not see each other).
- `predict.py`: `PredictionService.predict(team_a, team_b, venue, date, stage, toss=None, xi=None)` → `{p_a, p_b, tier, top_drivers[], model_run_id, latency_ms}`; **symmetrized** (average of both orientations); validates inputs against allow-lists (`InputError`).
- `explain.py`: permutation importance (global) + per-prediction contributions (linear model coefficients × standardized values; SHAP optional if it installs cleanly). Show a plain-English top-3 driver sentence.
- `registry.py`: writes `models/registry.json` (run_id, timestamp, model, params, data_sha256, git_commit, metrics, artifact path, artifact SHA-256); load path verifies the hash → `ModelIntegrityError` on mismatch.
- `score_regressor.py` (P1): target = first-innings runs; features = venue mean (as-of, shrunk), batting team rolling runs, opposition rolling runs conceded, era, stage, toss; models: Ridge + HistGradientBoostingRegressor; baselines: venue mean, season mean.

### M4 — Scenarios (`simulation/`)
- `what_if.py`: takes a baseline scenario, applies overrides (toss winner/decision, venue, home/away), returns Δp and a tornado-style breakdown. UI page with sliders/selectors.
- `season_monte_carlo.py` (P2): simulate a round-robin-plus-playoffs season using model probabilities (10k sims, seeded), output title/top-4 odds; label clearly as hypothetical.

### M5 — Ops & Reporting (`reporting/`, `logging_setup.py`)
- Structured logging (key=value or JSON) to console + `logs/creaseiq.log` (rotating). Every CLI command and pipeline stage logs `run_id`, duration, row counts, fixes applied.
- `prediction_log` table records each prediction (inputs, proba, run_id, latency).
- `drift.py`: PSI per key feature between training window and latest season; flagged in Model Lab.
- `model_card.py`: generates `docs/model_card.md` from `reports/metrics.json` (intended use, data, splits, metrics with CIs, calibration, limitations, ethical notes).

### CLI (Typer)
`creaseiq ingest | validate | build-db | features | train | evaluate | predict | whatif | report | benchmark | all` and `python -m creaseiq`. `--help` text is part of the deliverable. Exit codes non-zero on failure.

---

## 7. ML methodology (the part graders with an ML syllabus will read closely)

**Tasks.** (T1) binary classification: does team A win? (T2) regression: first-innings runs (P1).

**Population.** Decided matches only for T1 (n = 1,218).

**Orientation (trap #1).** Build one row per match with `team_a`/`team_b` assigned by a seeded coin flip (or alphabetical on franchise_id — pick via ADR), features expressed as **differences** (A − B) plus symmetric context; target `a_wins`. At inference, average `p(A,B)` and `1 − p(B,A)`. **Tests:** (i) swap-invariance `|p(A,B) − (1 − p(B,A))| < 1e-9`; (ii) a model given only the orientation flag scores AUC ≈ 0.5 (bootstrap CI contains 0.5).

**Two tiers.**
- **Tier A — pre-toss:** teams, venue, date, stage, and history-only features. No toss, no batting order, no current XI.
- **Tier B — post-toss:** Tier A + toss winner/decision, derived `a_bats_first`, and current-XI features.

**Features (all as-of, all prior matches only).**
- `elo_diff` (init 1500; K, margin-of-victory multiplier, season carry-over `elo ← λ·elo + (1−λ)·1500`, optional home bonus; **tune K, λ, margin scale on dev walk-forward log-loss**; new franchises start at 1500).
- Form: smoothed win% last 5/10, rolling runs scored/conceded (last 10), season-to-date win% and games played, days of rest (diff).
- Head-to-head: smoothed win% (all-time and last ~5 seasons), meetings count.
- Venue: shrunk venue mean first-innings score, shrunk bat-first win rate, each team's shrunk win% at the venue, `is_home` (from `home_grounds.yaml`).
- Context: `stage`, `impact_era`, `season_year` trend (careful: extrapolation risk — test with/without).
- Tier B only: toss features; XI continuity vs previous match (Jaccard); XI experience (sum of prior appearances); cumulative prior POTM count of the XI; debutant count.
- **Forbidden:** anything from the match itself post-toss (runs, wickets, margins, POTM, result_type, umpire-decisions).
- Smoothing/shrinkage: `(wins + m·prior)/(n + m)`, `m` tuned.

**Splits.**
- **Dev:** seasons ≤ 2024. Hyperparameter tuning and model selection by **expanding-window walk-forward** (train on seasons < S, validate on S, for S = 2012…2024); report mean ± std across folds.
- **Final holdout:** 2025 + 2026 (~146 decided matches). Touched **once**, after the final model/calibrator choice is frozen and logged. Report bootstrap CIs (≥ 2,000 resamples) — with n ≈ 146, expect wide intervals; say so.
- Standard random K-fold is **prohibited** for T1/T2 (assert in code that folds are chronological).

**Baselines (report all).** B0 constant p=0.5 · B1 chase-bias prior (bat-second win rate **estimated on the training fold only** — the 54.7% all-data figure would leak the holdout; plan_review #6) · B2 "toss winner wins" (Tier B) · B3 higher-Elo wins · B4 venue chase-rate. A model must beat these on log-loss with a paired bootstrap to be claimed as useful.

**Model families (≥ 4).** L2 logistic regression (scaled) · Random Forest · HistGradientBoosting (and/or XGBoost/LightGBM per R6) · a regularized stacked/blended model · optionally Elo-only logistic as an interpretable ablation. Search spaces small and documented (n is small — avoid heavy tuning; watch overfitting to walk-forward folds).

**Calibration.** Compare uncalibrated vs Platt (sigmoid) vs isotonic under walk-forward; with n ≈ 1.2k prefer the simpler method unless evidence says otherwise (R7). Report reliability diagram + ECE.

**Metrics.** Primary: **log-loss**. Secondary: Brier score (with reliability/resolution decomposition), accuracy, ROC-AUC, ECE. Ablations: feature-group removal (Elo only / +form / +venue / +H2H / +squad). Also report performance by era and by stage (league vs playoff).

**Leakage defenses (each has a test in `tests/validation/`).**
1. **Future-perturbation test:** mutate/delete all matches after date D → features for matches ≤ D unchanged (bitwise).
2. **Label-shuffle test:** shuffling `a_wins` collapses AUC to ≈ 0.5.
3. **Same-day test:** two matches on the same date never see each other.
4. **Column allow-list test:** the feature matrix columns ⊆ a declared allow-list; any post-match column raises `FeatureLeakageError`.
5. **"Too good" guard:** the evaluation step warns if holdout AUC > 0.72.

**Explainability & honesty.** Model card lists limitations: small n, unmodeled factors (injuries, pitch, form of individual players, weather/dew), franchise-continuity assumptions, D/L noise, structural changes (Impact Player). State the *value added over baselines*, even if small.

---

## 8. Database design (SQLite via SQLAlchemy 2.x; draw the ER diagram from the real models)

Tables (PK/FK, indexes, NOT NULL/CHECK constraints, FK enforcement `PRAGMA foreign_keys=ON`):
- `franchise(franchise_id PK, canonical_name UNIQUE, short_code, lineage_note)`
- `team_alias(alias PK, franchise_id FK, valid_from_year, valid_to_year)`
- `venue(venue_id PK, canonical_name UNIQUE, city, country)`
- `season(season_id PK, season_year UNIQUE, raw_label, host_note, n_matches)`
- `player(player_id PK, name UNIQUE)`
- `official(official_id PK, name UNIQUE)`
- `match(match_id PK, season_id FK, date, match_number NULL, stage, venue_id FK, team1_id FK, team2_id FK, toss_winner_id FK, toss_decision CHECK IN('bat','field'), bat_first_id FK, team1_runs, team1_wkts, team2_runs, team2_wkts, winner_id FK NULL, result_type CHECK IN('complete','tie','no result'), margin_type, margin_value, dls_flag, potm_player_id FK NULL, referee_id, umpire1_id, umpire2_id, tv_umpire_id, reserve_umpire_id; UNIQUE(date, team1_id, team2_id))`
- `match_player(match_id FK, team_id FK, player_id FK, slot_no; PK(match_id, team_id, player_id))`
- `model_run(run_id PK, created_at, model_name, tier, params_json, data_sha256, git_commit, metrics_json, artifact_path, artifact_sha256)`
- `prediction_log(prediction_id PK, created_at, run_id FK, team_a_id, team_b_id, venue_id, stage, toss_json, p_a, latency_ms)`
- Views: `v_team_season_summary`, `v_head_to_head`.

Deliver: ER diagram, schema DDL in `docs/`, normalization argument (3NF) in the report.

---

## 9. Testing strategy

- **Unit:** every function in `data/ analytics/ features/ models/ services/` (canonical maps, derived columns, Elo math, shrinkage, splits chronology, registry hashing).
- **Property-based (Hypothesis):** Elo zero-sum and monotonicity; shrinkage bounds; orientation swap symmetry; probabilities ∈ [0,1] and sum to 1.
- **Data-contract:** pandera schemas on raw + processed; test that the real CSV passes lenient mode with the *documented* number of quarantined rows.
- **Validation (ML):** the five leakage tests, reproducibility test, baseline-beating test (with tolerance), calibration sanity test.
- **Integration:** full pipeline on `tests/fixtures/sample_60.csv` (CSV → DB → features → train → predict) in < 30 s.
- **App/CLI:** `streamlit.testing.v1.AppTest` smoke tests for every page including invalid inputs; Typer `CliRunner` tests for every command.
- **Security tests:** SQL-injection strings as team/venue inputs are rejected or inert; tampered model artifact → `ModelIntegrityError`; oversized/non-CSV upload rejected; CSV-injection payloads neutralized in exports.
- **Report test:** `tests/validation/test_report_structure.py` extracts the PDF text and asserts all 15 required headings + diagram figure captions exist.
- **Coverage:** `pytest --cov` → `reports/coverage.json`; target ≥ 85% on core packages (state actual numbers, don't inflate).
- **CI (`.github/workflows/ci.yml`):** matrix {ubuntu, windows} × {py3.11, py3.12}: install, `ruff`, `mypy`, `pytest --cov`, `bandit`, `pip-audit`. Add the CI badge to README.

---

## 10. Documentation & diagram deliverables

Sources live in `docs/diagrams/` (Mermaid `.mmd`; PlantUML/Graphviz for the use-case diagram), rendered to **SVG + 300-dpi PNG**, embedded in README/report. Diagrams must reflect the *real* code (class/component/ER generated or checked against the codebase).

| ID | Diagram | Notes |
|---|---|---|
| D1 | System architecture | Layers, stores (CSV, SQLite, Parquet, registry), UI/CLI, CI |
| D2 | Data pipeline / process flow | Raw CSV → validate → quarantine/clean → canonicalize → DB/Parquet → features → train → evaluate → registry → app |
| D3 | User workflow | Analyst path and Predictor path (activity diagram) |
| D4 | Use case | Actors: Analyst/Student, Cricket Fan, Maintainer; use cases mapped to FR IDs |
| D5 | Sequence: predict | UI → PredictionService → FeatureBuilder(as_of) → Registry(hash check) → Model → Calibrator → Explainer → Logger → UI |
| D6 | Sequence: train/evaluate | CLI → pipeline → splits → tuning → holdout → registry → model card |
| D7 | Class diagram | Config, MatchRepository, FeatureBuilder, EloRatingSystem, Trainer, Evaluator, ModelRegistry, PredictionService, exceptions |
| D8 | Component/package diagram | Packages + allowed dependency arrows (matches import-linter contract) |
| D9 | ER diagram | From section 8 |
| D10 | Deployment/environment | Local Mac/Windows, optional Streamlit Community Cloud |
| D11 | Walk-forward timeline (figure) | Dev folds + final holdout |
| D12 | Model lifecycle state diagram (optional) | trained → validated → registered → served |

Other docs: `data_dictionary.md` (every raw + derived column, type, source, allowed values), `architecture.md`, `course_mapping.md` (syllabus topic → module → file → test), `rubric_traceability.md` (every rubric line and every PDF checklist item → evidence path), `viva_prep.md` (module-by-module explanation, why each design choice, ≥ 30 likely viva questions with answers, the leakage story, limitations — the student must be able to defend every line).

**README.md** (per PDF §5.1): title, overview, features, technologies, install & run (macOS + Windows), how to test, screenshots (real, from Playwright), architecture image, project structure, results summary (numbers injected from `reports/metrics.json`), disclaimer, license + **data attribution** (R5), author.
**statement.md** (per PDF §5.2): problem statement, scope (in/out), target users, high-level features.

---

## 11. Project report (PDF) — `report/build_report.py`

Build pipeline: Markdown sections (`report/sections/NN_*.md`) + Jinja2 → HTML (`template.html`, `styles.css`, TOC, page numbers, figure/table captions) → PDF via Playwright Chromium print (or WeasyPrint if research says it is more robust). **All numbers are template variables from `reports/*.json`; no hand-typed metrics.** Target 30–45 pages. Verify by rasterizing a few pages and inspecting them (layout, diagram legibility, no clipped tables).

Required structure — **use these exact headings, in this order** (matches PDF §6):
1. **Cover Page** — title, "Build Your Own Project – VITyarthi", course name, student name, registration number, section, university, date, repo URL.
2. **Introduction**
3. **Problem Statement**
4. **Functional Requirements** (table with IDs, module, priority, implementing file, test)
5. **Non-functional Requirements** (section 4.2 table + measured results)
6. **System Architecture** (D1, D10, layer rules)
7. **Design Diagrams** — Use Case (D4), Workflow (D2/D3), Sequence (D5/D6), Class/Component (D7/D8), ER (D9) + schema
8. **Design Decisions & Rationale** (summarize ADRs: orientation trap, canonicalization, walk-forward, calibration choice, SQLite, Streamlit, etc.)
9. **Implementation Details** (dataset description, cleaning fixes with counts, feature engineering, model selection rationale, evaluation methodology, module walkthrough)
10. **Screenshots / Results** (real app screenshots; metrics table with CIs; reliability diagram; ablations; baseline comparison; analytics highlights incl. toss finding)
11. **Testing Approach** (pyramid, leakage tests, coverage numbers, CI, security tests)
12. **Challenges Faced** (real ones from `PROGRESS.md`/ADRs — e.g., `team1` semantic drift, venue aliasing, D/L rows, small-n honesty)
13. **Learnings & Key Takeaways**
14. **Future Enhancements** (ball-by-ball data, live win probability, player-level models, auth/multi-user, deployment)
15. **References** (IEEE style, only sources actually opened; data source + license; library docs)

---

## 12. GitHub & version control plan (10% of grade — the history is graded)

- Create the public repo with `gh repo create <owner>/creaseiq --public --source=. --remote=origin` once `gh` is authenticated; otherwise finish locally and print the exact push commands.
- **Branching:** `main` protected by convention; feature branches `feat/…`, `fix/…`, `docs/…`, `test/…`, `chore/…`; merge with `--no-ff`; each phase ends with a tag (`v0.1.0` … `v1.0.0`).
- **Commits:** Conventional Commits (`feat(features): add as-of Elo engine`), small and atomic; test with its code; docs with their feature. Target **60+ meaningful commits** across the build (not padded — real increments). Write a proper body for non-trivial commits (why, not just what).
- Maintain `CHANGELOG.md` (Keep-a-Changelog). Add issue-style TODOs to `PROGRESS.md`; optionally open a few real GitHub issues/PRs for the P2 items to show workflow.
- `.gitignore`: venvs, caches, logs, `data/creaseiq.db`, `data/interim/`, large artifacts (keep `registry.json` and the small final model if < ~10 MB), Playwright browsers. Never commit secrets.
- Don't touch global git config; never force-push; never rewrite published history.

---

## 13. RESEARCH MANDATE (not optional, and not a one-time step)

**Ground rules.** Use web search **and fetch/read the actual pages**; do not cite from snippets or memory. Prefer primary sources (papers, official docs, IPL/BCCI pages, data-provider docs). Record each finding in `docs/research_notes.md` with: question · answer · source URL · date accessed · confidence · **decision it drives**. Paraphrase; do not copy text. If research contradicts this plan, the plan yields — write an ADR. Today is 2026-09-28: version numbers, deprecations and season facts must be verified live.

| ID | Research question | Drives |
|---|---|---|
| R1 | Identify the exact VITyarthi course/syllabus for `COURSE_NAME` (and read `docs/assignment/syllabus.txt` if present). Which units/concepts must the project visibly demonstrate? If the course is not ML/data-analytics-oriented, how should module emphasis be re-weighted? | `course_mapping.md`, ADR-001, module weights |
| R2 | IPL structural history: franchise lineage/renames and dates; which franchises are continuations; stadium renames and canonical names for all 60 venue strings; franchise home grounds by era; seasons hosted abroad; format changes (teams count, playoffs format, 2023 Impact Player). Player-name alias risks. | `team_lineage.yaml`, `venue_canonical.yaml`, `home_grounds.yaml`, `era` features |
| R3 | Literature and practitioner baselines for cricket/T20 pre-match outcome prediction: realistic accuracy/log-loss ceilings, features that actually work, Elo K/margin tuning for T20, known pitfalls. Collect 8–12 credible sources. | Expected-performance statement, feature set, Elo design |
| R4 | Toss effect in T20/IPL: published findings, proper test design, venue/era/dew confounders. | `toss_analysis.py`, report narrative |
| R5 | Data provenance and license (Cricsheet-style); attribution requirements and citation; provenance discrepancies. | README attribution, references, LICENSE notes |
| R6 | Tooling currency and compatibility on Apple Silicon + Windows + Python 3.12/3.13. | Pinned requirements, ADR-002 |
| R7 | Evaluation methodology for small, time-ordered data: walk-forward vs blocked CV, calibration method choice at n≈1.2k, paired bootstrap for log-loss differences, avoiding overfit to the holdout, ECE pitfalls. | `splits.py`, `evaluate.py`, `calibrate.py` |
| R8 | Super-over winners for the 16 tied matches (≥ 2 independent references each). Verify the 6 D/L-suspect rows and the `team2_wickets=12` and tiny-score anomalies. | `data/external/`, data-quality report |
| R9 | Existing IPL prediction/EDA projects: what they do, common flaws, and what CreaseIQ does differently. Do not copy code. | Innovation section of the report |
| R10 | Ground-truth checks: champions and finals for every season, IPL 2025 and 2026 season facts. | Data-quality assertions, tests |
| R11 | Responsible-use and academic-integrity expectations: disclaimer wording, VITyarthi rules on AI-assisted work. | README, `viva_prep.md` |

**Research cadence.**
- **Phase 0 (before code):** R1, R2, R5, R6, R10 minimum; start R3/R4/R7/R9.
- **Before modeling (Phase 3):** finish R3, R7, R8.
- **Before report (Phase 8):** re-verify every reference URL still resolves; finish R9, R11.
- **Plan review (Phase 0 exit):** write `docs/plan_review.md` — at least **5 concrete risks/improvements found in this plan** and the changes made.
- Log anything surprising in `PROGRESS.md → Challenges` (this becomes report section 12).

---

## 14. Phased execution plan (each phase ends with: `ruff` + `mypy` + `pytest` green → update `PROGRESS.md` → merge → tag)

**Phase 0 — Research, review, scaffolding (tag v0.1.0)** — research notes, plan review, ADR-001 (course relevance/scope), ADR-002 (stack); scaffold repo, pyproject, config loader, logging, exceptions, CI, pre-commit, CLAUDE.md, PROGRESS.md, README skeleton. **Exit:** CI green on skeleton; raw CSV hash recorded.

**Phase 1 — Data layer (v0.2.0)** — schema validation, lineage/venue YAMLs, cleaning + derived columns, quarantine, quality report, data dictionary. **Exit:** 0 unmapped teams/venues; documented fix counts; champion validated against R10; ≥ 90% coverage on `data/`.

**Phase 2 — Database + analytics (v0.3.0)** — SQLAlchemy models, idempotent loader, repositories, views; analytics functions, hypothesis tests, golden-file tests; thin EDA notebook. **Exit:** DB rebuild twice → identical content checksums; analytics 1–8 tested; toss/era findings with effect sizes + CIs.

**Phase 3 — Features + Elo (v0.4.0)** — Elo, form, H2H, venue, squad, `FeatureBuilder` with `as_of`; all five leakage tests written **before** model code. **Exit:** leakage, allow-list, Elo property and orientation tests pass.

**Phase 4 — Modeling & evaluation (v0.5.0)** — splits, baselines, ≥ 4 models, walk-forward tuning, calibration, ablations, one-shot holdout, registry, explainability, model card, drift; P1 score regressor. **Exit:** `reports/metrics.json` complete with CIs; honest baseline comparison; reproducibility test passes.

**Phase 5 — Services, CLI, app (v0.6.0)** — services, Typer CLI, Streamlit pages, caching, error UX, upload (P1), what-if (P1), logging + prediction log. **Exit:** AppTest on every page; invalid-input tests; NFR-01 benchmark met.

**Phase 6 — Hardening (v0.7.0)** — security tests, bandit/pip-audit, import contract, coverage ≥ 85% core, perf profile, Windows CI. **Exit:** NFR-01…08 evidence in `reports/`.

**Phase 7 — Documentation & diagrams (v0.8.0)** — D1–D12, architecture, course mapping, rubric traceability, viva prep, README with real screenshots, statement. **Exit:** diagrams match code; README install verified on a clean venv.

**Phase 8 — Report (v0.9.0)** — PDF from templates + JSON; rasterize and inspect; structure test; re-verify references. **Exit:** 15 headings in order, ≥ 30 pages, legible figures, zero hand-typed metrics.

**Phase 9 — Final QA and release (v1.0.0)** — independent review against section 15; clean-clone test (`creaseiq all`, tests, headless app screenshot). **Exit:** section 15 all ✅; push; final tag.

**Cut line:** cut P2 first, then P1 in this order: umpire table → Monte Carlo → score regressor → what-if → upload. **Never cut:** tests, leakage protection, docs/diagrams, README/statement, the report, git hygiene.

---

## 15. Final acceptance checklist (report ✅/❌ with evidence paths)

**Assignment compliance**
- [ ] Course relevance demonstrated in `docs/course_mapping.md` and report intro
- [ ] ≥ 3 major functional modules with clear I/O and workflow (we have 5)
- [ ] ≥ 4 NFRs specified and verified (we have 8)
- [ ] ≥ 5–10 meaningful modules/files, package structure, tests, validation/error handling, Git
- [ ] Problem statement, objectives, FR, NFR in docs and report
- [ ] Architecture, workflow, use case, class/component, sequence, ER diagrams + schema
- [ ] Dataset description, model selection rationale, evaluation methodology
- [ ] `README.md` has all 7 required items; `statement.md` has all 4
- [ ] PDF report has all 15 sections, in order

**Rubric mapping**
- [ ] Problem Understanding & Requirements (10): `statement.md`, FR/NFR tables, traceability matrix
- [ ] Design & Documentation (20): D1–D12, ADRs, data dictionary, model card
- [ ] Implementation Quality (25): clean layered code, types, docstrings, lint/type/CI green, coverage numbers, error handling
- [ ] Innovation, Depth & Complexity (15): leakage-safe `as_of` engine, margin-aware Elo, walk-forward + calibration + bootstrap CIs, two-tier prediction, what-if, score regressor, statistical tests, drift monitor, data-trap discoveries
- [ ] GitHub & Version Control (10): 60+ real commits, feature branches, tags, changelog, CI badge
- [ ] Project Report (20): complete, visual, evidence-based, references verified

**Integrity**
- [ ] No fabricated metrics, screenshots or references
- [ ] Holdout touched once and logged
- [ ] All leakage tests pass; holdout results plausible (no > 0.72 AUC unexplained)
- [ ] Clean-clone install + run verified (Windows locally; macOS/Ubuntu via CI)
- [ ] Data attribution and disclaimer present

---

## 16. Risk register

| Risk | Mitigation |
|---|---|
| Hidden leakage inflates results | Section 7 tests; treat suspiciously high scores as bugs |
| Course mismatch → 0 marks | R1 first; `course_mapping.md`; ADR-001 |
| Small n makes model gains statistically weak | Bootstrap CIs, paired tests, honest wording, baselines |
| Franchise-continuity assumptions bias Elo | ADR + sensitivity check |
| Venue/team alias gaps | Fail-loud canonicalization + tests |
| Dependency install trouble on M2/Windows | Prefer scikit-learn HGB; verify in CI |
| Context loss in a long build | `CLAUDE.md`, `PROGRESS.md`, small commits, phase exits |
| Over-scoping | Priorities P0/P1/P2 and the cut line in section 14 |
| Student can't defend the code in viva | `viva_prep.md`; readable, well-commented modules; ADRs explain *why* |

---

## 17. Style guide for Claude Code's own behavior

- Be terse in chat, thorough in artifacts. Report status as: phase · done · next · blockers.
- Prefer boring, well-tested code over clever code. Small functions, explicit names, no dead code.
- Comments explain *why*, docstrings explain *what/inputs/outputs* and cite FR IDs.
- Whenever you make a non-obvious choice, write a 10–20 line ADR: context · options · decision · consequences.
- When something in this plan turns out wrong, say so in `PROGRESS.md`, fix the plan file, and continue.
