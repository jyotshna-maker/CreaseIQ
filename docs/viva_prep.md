# Viva preparation: defend every line

The numbers quoted in answers come from `reports/metrics.json`, `reports/analytics.json` and `docs/data_quality_report.md`. Open those files during the viva rather than memorising figures.

## 1. The 60-second pitch
IPL data looks clean but hides traps:
- Renamed franchises.
- 60 spellings of 37 venues.
- A `team1` column that means "batting first" only from 2018.
- Tie rows that secretly include super-over runs.

CreaseIQ finds and fixes these traps with an auditable pipeline, stores the result in a normalised database, and answers questions with proper statistics. The toss has no detectable effect; chasing does have a small advantage.

It then builds a win-probability model the *right* way:
- no information from the future;
- no bias from which team is listed first;
- time-ordered validation, calibration and baselines;
- a holdout that is evaluated once.

The honest result is that pre-match IPL outcomes are close to a coin flip, and the project proves that rather than hiding it.

## 2. Module walkthrough

| Module | Explain in one breath | Key file to open |
|---|---|---|
| Data source and validation | Hash-check the raw CSV. A pandera schema checks types and allowed values; 9 vectorised row rules check cross-column logic. Lenient mode quarantines rows with reasons; strict mode raises. | `data/schema.py`, `data/ingest.py` |
| Canonicalisation | YAML knowledge base: alias → franchise with validity years, and venue alias → canonical venue. Unknown names raise errors instead of passing silently. | `data/canonical.py`, `configs/*.yaml` |
| Cleaning | Batting order from the toss; regulation scores for ties; voided and D/L flags; era-specific playoff stages; champions verified against ground truth. | `data/cleaning.py` |
| Database | 3NF schema, dimension upserts, fact refresh inside one transaction, and views. All SQL is parameterised. | `db/models.py`, `db/loader.py` |
| Analytics | Pure functions returning DataFrames; every rate has a CI. | `analytics/toss_analysis.py` |
| Features | State is updated one date batch at a time. Each match only sees earlier dates. | `features/builder.py` |
| Elo | Expected score from the rating gap; K × margin multiplier × (actual − expected); regression toward 1500 each season. | `features/elo.py` |
| Models | 5 families, walk-forward CV, one-SE rule, time-ordered calibration. | `models/train.py`, `models/experiment.py` |
| Registry | joblib bundle plus SHA-256; the hash is verified before loading. | `models/registry.py` |
| Serving | Validate against allow-lists → state as of the date → symmetric prediction → calibration → drivers → log. | `services/prediction_service.py`, `models/predict.py` |
| Dashboard | 7 Streamlit pages that call services only. | `app/` |

## 3. Likely questions and answers

**Data**
1. *Where does the data come from?* The CSV mirrors the `info` section of Cricsheet's JSON format. It has 1,243 IPL matches, the same count Cricsheet lists, and is licensed ODC-BY 1.0. It probably reached us through a Kaggle repackaging (research R5).
2. *Why never use `team1`/`team2` order?* Before 2018 the order is effectively random. From 2018 `team1` always bats first, and batting first loses more often. A model would learn "team1 loses", which is a leak of batting order. `test_raw_team1_order_would_leak_batting_order` documents this.
3. *What was wrong with tied matches?* The totals include super-over runs, which is why one side shows 12 wickets. We restore the regulation score from a verified external table with two sources per tie (ADR-004).
4. *Why not quarantine those rows?* That would drop 16 real matches, and the other ties would still be contaminated. Correcting them keeps the data, and the raw values stay available for audit.
5. *How do you detect D/L matches?* Two signals: (a) the margin contradicts the batting order, or the winner scored fewer runs; (b) a verified list. The heuristic alone misses D/L chases "won by N wickets".
6. *What is the voided match?* PBKS v DC on 08-05-2025 was stopped by a security blackout and replayed in full elsewhere. It is flagged and excluded from scoring stats.
7. *Why are Deccan Chargers and Sunrisers Hyderabad separate?* They have different owners and a new franchise contract, so they are legally different teams (ADR-003).
8. *How do you know the cleaning is correct?* Tests check that all 19 derived champions match published results, that there are 74 playoff fixtures with era-correct labels, that base rates are right, and that every alias maps.

**Statistics**
9. *Does the toss matter?* No detectable effect. The toss winner's rate is close to 50% and the 95% CI includes 50% (`docs/analytics_findings.md`).
10. *Why is that test causal?* The toss is random. Randomisation makes a simple comparison of winners against losers an unbiased estimate of its effect.
11. *Then why not test "field first wins more"?* The decision is made after the toss and depends on conditions and team strength. Conditioning on it gives an association, not a cause (Sood & Willis 2016).
12. *What is the minimum detectable effect?* It is the smallest true effect the sample would detect with 80% power at α = 0.05. It shows a non-significant result means "smaller than about 4 pp", not "zero".
13. *Why Wilson intervals?* They behave better than the normal-approximation interval for proportions, especially near 0/1 and at small n.
14. *Why Holm correction for venues?* Many venue tests inflate false positives. Holm controls the family-wise error rate.
15. *What is shrinkage?* `(successes + m·prior)/(n + m)`. It pulls small-sample venues toward the league value, like a Bayesian prior worth m matches.

