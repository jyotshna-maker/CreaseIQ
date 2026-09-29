# 9. Implementation Details

## 9.1 Dataset description
The core input data is sourced from Cricsheet's open community scorecard archives [1]:

- **Dimensionality:** {{ q.raw.rows | int }} match rows across {{ q.raw.columns }} attributes, structured as a single record per fixture spanning {{ q.seasons[0].first_match }} to {{ q.seasons[-1].last_match }}.
- **Integrity verification:** The dataset is treated as immutable, safeguarded by a SHA-256 fingerprint check (`{{ q.raw.sha256[:16] }}…`).
- **Core schema attributes:** Tournament edition, match index, fixture date, host city, designated venue, participating franchises, coin-toss victor and tactical decision, team totals (runs and wickets lost), final winner, victory margin, player of the match, officiating umpires, six fixed match descriptors (20-over male club T20), and participating squad arrays.
- **Squad representations:** Up to the 2022 season, lineups recorded 11 players per team. From 2023 onward, scorecards capture 12 players per side to incorporate the tactical Impact Player substitute.

{{ tab("Outcome composition") }}

| Matches | Decided | Ties | No result | Voided | Distinct players | Toss decision field / bat |
|---|---|---|---|---|---|---|
| {{ q.results.matches | int }} | {{ q.results.decided | int }} | {{ q.results.ties }} | {{ q.results.no_results }} | {{ q.results.voided }} | {{ q.identity.players }} | {{ q.results.toss_decision_counts.field }} / {{ q.results.toss_decision_counts.bat }} |

{{ tab("Seasons and derived champions (champions verified against published results for all seasons)") }}

| Season | Label | Matches | Decided | Ties | No result | Champion |
|---|---|---|---|---|---|---|
{% for s in q.seasons %}| {{ s.season_year }} | {{ s.raw_label }} | {{ s.matches }} | {{ s.decided }} | {{ s.ties }} | {{ s.no_results }} | {{ s.champion }} |
{% endfor %}

## 9.2 Validation and cleaning
**Validation pipeline:** Data integrity is evaluated across two complementary stages:

1. A declarative pandera schema validates datatype constraints, boundary conditions, acceptable categorical values, and fixed metadata columns.
2. Nine vectorized validation checks evaluate cross-attribute business logic:

    - Teams participating in a match must be distinct.
    - Both the coin-toss winner and final match winner must belong to the participating teams.
    - A declared winner must be present if and only if the match result is marked as completed.
    - Exactly one victory margin (runs or wickets) must be populated.
    - Tied contests must not register victory margins.
    - Wickets lost cannot exceed 10 in standard regulation play.
    - Match timestamps must represent valid calendar dates.
    - Lineups must enumerate between 11 and 13 registered athletes.

During exploratory ingestion, malformed entries are routed to `quarantine.csv` with specific diagnostic messages. In strict production mode, validation violations immediately raise fatal exceptions. The baseline IPL matches file passes strict validation with **{{ q.validation.quarantined }} quarantined rows**.

**Cleaning pipeline:** Every automated repair is systematically audited:

{{ tab("Fixes applied by the cleaning pipeline (from the data-quality report)") }}

| Fix | Rows |
|---|---|
{% for k, v in q.fixes.items() %}| `{{ k }}` | {{ v | int }} |
{% endfor %}

**Synthesized domain attributes** (detailed in `docs/data_dictionary.md`):
- `season_year` and actual batting order derived directly from toss outcomes.
- Standardized regulation scores for first and second innings (clearing super-over contamination).
- Playoff bracket classification (`stage`), final tournament winner (`season_champion`), and era flag (`impact_era`).
- Home territory flags derived from historical ground residency mappings, with neutral seasons specified for 2009, 2020, 2021, and 2022.
- Diagnostic indicators: `dls_flag`, `voided`, and `scores_usable`.

## 9.3 Feature engineering
To eliminate leakage, all features reflect tournament state accumulated *strictly prior to the match date* (Section 8.2), structured antisymmetrically as Team A minus Team B:

{{ tab("Feature groups (tier B adds the toss and squad groups)") }}

