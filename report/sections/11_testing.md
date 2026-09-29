# 11. Testing Approach

## 11.1 Test pyramid
Quality assurance in CreaseIQ is structured as a multi-tier test pyramid executed across distinct testing scopes:

{{ tab("Collected tests per suite") }}

| Suite | Tests | Content |
|---|---|---|
| Unit (`tests/unit`) | {{ tests.unit }} | Every data, analytics, feature, model, service and reporting function; Hypothesis property tests; architecture (AST) |
| Integration (`tests/integration`) | {{ tests.integration }} | Pipeline on isolated projects; CLI via `CliRunner`; Streamlit `AppTest` for all 7 pages |
| Validation (`tests/validation`) | {{ tests.validation }} | Leakage, reproducibility, experiment, security, documentation, performance |
| **Total** | **{{ tests.total }}** | |

To prevent test runs from polluting production data or mutating committed models, integration and validation fixtures operate inside **hermetic temporary directories**. Test runners provision isolated filesystem trees containing miniature configurations, mock databases, and temporary output directories that are torn down automatically.

## 11.2 Data-contract tests
- **Baseline data certification:** The primary IPL dataset passes strict schema validation, with {{ q.validation.quarantined }} records quarantined.
- **Fault-injection resistance:** The ingestion harness injects deliberate malformations to ensure error handling is reliable: invalid coin-toss decisions, non-participating toss winners, impossible calendar dates, duplicate team pairings, missing winners on complete games, truncated lineups, and irregular over counts. Each fault must trigger an explicit named error.
- **Historical domain invariants:** Automated checks confirm that all 19 tournament champions match official records, that all 74 playoff fixtures preserve era-appropriate terminology, that base rates align with published figures, and that every franchise alias resolves correctly.

## 11.3 Leakage tests (written before any model code)
Adhering to Test-Driven Development (TDD) for data science, adversarial leakage tests were written and committed *before* implementing feature extraction code:

1. **Future fixture deletion:** Feature matrices computed for matches up to date $T$ must remain bit-for-bit identical when all subsequent matches are purged from the database.
2. **Future fixture mutation:** Inverting outcomes and multiplying scores for matches after date $T$ cannot alter feature values computed for games on or before $T$.
3. **Same-day tournament isolation:** Selectively dropping the afternoon fixture of a double-header leaves feature vectors for the evening fixture completely unaffected.
4. **Label permuting validation:** When outcome labels are randomly permuted, the model's cross-validated mean AUC must collapse to $0.50 \pm 0.03$.
5. **Schema allow-listing:** Attempting to feed post-match scorecard attributes (such as second-innings boundaries or bowler wickets) into feature transformers raises a fatal `FeatureLeakageError`.

Additionally:
- Permuting orientation assignments confirms that the orientation indicator carries zero statistical signal (its bootstrap AUC 95% interval covers 0.50).
- Explicit regression tests document that raw `team1` ordering would indeed leak batting order post-2018.
- The automated audit guard trips if holdout AUC exceeds 0.72.

## 11.4 Model and property tests
- **Hypothesis property-based assertions:**
  - Expected scores computed by the Elo model are complementary ($E_A + E_B = 1$) and strictly monotonic with respect to rating differences.
  - Rating updates are zero-sum and always adjust in the direction of match victory.
  - The margin multiplier remains strictly positive and increases monotonically with run margin.
  - Empirical Bayesian shrinkage pulls venue averages strictly between raw sample means and global priors.
- **Directional swap invariance:** Every model family, calibrated scoring function, and served prediction pipeline satisfies $|P(A, B) - (1 - P(B, A))| < 10^{-9}$.
- **Numerical cross-validation:** Custom metric routines are benchmarked against reference implementations from scikit-learn and statsmodels (cross-entropy, Brier scores, ROC-AUC, Wilson intervals, and Welch tests).
- **End-to-end reproducibility:** Executing independent pipeline runs yields identical model selections, hyperparameter grids, and holdout loss figures within a tolerance of $10^{-9}$.
- **Model artifact integrity:** Serialized joblib models cannot be tampered with; modifying a single byte in a model file triggers an immediate `ModelIntegrityError`.

## 11.5 Security tests
- **Secrets scanning:** Automated static checks inspect all tracked repository files for accidentally committed credentials, API tokens, or private keys. This test was introduced after catching a development token in an early draft plan prior to initial repository commit.
- **SQL injection prevention:** AST-level inspection bans raw string interpolation within SQLAlchemy `text()`, `execute()`, and pandas `read_sql()`. Injection vectors supplied as team identifiers are safely escaped.
- **Safe deserialization:** Joblib deserialization is permitted exclusively within the model registry, guarded by SHA-256 manifest checks. Dangerous primitives (`eval`, `exec`, shell subprocess invocations) are forbidden.
- **File upload validation:** File upload endpoints enforce 5 MB limits, verify MIME types, enforce UTF-8 encodings, and reject unmapped franchise strings before touching disk.
- **CSV formula injection mitigation:** Tabular exports prepend single quotes to cells beginning with formula triggers (`=`, `+`, `-`, `@`, or tab characters) to prevent remote formula execution in desktop spreadsheet applications.
- **Automated dependency and code auditing:** Code scans with `bandit` yield 0 security warnings, while `pip-audit` confirms no known CVEs across installed dependencies (`reports/bandit.json`, `reports/pip_audit.json`).

## 11.6 Coverage and continuous integration
{{ tab("Line coverage (coverage.py)") }}

| data | features | models | analytics | total |
|---|---|---|---|---|
| {{ cov.data | f(1) }}% | {{ cov.features | f(1) }}% | {{ cov.models | f(1) }}% | {{ cov.analytics | f(1) }}% | {{ cov.total | f(1) }}% |

Continuous integration runs under GitHub Actions across a multi-platform matrix spanning Ubuntu Linux, Windows Server, and macOS under Python 3.12 and 3.13. Every pull request executes static formatting checks (`ruff`), static typing verification (`mypy`), architectural import boundary validation (`lint-imports`), unit and integration test suites with coverage thresholds (`pytest --cov`), and security scanners (`bandit` and `pip-audit`). Complete local reproduction starting from a clean git clone was validated on Windows 11 before publication.
