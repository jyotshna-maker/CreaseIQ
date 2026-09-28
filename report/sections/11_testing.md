# 11. Testing Approach

## 11.1 Test pyramid
{{ tab("Collected tests per suite") }}

| Suite | Tests | Content |
|---|---|---|
| Unit (`tests/unit`) | {{ tests.unit }} | Every data, analytics, feature, model, service and reporting function; Hypothesis property tests; architecture (AST) |
| Integration (`tests/integration`) | {{ tests.integration }} | Pipeline on isolated projects; CLI via `CliRunner`; Streamlit `AppTest` for all 7 pages |
| Validation (`tests/validation`) | {{ tests.validation }} | Leakage, reproducibility, experiment, security, documentation, performance |
| **Total** | **{{ tests.total }}** | |

The integration and validation tests never write into the repository. They build **isolated temporary projects**: copies of the configs and external data with their own raw CSV, database and outputs.

## 11.2 Data-contract tests
- **Raw data:** the real CSV passes strict validation with the documented number of quarantined rows ({{ q.validation.quarantined }}).
- **Corruption:** injected faults are caught with named reasons: bad toss decision, non-participant toss winner, 11 wickets on a non-tie, impossible date, same team twice, missing winner, short squad, non-constant overs.
- **Ground truth:** all 19 derived champions match published results; there are 74 playoff fixtures with era-correct labels; base rates are correct; every alias maps.

## 11.3 Leakage tests (written before any model code)
1. **Future deletion:** features for matches up to a cut-off are bitwise identical when all later matches are removed.
2. **Future mutation:** flipping every later result and inflating later scores changes no earlier feature.
3. **Same day:** removing one match of a double-header leaves the other's features unchanged.
4. **Label shuffle:** with shuffled labels, the model's mean AUC is within 0.03 of 0.5.
5. **Column allow-list:** post-match columns raise `FeatureLeakageError`.

In addition:
- The orientation flag alone has no signal (its bootstrap AUC CI contains 0.5).
- A documentation test shows that raw `team1` order *would* leak batting order.
- The "too good" guard fires above AUC 0.72.

## 11.4 Model and property tests
- **Hypothesis properties:**
  - Elo expected scores are complementary and monotone.
  - Updates are zero-sum and move in the right direction.
  - The margin multiplier is positive and increasing.
  - Shrunk rates lie between the raw rate and the prior.
- **Swap invariance:** |p(A,B) − (1 − p(B,A))| < 1e-9 for every model family, for calibrated predictions, and for served predictions.
- **Metrics:** cross-checked against scikit-learn and statsmodels (log-loss, Brier, AUC, Wilson, z-test, Holm).
- **Reproducibility:** two full experiment runs give identical selections, grids and holdout metrics (tolerance 1e-9).
- **Registry:** round-trip loading works; an appended byte triggers `ModelIntegrityError`, and so does a missing artifact.

## 11.5 Security tests
- **Secrets scan** of every tracked file (GitHub tokens, AWS keys, private keys, key assignments). It guards against a regression of a real incident: a token pasted into the original build plan, which was stripped before the first commit.
- **SQL:** an AST ban on f-string or concatenated SQL in `text()`, `execute()` and `read_sql()`. Injection strings passed as team ids are inert.
- **Deserialisation:** allowed only in the registry, and only after the hash check. No `eval`, `exec` or `shell=True`.
- **Uploads:** wrong type, oversize, bad encoding, invalid rows and unknown teams are all rejected, with nothing written.
- **Exports:** CSV-injection payloads (`=`, `+`, `-`, `@`, tab) are escaped.
- **Static analysis:** `bandit` reports 0 issues and `pip-audit` finds no known vulnerabilities (`reports/bandit.json`, `reports/pip_audit.json`).

## 11.6 Coverage and continuous integration
{{ tab("Line coverage (coverage.py)") }}

| data | features | models | analytics | total |
|---|---|---|---|---|
| {{ cov.data | f(1) }}% | {{ cov.features | f(1) }}% | {{ cov.models | f(1) }}% | {{ cov.analytics | f(1) }}% | {{ cov.total | f(1) }}% |

The GitHub Actions workflow runs a matrix of {Ubuntu, Windows, macOS} × {Python 3.12, 3.13}. Each run executes `ruff check`, `ruff format --check`, `mypy src`, `lint-imports` (the layer contract), `pytest --cov` and `bandit`, plus `pip-audit` once. All gates pass locally on Windows 11.