| Group | Features | Notes |
|---|---|---|
| Elo | `elo_diff`, `home_diff` | Margin-aware Elo, tuned; home bonus only when exactly one side is at home |
| Form | last-5 and last-10 smoothed win rate, runs scored and conceded (last 10), season win % and games, rest days | Smoothed toward 0.5 (prior strength 2) |
| Head-to-head | all-time and last-5-seasons edge, meetings | Edge = (wins_A − wins_B)/(n + 2) |
| Venue | team-at-venue edge, shrunk venue scoring level, shrunk bat-first rate | Priors are the league values *so far* |
| Context | playoff flag, Impact Player era | Symmetric |
| Toss (post-toss) | A bats first, A won the toss, batting order × venue, batting order × era | Interactions let linear models use venue and era context |
| Squad (post-toss) | experience of the XI, prior POTM awards, debutants, continuity (Jaccard) | Named XI known at the toss |

**Elo calculation engine:**

- **Win expectation:** $E_A = 1 / (1 + 10^{-(R_A - R_B + H)/400})$.
- **Rating update:** $R_A' = R_A + K \cdot M \cdot (S_A - E_A)$, where margin multiplier $M = \ln(\text{units} + 1) \cdot \frac{2.2}{0.001 \cdot \Delta_{\text{winner}} + 2.2}$ [6].
- **Margin scaling:** 10 runs or 2 wickets constitute one standardized margin unit.
- **Rain interruptions:** Duckworth-Lewis matches revert to a neutral multiplier of $M = 1$.
- **Inter-season reversion:** Franchise ratings regress 33% back toward the league mean of 1500 between tournament editions.

Elo hyperparameters were optimized across development seasons over {{ m.elo_tuning.n_candidates }} parameter combinations. The optimal configuration yielded `{{ m.elo_tuning.best | kv }}`, achieving a walk-forward cross-entropy of {{ m.elo_tuning.best_mean_log_loss | f(4) }} compared against {{ m.elo_tuning.default_mean_log_loss | f(4) }} under uncalibrated default parameters.

## 9.4 Model selection rationale
Given the bounded sample size of ~1,200 professional cricket matches and inherently high gameplay variance, we deliberately focused on constrained, interpretable model families rather than overly complex deep networks:

{{ tab("Walk-forward mean log-loss of the best configuration of each family, with baselines (development seasons)") }}

| Candidate | Pre-toss | Post-toss |
|---|---|---|
{% for name in ["elo_logit", "logreg", "random_forest", "hist_gb", "blend"] %}| {{ name }} | {{ m.tiers.pre_toss.best_per_family[name].mean_log_loss | f(4) }} ± {{ m.tiers.pre_toss.best_per_family[name].std_log_loss | f(4) }} | {{ m.tiers.post_toss.best_per_family[name].mean_log_loss | f(4) }} ± {{ m.tiers.post_toss.best_per_family[name].std_log_loss | f(4) }} |
{% endfor %}| B0 coin flip | {{ m.tiers.pre_toss.baselines_walk_forward.B0_constant.mean_log_loss | f(4) }} | {{ m.tiers.post_toss.baselines_walk_forward.B0_constant.mean_log_loss | f(4) }} |
| B3 Elo probability | {{ m.tiers.pre_toss.baselines_walk_forward.B3_elo.mean_log_loss | f(4) }} | {{ m.tiers.post_toss.baselines_walk_forward.B3_elo.mean_log_loss | f(4) }} |
| B1 chase prior | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B1_chase_prior.mean_log_loss | f(4) }} |
| B2 toss winner | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B2_toss_winner.mean_log_loss | f(4) }} |
| B4 venue chase rate | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B4_venue_chase.mean_log_loss | f(4) }} |

Model families evaluated:
- **Elo-logistic classifier:** A minimal, highly transparent baseline driven by rating differentials.
- **L2 regularized logistic regression:** Optimized with zero intercept over purely antisymmetric features (Section 8.1).
- **Random Forests & Histogram Gradient Boosting:** Non-linear tree ensembles capable of discovering complex feature interactions.
- **Ensemble Blend:** A weighted combination of regularized logistic regression and gradient boosted decision trees.

