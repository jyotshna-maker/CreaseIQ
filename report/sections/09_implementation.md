# 9. Implementation Details

## 9.1 Dataset description
The input is a Cricsheet-derived IPL match file [1]:

- **Size:** {{ q.raw.rows | int }} rows × {{ q.raw.columns }} columns, one row per match, from {{ q.seasons[0].first_match }} to {{ q.seasons[-1].last_match }}.
- **Integrity:** SHA-256 `{{ q.raw.sha256[:16] }}…`, stored immutably.
- **Columns:** event, season label, match number, date, city, venue, the two teams, toss winner and decision, runs and wickets for each team, winner, result type, margins, player of the match, five officials, six constant columns (T20, 20 overs, 6 balls, male, club), and the two squad lists.
- **Squads:** 11 players each through 2022, and 12 from 2023, when the Impact Player substitute is listed.

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
**Validation** has two layers:

1. A pandera schema checks types, value ranges, allowed values and the six constant columns.
2. Nine vectorised row rules check cross-column logic:
   - the teams are distinct;
   - the toss winner and the winner both took part in the match;
   - a winner is present exactly when the result is "complete";
   - exactly one margin is recorded;
   - there are no margins on ties;
   - at most 10 wickets except on ties;
   - the date is valid;
   - each squad lists 11–13 players.

In lenient mode, failing rows go to `quarantine.csv` with named reasons. Strict mode raises with the row indices. The real file passes strict validation with **{{ q.validation.quarantined }} quarantined rows**.

**Cleaning** records every change it makes:

{{ tab("Fixes applied by the cleaning pipeline (from the data-quality report)") }}

| Fix | Rows |
|---|---|
{% for k, v in q.fixes.items() %}| `{{ k }}` | {{ v | int }} |
{% endfor %}

**Derived columns** (all documented in `docs/data_dictionary.md`):
- `season_year` and batting order from the toss.
- Regulation first- and second-innings runs.
- An era-specific playoff `stage`, `season_champion` and `impact_era`.
- Home flags from a researched home-ground knowledge base, with neutral seasons covering 2009, 2020, 2021 and 2022.
- `dls_flag`, `voided` and `scores_usable`.

## 9.3 Feature engineering
Every feature is computed *as of the day before* the match (Section 8.2) and oriented A − B. The groups are:

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

**Elo engine.**

- **Expected score:** 1/(1 + 10^(−(R_A − R_B + H)/400)).
- **Update:** K × margin multiplier × (S − E), where the multiplier is ln(units + 1) · 2.2/(0.001 · Δ_winner + 2.2) [6].
- **Margin units:** runs/10 or wickets/2.
- **D/L results:** the multiplier is 1.
- **Season carry-over:** ratings regress toward 1500 each season.

The Elo parameters were tuned on development folds over {{ m.elo_tuning.n_candidates }} combinations. Best: `{{ m.elo_tuning.best | kv }}`, with walk-forward log-loss {{ m.elo_tuning.best_mean_log_loss | f(4) }} against {{ m.elo_tuning.default_mean_log_loss | f(4) }} for the defaults.

## 9.4 Model selection rationale
With about 1,200 matches and weak signal, the model families are deliberately simple and their search grids small:

{{ tab("Walk-forward mean log-loss of the best configuration of each family, with baselines (development seasons)") }}

| Candidate | Pre-toss | Post-toss |
|---|---|---|
{% for name in ["elo_logit", "logreg", "random_forest", "hist_gb", "blend"] %}| {{ name }} | {{ m.tiers.pre_toss.best_per_family[name].mean_log_loss | f(4) }} ± {{ m.tiers.pre_toss.best_per_family[name].std_log_loss | f(4) }} | {{ m.tiers.post_toss.best_per_family[name].mean_log_loss | f(4) }} ± {{ m.tiers.post_toss.best_per_family[name].std_log_loss | f(4) }} |
{% endfor %}| B0 coin flip | {{ m.tiers.pre_toss.baselines_walk_forward.B0_constant.mean_log_loss | f(4) }} | {{ m.tiers.post_toss.baselines_walk_forward.B0_constant.mean_log_loss | f(4) }} |
| B3 Elo probability | {{ m.tiers.pre_toss.baselines_walk_forward.B3_elo.mean_log_loss | f(4) }} | {{ m.tiers.post_toss.baselines_walk_forward.B3_elo.mean_log_loss | f(4) }} |
| B1 chase prior | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B1_chase_prior.mean_log_loss | f(4) }} |
| B2 toss winner | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B2_toss_winner.mean_log_loss | f(4) }} |
| B4 venue chase rate | n/a | {{ m.tiers.post_toss.baselines_walk_forward.B4_venue_chase.mean_log_loss | f(4) }} |

The families:

- **Elo-logit.** Interpretable, with two features.
- **L2 logistic regression.** No intercept and antisymmetric features only (Section 8.1).
- **Random forest and histogram gradient boosting.** They can use the symmetric context through interactions.
- **Blend.** Of logistic regression and gradient boosting.

Selection used the one-SE rule:

- **Pre-toss:** **{{ m.tiers.pre_toss.selection.chosen }}** `{{ m.tiers.pre_toss.selection.params | kv }}`. The best mean belonged to {{ m.tiers.pre_toss.selection.best_by_mean }}.
- **Post-toss:** **{{ m.tiers.post_toss.selection.chosen }}** `{{ m.tiers.post_toss.selection.params | kv }}`. The best mean belonged to {{ m.tiers.post_toss.selection.best_by_mean }}.

The tree ensembles did not beat the linear models. That is expected with n ≈ 1k and weak signal, where variance dominates.

## 9.5 Evaluation methodology
{{ fig("reports/figures/walk_forward_timeline.png", "Expanding-window walk-forward folds and the locked holdout (D11)", "85%") }}

- **Splits:**
  - Development seasons are ≤ {{ m.splits.dev_last_season }}, with folds validating seasons {{ m.splits.first_validation_season }}–{{ m.splits.dev_last_season }}.
  - The holdout is {{ m.splits.holdout_seasons | join(", ") }}: n = {{ m.tiers.post_toss.n_holdout }} decided matches, evaluated once per frozen selection.
- **Metrics:**
  - Primary: log-loss.
  - Also: Brier score with its Murphy decomposition, accuracy, ROC-AUC, and ECE on equal-mass bins (descriptive only [14]–[16]).
- **Uncertainty:** percentile bootstrap with {{ m.seed }}-seeded resampling (2,000 resamples) for every holdout metric.
- **Comparison with baselines:** a paired bootstrap of per-match log-loss differences (10,000 resamples), plus the Diebold–Mariano test with the Harvey–Leybourne–Newbold correction [18].
- **Baselines:** all rates are fitted on the training fold only. The plan's all-data chase rate would have leaked the holdout base rate (plan review finding 6).
- **Guards:**
  - A "too good" check flags holdout AUC above 0.72 or accuracy above 68% as suspected leakage.
  - Ablations add feature groups cumulatively.
  - Performance is broken down by era and stage.

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
| `viz`, `app`, `cli` | Plotly charts; 7 Streamlit pages; 12 CLI commands | Presentation |

The main CLI commands are `validate`, `build-db`, `analyze`, `features`, `train`, `evaluate`, `predict`, `whatif`, `simulate`, `ingest`, `benchmark`, `report` and `all`. Expected errors exit with code 1 and a one-line message.
