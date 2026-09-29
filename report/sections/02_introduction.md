# 2. Introduction

## 2.1 Context
Twenty-over cricket is notoriously volatile. In a short match where a single dropped catch or a couple of clean hits can flip the result, enthusiasts, broadcast commentators, and analysts routinely debate key strategic factors:

- Does winning the pre-match coin toss genuinely tilt the odds of winning?
- Has chasing down targets under lights become an overwhelming advantage?
- How drastically did the 2023 Impact Player tactical substitution rule inflate first-innings scores?
- Can an algorithmic model reliably anticipate which team will come out on top before play begins?

While ball-by-ball and match-level records from {{ q.seasons | length }} seasons (encompassing {{ q.results.matches | int }} official fixtures since 2008) are publicly available, standard analyses often stumble over deceptive quirks in the underlying logs. More importantly, pre-game probability estimates that candidly acknowledge real-world uncertainty remain surprisingly rare in the sports analytics space.

## 2.2 What CreaseIQ is
CreaseIQ represents an end-to-end applied machine learning platform engineered directly from historical Indian Premier League match scorecards. Rather than stitching together ad-hoc scripts, the system is organised into five cohesive functional subsystems:

1. **Data engineering (M1):** Ingests, inspects, and standardises raw scorecard records into a clean relational database, recording every single transformation inside an inspectable quality ledger.
2. **Analytics & visualisation (M2):** Examines historical trends, team records, venue behaviours, and toss dynamics using formal hypothesis testing and confidence intervals, accessible through an interactive dashboard.
3. **Prediction engine (M3):** Computes pre-game win probabilities through strict *leakage-safe* temporal feature sets, walk-forward cross-validation, probability calibration, and local feature attribution.
4. **Scenarios (M4):** Provides an interactive "what-if" perturbation surface (evaluating venue shifts and toss decisions) alongside a Monte Carlo tournament simulation.
5. **Operations & reporting (M5):** Tracks system operations via structured run-keyed logs, maintains persistent inference audits, monitors population feature drift, and automates documentation and model card generation.

## 2.3 Objectives
Our practical implementation was guided by six key milestones:
1. Parse and validate the historical match repository, systematically isolating flawed entries while outputting an auditable data quality trail.
2. Structure all verified entities into a normalized third-normal-form SQLite repository capable of repeatable, idempotent builds.
3. Run statistically disciplined inference on toss outcomes, venue scoring tiers, franchise records, and rule changes with explicit uncertainty bounds.
4. Train pre-match win classifiers using strict temporal cutoffs to eliminate information leakage, evaluating models via walk-forward splits and calibrated outputs.
5. Deliver a practical, user-friendly Streamlit web interface and a companion Typer terminal interface, backed by thorough test suites.
6. Compile our technical decisions, empirical metrics, and architectural tradeoffs into a complete project deliverable matching course evaluation standards.

## 2.4 Relevance to the course
This project serves as a comprehensive capstone integrating the core themes of the AI and Machine Learning curriculum:

- **Data hygiene and preprocessing:** Declarative contract validation, handling structural renames, anomaly correction, and value imputation.
- **Exploratory analysis and inferential statistics:** Wilson score intervals, causal toss testing, two-sample Welch tests, and effect size measurement.
- **Feature representation:** As-of temporal state accumulation and sequential margin-weighted Elo rating dynamics.
- **Supervised classification and regression:** Regularized logistic models, tree ensembles (Random Forest, Histogram Gradient Boosting), and linear regularized score estimators.
- **Unsupervised clustering:** Grouping stadium scoring environments through k-means clustering.
- **Time-series validation rigor:** Expanding-window walk-forward validation, the one-standard-error heuristic, bootstrap intervals, and paired baseline tests.
- **Calibration and interpretability:** Sigmoid probability mapping, reliability analysis, and intuitive prediction driver breakdowns.
- **Engineering ethics:** Rigorous leakage detection, truthful reporting of modest predictive power, and clear disclaimers prohibiting betting usage.

In addition, foundational AI ideas find practical expression here: hyperparameter grid exploration functions as state-space search, YAML identity mappings operate as an explicit domain knowledge base, and the prediction coordinator functions as a discrete inference agent (mapped in detail in `docs/course_mapping.md`).

## 2.5 Structure of this report
The rest of this document walks through the project lifecycle: Sections 3 through 5 define the core data challenges alongside our functional and non-functional engineering requirements. Sections 6 to 8 outline the system architecture, UML design schematics, and key architectural decision records. Section 9 walks through implementation choices spanning data cleaning, Elo formulation, and model training. Section 10 reviews our experimental metrics alongside live application captures, followed by the verification framework in Section 11. Finally, Sections 12 through 14 reflect on practical development hurdles, personal technical takeaways, and proposed future expansions, concluding with references in Section 15.

<p class="callout"><b>Headline result.</b> CreaseIQ's most critical takeaway is one of scientific candour: predicting T20 cricket outcomes prior to the match is fundamentally close to tossing a coin. Our strongest walk-forward log-loss achieved {{ m.tiers.post_toss.selection.walk_forward_mean_log_loss | f(4) }}, compared against the uninformative 0.6931 baseline. When assessed on the untouched 2025–26 holdout dataset after model selections were permanently locked, no model systematically outperformed a baseline coin flip. As explored in Section 8, online projects touting 85% to 90% accuracy almost invariably suffer from subtle data leakage.</p>
