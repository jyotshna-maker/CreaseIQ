# 8. Design Decisions & Rationale

Non-obvious decisions are recorded as Architecture Decision Records (ADRs) in `docs/decisions/`. Each ADR gives the context, the options considered, the decision and its consequences. They are summarised below.

{{ tab("Architecture decision records") }}

| ADR | Decision | Why |
|---|---|---|
| 001 Course relevance | ML core, with AI fundamentals mapped explicitly; adds k-means venue profiling | An irrelevant project scores 0; the syllabus covers agents, search and knowledge representation as well as ML |
| 002 Stack | Python ≥ 3.12; scikit-learn only; Playwright for PDFs | numpy 2.5 and scipy 1.18 dropped 3.11; avoids native OpenMP and GTK installs on Windows |
| 003 Franchise continuity | Renames share one id; new owner or contract means a new franchise | Legally correct; fixes title counts and head-to-head; sensitivity documented |
| 004 Data corrections | Correct ties with regulation scores, flag voided and D/L rows; never quarantine them | Keeps 16 real matches; the raw values stay available for audit |
| 005 Orientation & symmetry | Hash-seeded coin flip per match; declared antisymmetric features; symmetrised predictions | Raw `team1` order leaks batting order from 2018 |
| 006 Selection, calibration, holdout | Walk-forward CV; one-SE rule; time-ordered calibration; hashed one-shot holdout with a ledger | Prevents overfitting noise and silent re-use of the holdout |

## 8.1 The orientation trap (ADR-005)
A classifier needs a target such as "does team A win?", so every match must be oriented. The obvious choice, raw `team1` as A, is wrong. From 2018 onward `team1` is always the side batting first, and batting first wins only {{ q.results.bat_first_win_rate | pct }} of decided matches. A model trained on that orientation would learn batting order through a side channel, even in the pre-toss tier.

CreaseIQ handles this in four steps:

1. Each match is oriented by a SHA-256-seeded coin flip on its own date and teams, so deleting other matches cannot change it.
2. Every feature is declared *antisymmetric* (a difference or ±1 flag) or *symmetric context* (venue, stage, era).
3. The logistic model has no intercept and uses only antisymmetric features. That makes it exactly symmetric: p(A,B) = 1 − p(B,A).
4. Tree models are symmetrised at prediction time, and a test checks invariance to 1e-9.

## 8.2 Leakage-safe features ("as-of")
Features are built by one incremental state machine that processes matches in **date batches**. Every match on a date is featurised from the state *before* that date, and the state is updated only after the whole date. Same-day double-headers therefore never see each other. Five automated tests guard this (Section 11): future deletion, future mutation, same-day isolation, label shuffle, and the column allow-list.

## 8.3 Why walk-forward, the one-SE rule and log-loss
Random k-fold would train on future seasons. The IPL is non-stationary (auctions, the Impact Player rule, neutral seasons), and Cerqueira et al. recommend time-ordered out-of-sample evaluation for such series [11]. CreaseIQ therefore validates each development season 2012–{{ m.splits.dev_last_season }} with a model trained on all earlier seasons.

With only about 1,000 development matches, the gaps between models are small. The *one-standard-error rule* picks the simplest model within one SE of the best mean. The primary metric is **log-loss**, a proper scoring rule. Accuracy ignores confidence, and selecting on calibration is known to be more useful than selecting on accuracy [9].

## 8.4 Calibration choice
The candidates are none, Platt (sigmoid) and isotonic. Each is evaluated in time order: the calibrator for season S is fitted only on out-of-fold predictions from earlier seasons. Isotonic regression overfits below about 1,000 calibration points [12], [13], and the result confirmed it here:

| Tier | none | sigmoid | isotonic | Chosen |
|---|---|---|---|---|
{% for t, v in m.tiers.items() %}| {{ t }} | {{ v.calibration.comparison.none.mean | f(4) }} | {{ v.calibration.comparison.sigmoid.mean | f(4) }} | {{ v.calibration.comparison.isotonic.mean | f(4) }} | **{{ v.calibration.chosen }}** |
{% endfor %}

## 8.5 One-shot holdout with a ledger
2025–26 is the holdout. Before it is touched, the selection is frozen: model, parameters, calibration, Elo settings, feature list and data hash are hashed into a selection id. The id is logged in `reports/holdout_ledger.json`, which counts every evaluation.

Re-running the same frozen selection recomputes identical numbers. Evaluating a *different* selection would be flagged as holdout re-use. ADR-006 also discloses that the ledger file was reset once after an exploratory run of the same selection.

## 8.6 Other decisions
- **SQLite vs a server database:** zero administration for a single-user app; PostgreSQL remains one URL away (NFR-08).
- **Streamlit:** a Python-only UI, with `AppTest` for automated UI tests.
- **Correct, don't quarantine:** anomalies with a verifiable explanation are corrected. Unknown values fail loudly instead of being guessed.
- **Causal vs associational toss analysis:** the toss is randomised, so "toss winner wins" is a valid causal test. The bat/field *decision* is post-treatment, so tests conditioned on it are labelled associational [2].
- **Shrinkage:** venue and team-at-venue rates are pulled toward league values, so venues with few matches are not over-interpreted.
