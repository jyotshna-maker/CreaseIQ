# ADR-005: Match orientation, antisymmetric features and symmetrised predictions

- **Status:** Accepted, 2026-09-29
- **Context:** A classifier needs a "team A wins?" target, so each match needs an orientation. The raw `team1`/`team2` order is **not** neutral:
  - From 2018 onward `team1` is always the side batting first.
  - Batting first wins only 45.3% of the time.
  - A model trained on raw order would therefore learn batting order through a side channel, and would even do so in the pre-toss tier.

  A test documents this artefact: raw team1 wins under 48% of the time from 2018.

## Options

1. Use the raw order as it stands.
2. Order the teams alphabetically by `franchise_id`.
3. Flip a seeded coin for each match.
4. Use both orientations for every match, duplicating the rows.

## Decision

Option 3, with the rest of the design built around it:

- **Coin flip.** Each match's flip is `sha256(seed | date | sorted teams)`. It depends only on the match itself. Deleting or changing other matches cannot change it, which the future-perturbation test relies on. Alphabetical order was rejected because it ties orientation to franchise identity: CSK would always be A against MI.
- **Feature types.** Every feature is declared as either *antisymmetric* or *symmetric context*:
  - Antisymmetric features are A − B differences and ±1 flags. They change sign when A and B are swapped.
  - Symmetric context (venue, stage, era) is the same from either side.
  - A test computes (B, A) directly and checks it equals the declared swap of (A, B) for every feature.
- **Inference is symmetrised:** `p = ½ [ p(A,B) + 1 − p(B,A) ]`. The answer therefore cannot depend on which team the user typed first, and a test checks invariance to 1e-9.
- Option 4 was rejected: duplicating rows doubles n artificially, which misleads bootstrap CIs and some learners.

## Consequences

- A test checks that the orientation flag alone has no predictive signal (its bootstrap AUC CI contains 0.5).
- In a linear model, symmetric-context features act only as a shift in the intercept, and symmetrisation cancels that shift. They carry information only through interactions: tree models, and the explicit `bats_first_x_venue` and `bats_first_x_impact` terms.