**Machine learning**
16. *What is data leakage, and how do you prevent it?* Leakage means training on information that would not be available at prediction time. We prevent it in five ways:
    - features are built in date batches from the past only;
    - a column allow-list excludes post-match fields;
    - a future-perturbation test deletes or mutates future matches and requires identical past features;
    - a same-day test;
    - a label-shuffle test.
17. *Why walk-forward instead of k-fold?* The data is a time series with regime changes. Random folds would train on the future, and Cerqueira et al. (2020) favour out-of-sample time-ordered evaluation for non-stationary series.
18. *What is the one-standard-error rule?* Choose the simplest model whose CV error is within one SE of the best. It avoids picking a model that won by noise.
19. *Why log-loss as the primary metric?* It scores the probabilities themselves, is a proper scoring rule, and rewards calibration. Accuracy ignores confidence.
20. *What does calibration mean?* Among predictions of 60%, about 60% should come true. We compare none, Platt and isotonic in time order. With under about 1,000 points isotonic overfits (Niculescu-Mizil & Caruana 2005).
21. *Why is the logistic model fitted without an intercept?* All its features change sign when A and B swap. With no intercept the logit is an odd function, so p(A,B) = 1 − p(B,A) exactly.
22. *How are the tree models made symmetric?* Prediction averages p(A,B) and 1 − p(B,A) (ADR-005). A test checks invariance to 1e-9.
23. *How was Elo tuned?* A grid over K, home bonus, season regression and margin on/off, scored by walk-forward log-loss on development seasons only.
24. *What are the baselines, and why?* Coin flip, chase prior, toss winner, Elo probability and venue chase rate. A model is only useful if it beats simple rules, checked with paired tests.
25. *Why is the holdout "evaluated once", and how can we trust that?* The selection is frozen and hashed before evaluation, and every evaluation is counted in `reports/holdout_ledger.json`. ADR-006 discloses one exploratory recomputation of the same frozen selection.
26. *Your model is worse than a coin on 2025–26. Is the project a failure?* No. That is the honest result. The CIs overlap the coin flip, and the pre-2023 patterns weakened: home sides won only about 40% in 2023 and 2025. Claiming 80% would require leakage. The project's value is the method.
27. *What would you check if the AUC were 0.9?* Assume leakage: post-match columns, future data in aggregates, random splits, orientation. The "too good" guard warns above AUC 0.72.
28. *What is the paired bootstrap?* Resample matches, recompute the mean difference in per-match log-loss between the model and a baseline, and read the CI of that difference. Pairing removes shared noise.
29. *What is the Brier decomposition?* Brier ≈ reliability − resolution + uncertainty. It separates miscalibration from discrimination.
30. *Why is ECE only descriptive?* Binned ECE is biased at small n and sensitive to the binning. We use equal-mass bins and do not select models on it.
31. *How do you explain a prediction?* For the linear model, each feature contributes `coef × x / scale` to the log-odds. The contributions sum to the logit, and the top three become a sentence.
32. *What is PSI, and what did it show?* The Population Stability Index compares feature distributions. Scoring features drift strongly in the Impact Player era, which warns that the training data no longer resembles current play.
33. *What unsupervised learning is used?* k-means on shrunk venue profiles, with k chosen by silhouette. It is descriptive only and never a model input.
34. *What is the score regressor, and is it useful?* Ridge and gradient boosting predict first-innings runs. It barely beats a recent-league-mean baseline, and we say so.

**Engineering**
35. *Why a layered architecture?* One implementation of each use case serves both the CLI and the UI, and the domain is testable without the UI. The layering is enforced by import-linter and an AST test.
36. *How is SQL injection prevented?* SQLAlchemy Core with bound parameters, plus an AST test that bans f-string or concatenated SQL. Injection strings are tested as inert.
37. *Why verify the model file's hash?* joblib uses pickle, which can execute code. We load only the file whose SHA-256 matches our own registry.
38. *How are uploads kept safe?* CSV only, at most 5 MB, UTF-8, exact columns, strict validation (all-or-nothing), dedup, a dry-run canonicalisation, an atomic write, and a rollback on failure. The raw file is never touched.
39. *How reproducible is it?* Seeds, pinned versions, config files and hash-seeded orientation. The test suite runs the experiment twice and compares the metrics.
40. *What is the evidence for performance?* `creaseiq benchmark` writes `reports/perf.json`: pipeline time, prediction latency, page render time and memory. All targets pass.

## 4. Limitations to state before being asked
- Small n. The holdout has about 140 matches, so CIs are wide.
- No player-level or ball-by-ball data. Injuries, pitch, dew and weather are not modelled.
- Structural breaks: the Impact Player rule, auctions, neutral seasons.
- Player identity is exact-string only (one known ambiguous name). D/L coverage is incomplete in three seasons.
- Home-ground lists are curated by hand from research.

## 5. Future work
- Ball-by-ball Cricsheet data for in-play win probability and player ratings.
- Squad-strength features from auctions.
- Bayesian hierarchical models.
- A REST API, authentication for multi-user use, and cloud deployment.
