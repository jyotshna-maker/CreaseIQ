# Course mapping: Machine Learning / Fundamentals of AI & ML

The student confirmed the course as *Machine Learning*. The VITyarthi flipped course cited by other submissions is *Fundamentals of AI & ML* (CSA2001). Its public outline was used where the official syllabus was unavailable (research R1, ADR-001). If `docs/assignment/syllabus.txt` is added, this table should be re-keyed to its exact unit names.

| Syllabus topic | Where it is demonstrated | Key files | Evidence (tests / outputs) |
|---|---|---|---|
| **Data collection & preprocessing** | Schema validation, cleaning, canonicalisation, handling of anomalies (super-over contamination, D/L, voided matches), missing-value imputation (cities) | `data/schema.py`, `data/ingest.py`, `data/cleaning.py`, `data/canonical.py` | `tests/unit/test_ingest.py`, `test_cleaning.py`, `docs/data_quality_report.md` |
| **Exploratory data analysis** | Distributions, trends, era comparisons, venue profiles | `analytics/*`, `notebooks/01_eda.ipynb` | `docs/analytics_findings.md`, `reports/analytics.json` |
| **Statistical inference** | Exact binomial and Wilson CIs, two-proportion z-test, χ² with Cramér's V, Welch t / Mann-Whitney, Holm correction, minimum detectable effect, shrinkage estimators | `analytics/hypothesis_tests.py`, `analytics/toss_analysis.py` | `tests/unit/test_hypothesis_tests.py` (cross-checked against statsmodels) |
| **Feature engineering** | As-of rolling form, head-to-head, venue effects, squad experience; antisymmetric feature design | `features/*` | `tests/unit/test_features.py`, `tests/validation/test_leakage.py` |
| **Rating systems / online learning** | Margin-aware Elo with season regression (sequential updates) | `features/elo.py` | Hypothesis property tests (zero-sum, monotone) |
| **Supervised learning: classification** | Logistic regression (L2), random forest, gradient boosting, blending | `models/train.py` | `reports/metrics.json` (model grid) |
| **Supervised learning: regression** | Ridge and gradient-boosted first-innings score regression | `models/score_regressor.py` | `metrics.json["score_regression"]` |
| **Unsupervised learning** | k-means venue clustering, with k chosen by silhouette | `analytics/venue_clusters.py` | `tests/unit/test_analytics.py::test_venue_clusters_are_deterministic` |
| **Model evaluation & selection** | Walk-forward (time-series) CV, one-SE rule, baselines, log-loss, Brier decomposition, AUC, ECE, bootstrap CIs, paired bootstrap, Diebold–Mariano | `models/splits.py`, `models/evaluate.py`, `models/experiment.py` | `tests/unit/test_models.py`, `docs/model_card.md` |
| **Bias–variance / regularisation / overfitting** | L2 strength search, tree depth and leaf limits, one-SE rule, locked holdout with ledger | `models/train.py`, `models/experiment.py` | `reports/holdout_ledger.json` |
| **Probability calibration** | Platt vs isotonic vs none, fitted in time order | `models/calibrate.py` | `metrics.json["tiers"][…]["calibration"]` |
| **Data leakage & validation design** | as-of contract, date batches, column allow-list, label-shuffle, orientation test | `features/builder.py` | `tests/validation/test_leakage.py` |
| **Interpretability** | Permutation importance, exact logistic contributions, plain-English drivers | `models/explain.py` | `reports/figures/permutation_importance_post_toss.png` |
| **Search & optimisation (AI fundamentals)** | Grid / heuristic search over the Elo hyperparameter landscape and model grids, scored by validation loss | `models/elo_tuning.py`, `models/train.py` | `metrics.json["elo_tuning"]` |
| **Knowledge representation (AI fundamentals)** | Declarative YAML knowledge base (franchise lineage with validity windows, venue aliases, home grounds) plus rule-based validation | `configs/*.yaml`, `data/schema.py` `ROW_RULES` | `tests/unit/test_canonical.py` |
| **Intelligent agents (AI fundamentals)** | `PredictionService` as a simple PEAS agent. **Performance:** log-loss. **Environment:** the IPL match context. **Actuators:** probability and explanation. **Sensors:** the validated request plus history. | `services/prediction_service.py` | `tests/unit/test_services.py` |
| **Simulation** | Monte Carlo season simulation | `simulation/season_monte_carlo.py` | `tests/unit/test_services.py::test_monte_carlo_logic` |
| **Ethics & responsible AI** | Honest reporting of weak results, betting disclaimer, limitations, data attribution, AI-assistance statement | `docs/model_card.md`, `README.md` | `docs/decisions/ADR-006-…` |
| **ML engineering / MLOps** | Model registry, drift monitoring (PSI), reproducible pipelines, CI | `models/registry.py`, `reporting/drift.py`, `.github/workflows/ci.yml` | `tests/validation/test_experiment.py::test_reproducible_metrics` |
