# Project statement: CreaseIQ

## Problem statement
Indian Premier League (IPL) data is rich but messy, and four problems follow from that.

**Inconsistent labels.** Franchises have been renamed (Delhi Daredevils → Delhi Capitals, Kings XI Punjab → Punjab Kings). One stadium can appear under several spellings, or under an old and a new name. Season labels are not plain years (`2007/08`, `2020/21`).

**Silent traps in the data.**
- Before 2018 the `team1` column does not mean "batting first". From 2018 onward it always does.
- Tied matches include super-over runs in their innings totals.
- One match that was voided and replayed looks like a washout.

**No trustworthy way to answer basic questions.** Students, analysts and fans have no clean, validated, reproducible dataset. Nor do they have a principled way to ask:
- Does winning the toss matter?
- Is chasing easier?
- Did the Impact Player rule change the game?
- How likely is team A to beat team B?

**Unreliable online predictors.** Many "IPL predictors" online report 80–90%+ accuracy. They reach those figures by leaking post-match information into features or by ignoring time order.

CreaseIQ addresses all of this with a validated data pipeline, statistically sound analytics with uncertainty, and a **leakage-safe, calibrated pre-match win-probability engine** that reports its real, modest accuracy honestly.

## Scope
**In scope**
- Ingest, validate, clean and canonicalise the supplied IPL match file (2008–2026).
- Validated uploads of new matches.
- A normalised relational database with idempotent rebuilds.
- Analytics: toss and chasing tests with confidence intervals, team records, head-to-head, venues (including k-means profiling), scoring eras and player-of-the-match leaders.
- Win probability in two tiers (pre-toss and post-toss). It uses walk-forward validation, calibration, explanations and a one-shot holdout.
- First-innings score regression, what-if scenarios and a hypothetical season simulation.
- A Streamlit dashboard, a Typer CLI, tests, CI, documentation and a PDF report.

**Out of scope**
- Ball-by-ball or live in-play prediction.
- Betting odds or betting advice.
- Player-level batting and bowling statistics (not in the data).
- User accounts or multi-user authentication. It is a single-user local app, so the data contains nothing personal to protect beyond public match records.

## Target users
1. **Students and analysts** exploring IPL data who want clean data and statistically honest answers.
2. **Cricket fans** who want evidence-based match previews and "what if" explorations.
3. **Maintainers and data engineers** who extend the pipeline with new seasons or sources.

## High-level features
- **Data engineering (M1):**
  - Schema-validated ingest with a quarantine file.
  - Fail-loud canonicalisation, with 60 venue strings mapped to 37 venues and 19 team strings to 15 franchises.
  - Correction of super-over contamination and D/L flags.
  - An auto-generated data-quality report and data dictionary.
  - A SQLite store in 3NF.
- **Analytics and visualisation (M2):**
  - A causal toss test with its minimum detectable effect.
  - Chasing advantage and era tests.
  - Venue shrinkage and clustering.
  - Head-to-head records and Elo history.
  - An interactive dashboard with sanitised CSV export.
- **Prediction engine (M3):**
  - As-of features protected by automated leakage tests.
  - Margin-aware Elo.
  - Five model families, compared with walk-forward CV and a one-SE selection rule.
  - Time-ordered calibration.
  - Bootstrap CIs and paired tests against baselines.
  - A hash-verified model registry.
  - Plain-English prediction drivers.
- **Scenarios (M4):** a what-if tornado (toss, venue, opponent) and a Monte Carlo season simulation.
- **Operations and reporting (M5):**
  - Structured logs with run ids and a prediction log.
  - A PSI drift monitor.
  - A generated model card, figures and NFR evidence.
