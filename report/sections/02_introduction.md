# 2. Introduction

## 2.1 Context
The Indian Premier League (IPL) is the world's most-watched T20 cricket competition. Since 2008 it has produced {{ q.results.matches | int }} matches over {{ q.seasons | length }} seasons, and every one has a public scorecard. Fans, journalists and analysts argue about the same questions each season:

- Does winning the toss decide the match?
- Is chasing easier?
- Did the 2023 *Impact Player* rule change the game?
- Can anyone predict who will win?

The data needed to answer them exists, but it is messy. Answers that are both statistically sound and honest about their uncertainty are rare.

## 2.2 What CreaseIQ is
CreaseIQ is a complete machine-learning project built on the supplied IPL match file. It has five functional modules:

1. **Data engineering (M1).** Validates, cleans and canonicalises the raw file into a normalised relational database, and records every correction in an auditable quality report.
2. **Analytics & visualisation (M2).** Answers the questions above with proper statistical tests and confidence intervals, through an interactive dashboard.
3. **Prediction engine (M3).** Estimates pre-match win probabilities with *leakage-safe* features, time-ordered validation, calibration and baselines, and explains each prediction.
4. **Scenarios (M4).** What-if analysis (toss, venue, opponent) and a Monte Carlo season simulation.
5. **Operations & reporting (M5).** Structured logging, a prediction log, drift monitoring and generated evidence (model card, figures, NFR verification).

## 2.3 Objectives
1. Ingest, validate, clean and canonicalise the dataset, with an auditable quality report.
2. Store it in a normalised schema with reproducible, idempotent rebuilds.
3. Provide statistically sound analytics (toss, venue, team and era effects) that report their uncertainty.
4. Predict match outcomes with leakage-safe features, walk-forward validation, calibrated probabilities and explanations.
5. Offer an accessible dashboard and CLI with logging, monitoring and thorough test coverage.
6. Document the design and results against the assignment's artefact list.

## 2.4 Relevance to the course
The project is an end-to-end application of machine learning. It covers:

- **Data preprocessing:** schema validation, anomaly correction, imputation.
- **Exploratory and inferential statistics.**
- **Feature engineering:** including sequential Elo ratings.
- **Supervised classification and regression:** logistic regression, random forests, gradient boosting and ridge regression.
- **Unsupervised learning:** k-means venue clustering.
- **Model selection and evaluation for time-ordered data:** walk-forward CV, the one-standard-error rule, bootstrap confidence intervals and paired tests.
- **Probability calibration and interpretability.**
- **ML ethics:** data leakage, honest reporting, a betting disclaimer.

The AI-fundamentals topics of the VITyarthi course are also mapped explicitly. Hyperparameter search is treated as heuristic search, the YAML identity rules as a knowledge base, and the prediction service as a simple agent. `docs/course_mapping.md` maps each topic to its implementing file and test.

## 2.5 Structure of this report
Sections 3–5 define the problem and the functional and non-functional requirements. Sections 6–8 present the architecture, the design diagrams and the reasoning behind each design decision. Section 9 details the implementation: dataset, cleaning, features, model selection and evaluation methodology. Section 10 shows the results and real screenshots, and Section 11 the testing approach. Sections 12–14 reflect on challenges, learnings and future work, and Section 15 lists the references.

<p class="callout"><b>Headline result.</b> CreaseIQ's most important finding is honest: pre-match IPL outcomes are close to a coin flip. The best walk-forward log-loss is {{ m.tiers.post_toss.selection.walk_forward_mean_log_loss | f(4) }}, against 0.6931 for a coin. On the 2025–26 holdout, which was evaluated once, no model beat the coin. Online "predictors" that claim 80–90% accuracy are almost always leaking information (Section 8).</p>
