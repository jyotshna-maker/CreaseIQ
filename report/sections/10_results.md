# 10. Screenshots / Results

## 10.1 Application screenshots
The dashboard visualisations depicted below represent direct captures of the live Streamlit runtime environment, taken through automated Playwright headless sessions (`scripts/capture_screenshots.py`).

{{ fig("docs/screenshots/01_home.png", "Home: KPIs, data-quality and model status", "70%") }}

{{ fig("docs/screenshots/05_predict_match.png", "Predict Match: probability, plain-English drivers and model information", "70%") }}

{{ fig("docs/screenshots/04_venue_and_toss.png", "Venue & Toss: causal toss test with CI and minimum detectable effect, chasing by season", "70%") }}

{{ fig("docs/screenshots/03_team_analytics.png", "Team Analytics: records with Wilson CIs, titles, season form", "70%") }}

{{ fig("docs/screenshots/06_model_lab.png", "Model Lab: holdout metrics, paired comparisons, reliability, selection table", "70%") }}

{{ fig("docs/screenshots/07_what_if.png", "What-If: change in win probability for toss and venue scenarios", "70%") }}

{{ fig("docs/screenshots/02_data_explorer.png", "Data Explorer: filters, sanitised export and validated upload", "70%") }}

## 10.2 Analytics highlights
{{ tab("Headline statistical findings (decided matches)") }}

| Question | Estimate | 95% CI | Test | Interpretation |
|---|---|---|---|---|
| Does the toss winner win? | {{ a.toss.overall.rate | pct }} | {{ a.toss.overall.ci_low | pct }}–{{ a.toss.overall.ci_high | pct }} | exact binomial p = {{ a.toss.overall.p_value | f(2) }} | No detectable effect; MDE ±{{ (100 * a.toss.overall.mde) | f(1) }} pp |
| Does the chasing side win? | {{ a.chasing.overall.rate | pct }} | {{ a.chasing.overall.ci_low | pct }}–{{ a.chasing.overall.ci_high | pct }} | p = {{ a.chasing.overall.p_value | f(3) }} | Real, modest chasing edge |
| Chase edge, Impact era minus pre-2023 | {{ (100 * a.chasing.era_test_impact_minus_pre.diff) | f(1) }} pp | {{ (100 * a.chasing.era_test_impact_minus_pre.ci_low) | f(1) }} to {{ (100 * a.chasing.era_test_impact_minus_pre.ci_high) | f(1) }} pp | z-test p = {{ a.chasing.era_test_impact_minus_pre.p_value | f(2) }} | No evidence it changed |
| Home side wins (neutral seasons excluded) | {{ a.home_advantage.rate | pct }} | {{ a.home_advantage.ci_low | pct }}–{{ a.home_advantage.ci_high | pct }} | p = {{ a.home_advantage.p_value | f(3) }} | Small, borderline |
| First-innings runs, Impact era vs before | {{ a.era_scoring.mean_post | f(1) }} vs {{ a.era_scoring.mean_pre | f(1) }} | Δ {{ a.era_scoring.ci_low | f(1) }}–{{ a.era_scoring.ci_high | f(1) }} | Welch p = {{ "%.1e" | format(a.era_scoring.welch_p) }}; d = {{ a.era_scoring.cohens_d | f(2) }} | Large effect |
| 200+ first innings | {{ a.era_scoring.share_200_post | pct }} vs {{ a.era_scoring.share_200_pre | pct }} | n/a | n/a | {{ (a.era_scoring.share_200_post / a.era_scoring.share_200_pre) | f(1) }}× as frequent |