Applying the one-SE selection heuristic identified:
- **Pre-toss selection:** **{{ m.tiers.pre_toss.selection.chosen }}** (`{{ m.tiers.pre_toss.selection.params | kv }}`), where the numerical minimum belonged to {{ m.tiers.pre_toss.selection.best_by_mean }}.
- **Post-toss selection:** **{{ m.tiers.post_toss.selection.chosen }}** (`{{ m.tiers.post_toss.selection.params | kv }}`), where the numerical minimum belonged to {{ m.tiers.post_toss.selection.best_by_mean }}.

Tree-based ensembles failed to convincingly outperform linear formulations. With limited observations and high noise levels, ensemble variance rapidly overshadows non-linear expressive gains.

## 9.5 Evaluation methodology
{{ fig("reports/figures/walk_forward_timeline.png", "Expanding-window walk-forward folds and the locked holdout (D11)", "85%") }}

- **Data splits:**
  - Development seasons encompass tournaments through {{ m.splits.dev_last_season }}, evaluated across expanding walk-forward slices from {{ m.splits.first_validation_season }} to {{ m.splits.dev_last_season }}.
  - Final holdout testing isolates the {{ m.splits.holdout_seasons | join(", ") }} seasons (comprising n = {{ m.tiers.post_toss.n_holdout }} decided games), evaluated strictly once after model selection was locked.
- **Evaluation metrics:**
  - Primary metric: cross-entropy log-loss.
  - Secondary metrics: Brier score (with Murphy calibration decomposition), classification accuracy, ROC-AUC, and equal-mass Expected Calibration Error [14]–[16].
- **Uncertainty quantification:** 2,000 percentile bootstrap resamples (seed {{ m.seed }}) calculated for all reported holdout metrics.
- **Baseline statistical testing:** Paired bootstrap comparison of per-match log-loss differentials (10,000 iterations), complemented by the Diebold-Mariano test using Harvey-Leybourne-Newbold small-sample corrections [18].
- **Rigorous baseline boundaries:** Baseline historical win percentages are fit strictly on training splits. Fitting chase rates across the complete dataset would have leaked holdout base rates into early predictions.
- **Automated safeguards:**
  - A suspicious-performance guard flags holdout AUC exceeding 0.72 or accuracy over 68% as potential data leakage.
  - Layered ablation experiments track incremental performance gains as feature groups are introduced.
  - Model diagnostics break down errors across tournament eras and playoff stages.

## 9.6 Module walkthrough
{{ tab("Packages and their responsibilities") }}

| Package | Main modules | Responsibility |
|---|---|---|
| `data` | `source`, `schema`, `ingest`, `canonical`, `cleaning`, `quality_report`, `pipeline` | FR-01..03: validated, canonical match table |
| `db` | `models`, `session`, `loader`, `repository` | FR-04: 3NF schema, idempotent load, parameterised queries |
| `analytics` | `hypothesis_tests`, `toss_analysis`, `team_stats`, `venue_stats`, `venue_clusters`, `season_trends`, `player_stats`, `summary` | FR-06..10 |
| `features` | `elo`, `form`, `head_to_head`, `venue_effects`, `squad`, `builder` | FR-12, FR-13 |
| `models` | `splits`, `baselines`, `train`, `calibrate`, `evaluate`, `elo_tuning`, `explain`, `registry`, `predict`, `score_regressor`, `experiment` | FR-14..18 |
| `simulation` | `what_if`, `season_monte_carlo` | FR-19, FR-20 |
| `services` | `context`, `prediction_service`, `analytics_service`, `scenario_service`, `ingest_service`, `benchmark_service` | Use cases for the CLI and UI |
| `reporting` | `figures`, `model_card`, `drift`, `nfr`, `readme`, `report_builder`, `assets` | FR-21, FR-22, this report |
| `viz`, `app`, `cli` | Plotly charts; 7 Streamlit pages; 15 CLI commands | Presentation |

In addition to operational utilities `version` and `info`, the platform CLI exposes thirteen primary commands: `validate`, `build-db`, `analyze`, `features`, `train`, `evaluate`, `predict`, `whatif`, `simulate`, `ingest`, `benchmark`, `report`, and `all`. Operational failures display human-friendly explanations and return clean non-zero exit codes without unhandled tracebacks.
