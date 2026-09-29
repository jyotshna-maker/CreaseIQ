# 8. Design Decisions & Rationale

Key architectural tradeoffs and non-trivial engineering choices are captured as Architecture Decision Records (ADRs) within `docs/decisions/`. Documenting the context, alternatives evaluated, chosen strategy, and practical consequences prevents architectural regressions. A synthesis of these records is presented below:

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
Binary classification requires a directional prediction target—in our case, estimating $P(\text{team } A \text{ defeats team } B)$. In domestic football leagues, setting Team A as the home team provides a natural, physically meaningful frame of reference. In tournament cricket, however, neutral venues, double-headers, and playoff games mean neither side is necessarily "at home". 

The naive shortcut—designating whatever franchise appears in the raw `team1` column as Team A—introduces a critical data leakage bug. In the historical raw records, `team1` corresponds to the side batting first in every single fixture from the 2018 season onward, whereas in pre-2018 seasons, the listing was arbitrary (ranging between 45% and 62% bat-first). Because the side setting a target wins only {{ q.results.bat_first_win_rate | pct }} of completed matches across league history, any classifier presented with raw `team1` as Team A inadvertently learns batting order long before the actual coin toss takes place.

To solve this, CreaseIQ enforces mathematical symmetry through four safeguards:

1. **Independent coin-flip assignment:** Each fixture is assigned Team A and Team B via an isolated SHA-256 hash computed on that fixture's date and participating team IDs.
2. **Antisymmetric feature formulation:** Predictive metrics (such as Elo differences or form deltas) are defined antisymmetrically as $f(A, B) = -f(B, A)$, while environmental context (venue, tournament stage) is marked as symmetric.
3. **Intercept-free linear models:** By stripping the intercept term and utilizing purely antisymmetric features in our logistic classifier, the model guarantees exact mathematical symmetry: $P(A \text{ beats } B) = 1 - P(B \text{ beats } A)$.
4. **Symmetrized inference for tree ensembles:** For non-linear models where symmetry cannot be proven analytically, predictions at inference time average $P(A, B)$ with $1 - P(B, A)$, verified to within $10^{-9}$ tolerance by automated unit tests.

## 8.2 Leakage-safe features ("as-of")
To prevent future data from contaminating historical training sets, all feature extraction runs through an incremental state machine operating strictly on **date batches**. When computing metrics for games played on date $T$, the feature builder only has access to tournament history accumulated *strictly before* $T$. All updates (updating Elo ratings, recording runs scored, or incrementing encounter histories) occur only after all fixtures on date $T$ have been featurized. Consequently, double-header fixtures played on the same afternoon cannot leak outcomes to evening matches. Five adversarial tests safeguard this contract: future deletion, future mutation, same-day isolation, label shuffling, and strict column allow-lists.

## 8.3 Why walk-forward, the one-SE rule and log-loss
Applying standard shuffled k-fold cross-validation to athletic time series violates temporal reality: models end up training on modern batting strike rates to predict matches from 2010. Furthermore, the IPL evolves across distinct eras marked by mega-auctions, new franchise expansions, and systemic rule adjustments like the Impact Player rule. Following established econometric guidelines for non-stationary series [11], we employ an expanding-window walk-forward validation strategy from 2012 through development season {{ m.splits.dev_last_season }}, evaluating every season strictly on models trained exclusively on preceding tournaments.

Given our sample size of roughly 1,000 historical training contests, empirical differences in mean cross-validation loss across architectures are modest. We therefore apply the **one-standard-error rule** (one-SE): selecting the simplest, most regularized model whose validation loss falls within one standard error of the numerical minimum. The primary optimization metric is **log-loss** (cross-entropy). Classification accuracy discards confidence and calibration, whereas optimizing for calibrated log-loss ensures that an estimated 65% probability reflects an authentic 65% long-run win rate [9].

## 8.4 Calibration choice
Raw model outputs rarely represent true probabilities. We tested three calibration techniques: uncalibrated outputs, Platt scaling (logistic sigmoid), and non-parametric isotonic regression. Crucially, calibration was evaluated in strict temporal order: calibrators for season $S$ were trained exclusively on out-of-fold historical predictions prior to $S$. As documented in statistical literature, isotonic regression tends to overfit on smaller calibration sets under 1,000 observations [12], [13]. Our empirical validation confirmed this behavior:

| Tier | none | sigmoid | isotonic | Chosen |
|---|---|---|---|---|
{% for t, v in m.tiers.items() %}| {{ t }} | {{ v.calibration.comparison.none.mean | f(4) }} | {{ v.calibration.comparison.sigmoid.mean | f(4) }} | {{ v.calibration.comparison.isotonic.mean | f(4) }} | **{{ v.calibration.chosen }}** |
{% endfor %}

## 8.5 One-shot holdout with a ledger
The 2025 and 2026 seasons were set aside as a true out-of-sample holdout test. To prevent iterative "holdout snooping"—where an engineer repeatedly tweaks features until holdout performance looks appealing—the entire model configuration was frozen and hashed before running holdout inference. The SHA-256 fingerprint encompasses selected algorithms, hyperparameters, calibration parameters, Elo settings, and training data hashes.

Each holdout evaluation is tracked within `reports/holdout_ledger.json`. Re-running the fixed pipeline simply regenerates verified numbers, whereas modifying features or hyperparameters while pointing at the holdout raises an explicit ledger warning. ADR-006 transparently discloses that this tracking file was reset once during initial exploratory pipeline stabilization.

## 8.6 Other decisions
- **SQLite embedded database:** Opting for SQLite eliminated external database management dependencies on student machines while preserving the option to redirect to PostgreSQL simply by changing the database connection string (NFR-08).
- **Streamlit web framework:** Selected because it allows creating interactive dashboards purely in Python, and importantly, supports headless UI testing through Streamlit's official `AppTest` test runner.
- **Auditable correction over data quarantine:** When records contain known, explainable historical quirks (such as super-over runs included in tied matches), we repair the values using verified external match sheets rather than discarding real games. Unrecognized values, however, fail loudly.
- **Causal vs associational toss framing:** The initial coin toss is an idealized random experiment, making "toss winner win rate" a valid causal inquiry. Conversely, a captain's subsequent decision to bat or field is conditioned on pitch dampness, dew forecasts, and lineup construction, making decision-based breakdowns strictly associational [2].
- **Empirical Bayesian shrinkage:** Raw venue averages and team-ground win rates are shrunk toward league-wide priors using pseudo-counts, preventing extreme percentages from misleading the model on grounds that have hosted only one or two games.