Looking at toss choices, captains opting to field first won a higher proportion of fixtures ({{ a.toss.by_decision[1].rate | pct }} versus {{ a.toss.by_decision[0].rate | pct }}; $\chi^2$ test $p = {{ a.toss.decision_outcome_chi2_associational.p_value | f(3) }}$, with Cramér's $V = {{ a.toss.decision_outcome_chi2_associational.cramers_v | f(2) }}$). We emphasize that this correlation is purely **associational**: tacticians choose to field when evening dew is anticipated or when their bowling attack is constructed for chasing.

{{ fig("reports/figures/chase_by_season.png", "Chasing side's win rate by season with 95% Wilson intervals", "85%") }}

{{ fig("reports/figures/scoring_trend.png", "Mean first-innings score and share of 200+ totals; the Impact Player era is shaded", "85%") }}

{{ fig("reports/figures/elo_timeline.png", "Tuned Elo ratings of the current top franchises", "85%") }}

Unsupervised venue clustering converged on **k = {{ a.venue_clusters.k }}** ground categories determined by silhouette scoring optimization: {% for c in a.venue_clusters.centroids %}"{{ c.label }}"{% if not loop.last %}, {% endif %}{% endfor %}.

## 10.3 Win-probability results
{{ tab("Holdout (2025–26) metrics with 95% bootstrap CIs") }}

| Tier | Model | Calibration | n | Log-loss | Brier | Accuracy | AUC | ECE |
|---|---|---|---|---|---|---|---|---|
{% for t, v in m.tiers.items() %}| {{ t }} | {{ v.selection.chosen }} | {{ v.calibration.chosen }} | {{ v.holdout.model.n }} | {{ v.holdout.model.log_loss | f(4) }} [{{ v.holdout.model.ci.log_loss.low | f(3) }}, {{ v.holdout.model.ci.log_loss.high | f(3) }}] | {{ v.holdout.model.brier | f(4) }} | {{ v.holdout.model.accuracy | pct }} [{{ v.holdout.model.ci.accuracy.low | pct }}, {{ v.holdout.model.ci.accuracy.high | pct }}] | {{ v.holdout.model.auc | f(3) }} [{{ v.holdout.model.ci.auc.low | f(2) }}, {{ v.holdout.model.ci.auc.high | f(2) }}] | {{ v.holdout.model.ece | f(3) }} |
{% endfor %}

{{ tab("Holdout comparison with every baseline (Δ = model − baseline log-loss; negative means the model is better)") }}

| Tier | Baseline | Baseline log-loss | Δ | 95% CI of Δ | P(model not better) | DM p |
|---|---|---|---|---|---|---|
{% for t, v in m.tiers.items() %}{% for b, c in v.holdout_vs_baselines.items() %}| {{ t }} | {{ b }} | {{ v.holdout[b].log_loss | f(4) }} | {{ c.diff | signed }} | [{{ c.ci_low | signed }}, {{ c.ci_high | signed }}] | {{ c.p_not_better | f(2) }} | {{ c.diebold_mariano.p_value | f(2) }} |
{% endfor %}{% endfor %}

<p class="callout"><b>Interpretation.</b> Across our historical walk-forward cross-validation splits, the chosen post-toss classifier (achieving log-loss {{ m.tiers.post_toss.selection.walk_forward_mean_log_loss | f(4) }}) consistently improved upon the uninformative coin flip baseline ({{ m.tiers.post_toss.baselines_walk_forward.B0_constant.mean_log_loss | f(4) }}) and the chase prior ({{ m.tiers.post_toss.baselines_walk_forward.B1_chase_prior.mean_log_loss | f(4) }}). However, when exposed to the untouched 2025–26 holdout dataset, <b>neither modeling tier maintained a statistical edge over a naive 0.5 coin-flip benchmark</b>, with confidence bounds remaining relatively wide given n = {{ m.tiers.post_toss.n_holdout }} games. Consistent with scientific integrity, we chose not to retroactively fiddle with hyperparameters to manufacture an artificial holdout gain. In recent seasons, home advantage has shifted dramatically—yielding win rates of {% for r in a.home_by_season if r.season_year >= 2023 %}{{ r.season_year }}: {{ r.home_win_rate | pct(0) }}{% if not loop.last %}, {% endif %}{% endfor %}, compared to {{ a.home_advantage.rate | pct(0) }} historically—indicating that historical statistical associations weakened considerably following the introduction of tactical substitution rules. Crucially, our automated leakage test was {{ "triggered" if m.tiers.post_toss.too_good_guard.suspicious else "not triggered" }}, demonstrating that our modest performance reflects the authentic boundary of pre-match predictability rather than hidden pipeline bugs.</p>

{{ fig("reports/figures/walk_forward_by_season.png", "Validation log-loss by season: chosen models against baselines", "90%") }}

{{ fig("reports/figures/holdout_vs_baselines_post_toss.png", "Post-toss holdout log-loss vs baselines (model bar with 95% CI)", "75%") }}

{{ fig("reports/figures/reliability_holdout.png", "Holdout reliability diagram (equal-mass bins)", "60%") }}

{{ tab("Cumulative feature-group ablation (post-toss logistic, walk-forward mean log-loss)") }}

| Feature groups | # features | Log-loss |
|---|---|---|
{% for r in m.tiers.post_toss.ablation %}| {{ r.groups }} | {{ r.n_features }} | {{ r.mean_log_loss | f(4) }} |
{% endfor %}

Ablation tracking demonstrates that virtually all marginal predictive gains stem from **toss decisions, batting sequence**, and **lineup continuity**, data points that only become visible minutes before the first ball. Distant historical head-to-head records contribute negligible predictive signal.

{{ fig("reports/figures/permutation_importance_post_toss.png", "Permutation importance of the post-toss model (development seasons)", "80%") }}

{{ tab("Validation log-loss by era and stage (time-ordered calibrated out-of-fold predictions, post-toss)") }}

| Segment | n | Log-loss | Accuracy |
|---|---|---|---|
{% for r in m.tiers.post_toss.oof_by_era %}| era: {{ r.era }} | {{ r.n }} | {{ r.log_loss | f(4) }} | {{ r.accuracy | pct }} |
{% endfor %}{% for r in m.tiers.post_toss.oof_by_stage %}| stage: {{ r.stage_group }} | {{ r.n }} | {{ r.log_loss | f(4) }} | {{ r.accuracy | pct }} |
{% endfor %}

## 10.4 First-innings score regression
{{ tab("First-innings runs, mean absolute error (MAE, runs)") }}

| Model | Walk-forward MAE | Holdout MAE [95% CI] | Holdout RMSE | Holdout bias |
|---|---|---|---|---|
{% for k in ["ridge", "hist_gb", "baseline_recent_league_mean", "baseline_venue_level"] %}| {{ k }} | {{ m.score_regression.walk_forward[k].mae | f(1) }} | {{ m.score_regression.holdout[k].mae | f(1) }} [{{ m.score_regression.holdout[k].mae_ci.low | f(1) }}, {{ m.score_regression.holdout[k].mae_ci.high | f(1) }}] | {{ m.score_regression.holdout[k].rmse | f(1) }} | {{ m.score_regression.holdout[k].bias | f(1) }} |
{% endfor %}

In practice, a straightforward rolling league average (tracking the preceding ~74 games) serves as a formidable target regressor because it rapidly assimilates the structural upward scoring drift characteristic of recent seasons. In contrast, historical venue-level baselines lag behind, showing substantial negative forecast bias. Neither regularized linear models nor gradient-boosted trees offered notable improvements over this simple rolling benchmark.

## 10.5 Drift
Population Stability Index (PSI) tracking quantifies how feature distributions in the newest season diverge from development eras. The most pronounced distributional divergences include:
{% for r in m.drift.table[:6] %}
- `{{ r.feature }}`: PSI {{ r.psi | f(2) }} ({{ r.status }}){% endfor %}

Features tracking first-innings run rates experienced severe distribution shifts after 2023. This regime change accounts for decreased holdout effectiveness and would naturally mandate model retraining in an operational deployment.
