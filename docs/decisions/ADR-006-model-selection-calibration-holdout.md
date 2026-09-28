# ADR-006: Model selection, calibration and the one-shot holdout protocol

- **Status:** Accepted, 2026-09-29
- **Context:** The data give about 1.2k decided matches, and the predictive signal is weak: the best univariate AUCs are around 0.55. With data this small and this noisy, three dangers loom (research R3, R7):
  - overfitting the validation folds when many configurations are compared;
  - miscalibrated probabilities;
  - quietly re-using the holdout until something looks good.

## Decisions

1. **Walk-forward model selection on development seasons (≤ 2024).** Folds validate each season from 2012 to 2024, training on all earlier seasons. The primary metric is log-loss.
2. **One-standard-error rule.** Among the best configuration of each family, choose the *simplest* model whose mean fold log-loss is within one standard error of the best. Complexity order: elo-logit < logistic < random forest < gradient boosting < blend. This guards against selecting noise.
3. **Linear models are antisymmetric by construction.** The logistic model has no intercept and uses only antisymmetric features, scaled but not centred. Its predictions satisfy p(A,B) = 1 − p(B,A) exactly, even before symmetrisation.
4. **Time-ordered calibration choice.** The candidates are none, Platt (sigmoid) and isotonic:
   - Season S is calibrated with a mapping fitted only on out-of-fold predictions from seasons before S.
   - The simplest method within 0.001 log-loss of the best is chosen.
   - A calibrator g is applied symmetrically as ½[g(p) + 1 − g(1 − p)], so calibration cannot break orientation invariance.
5. **Holdout protocol.** 2025–26 is evaluated only after the selection has been frozen. That selection (model, parameters, calibration, Elo, features, data hash) is hashed and logged in `reports/holdout_ledger.json`:
   - Re-running the *same* frozen selection increments a counter. It is a deterministic recomputation.
   - Evaluating a *different* selection sets `reused_with_new_selection = true`, which the report must disclose.
6. **Serving.** After evaluation, the frozen configuration is refit on every decided match and registered for serving. The reported metrics come from the development-trained model, which is the only honest estimate.

## Consequences and outcome (from `reports/metrics.json`)

- The walk-forward log-loss of the chosen models sits slightly below the coin flip.
- On the 2025–26 holdout neither tier beats the constant 0.5 forecast. The paired bootstrap CIs include zero or favour the coin.
- The model is **not** re-tuned after seeing this. The weak holdout result is reported as a finding: pre-2023 regularities (home advantage, rating persistence) weakened after the Impact Player rule and the 2025 mega-auction.
- Honesty note: before the official `creaseiq train`, the holdout was also computed during one exploratory smoke run of the *same* frozen selection. That ledger file was deleted before the official run, and this note discloses it. The results were identical because the pipeline is deterministic.
