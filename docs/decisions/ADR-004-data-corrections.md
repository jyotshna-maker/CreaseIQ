# ADR-004: Correcting ties, voided matches and D/L results instead of quarantining them

- **Status:** Accepted, 2026-09-29
- **Context:** Phase 0 research (R8) found three systematic problems in the raw CSV:
  1. **Ties.** All 16 tied rows add the super-over runs and wickets into the innings totals. One row adds two super overs. This is why a side appears to lose 12 wickets. The `winner` column is empty for ties.
  2. **Voided match.** The 08-05-2025 PBKS v DC game was abandoned because of a security blackout and then replayed in full at another ground. It appears as an ordinary "no result".
  3. **D/L results.** Rain-affected (D/L) results give margins that contradict the batting order, and totals where the winner scored fewer runs than the loser. Only some D/L matches show these symptoms.

  The plan said to "flag, quarantine, log" the anomalies. Quarantining would drop 16 real, informative matches from analytics and still leave every other tie contaminated.

## Options

1. Quarantine the anomalous rows.
2. Correct them in the cleaning step, using verified external facts, and keep the raw values for audit.
3. Leave them as they are and document the problem.

## Decision

We chose option 2.

- `data/external/super_over_winners.csv` records the regulation tied score and the super-over winner for each tie, with two sources each.
  - `first_innings_runs` and `second_innings_runs` are set to the regulation score.
  - Regulation wickets cannot be separated from super-over wickets in the source, so the wicket columns are set to null for ties.
  - The raw `team*_runs` and `team*_wickets` columns are kept for audit.
- Voided matches are listed in `configs/config.yaml` and flagged `voided`. They are excluded from scoring stats through `scores_usable`.
- `dls_flag = dls_heuristic OR dls_external`.
  - The heuristic flags 14 rows. In the years the external list covers, every flagged row is confirmed by it.
  - The external list adds D/L results the heuristic cannot see, giving 19 flagged rows in total.
- Validation allows more than 10 wickets **only** on tie rows. On any other row it is still an error.

## Consequences

- The real file validates with **0 quarantined rows**, and every change is counted in the data-quality report.
- Ties are still excluded from the classification target (n = 1,218 decided matches). `super_over_winner` is used only for descriptive analytics.
- Subsets of the data, such as the test fixture or user uploads, may lack some reference rows. Unmatched external records become notes rather than errors, and a test asserts there are none for the full dataset.
