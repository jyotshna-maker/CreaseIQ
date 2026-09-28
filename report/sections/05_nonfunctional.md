# 5. Non-functional Requirements

The assignment requires at least four non-functional requirements. CreaseIQ specifies eight. Each has a measurable target and a verification method, and each is verified with evidence produced by the code (`docs/nfr_verification.md`).

{{ tab("Non-functional requirements: targets and verification method") }}

| ID | Category | Requirement (target) | Verified by |
|---|---|---|---|
| NFR-01 | Performance | Full pipeline ≤ 90 s; single warm prediction ≤ 200 ms; dashboard page ≤ 2 s | `creaseiq benchmark` → `reports/perf.json`; `test_performance.py` |
| NFR-02 | Reliability & error handling | Typed exception hierarchy; idempotent pipeline; friendly errors with no stack traces | Unit, CLI and AppTest tests with bad inputs |
| NFR-03 | Security | Allow-list validation; parameterised SQL only; hash-verified model loading; CSV-only uploads ≤ 5 MB; CSV-injection escaping; no secrets | `bandit`, `pip-audit`, `test_security.py` |
| NFR-04 | Usability | ≤ 3 clicks to a prediction; colour-blind-safe palettes; tooltips; empty states; disclaimer | AppTest, screenshots |
| NFR-05 | Maintainability | Type hints, docstrings, ruff and mypy clean, enforced layering, ≥ 85% coverage on core packages | CI, `coverage.json`, `test_architecture.py` |
| NFR-06 | Reproducibility | Seeds, pinned dependencies, config-driven; identical metrics across runs | `test_experiment.py::test_reproducible_metrics` |
| NFR-07 | Logging & monitoring | Structured logs with run id and timings; prediction log; PSI drift panel | `test_figures_logging.py`, Model Lab |
| NFR-08 | Scalability & efficiency | DB backend by URL; `MatchSource` interface; O(n) incremental features; RAM < 1 GB | `perf.json`, interface tests |

## 5.1 Measured results
{{ tab("Measured NFR results (generated from evidence files)") }}

| ID | Category | Measured | Result |
|---|---|---|---|
{% for r in nfr.rows %}| {{ r.id }} | {{ r.category }} | {{ r.measured }} | {{ "PASS" if r.passed else "FAIL" }} |
{% endfor %}

Measured on {{ p.machine.platform }} ({{ p.machine.cpu_count }} logical CPUs, Python {{ p.machine.python }}).

Pipeline stage times (seconds):

| Stage | Time |
|---|---|
| Data | {{ p.stages_s.data | f(2) }} |
| Database | {{ p.stages_s.db | f(2) }} |
| Features | {{ p.stages_s.features | f(2) }} |
| Training the registered configuration | {{ p.stages_s.train_best | f(2) }} |

NFR-01 covers the operational pipeline, which trains the registered configuration. The one-off model-selection experiment is not part of it. That experiment (the Elo grid, five model families and their grids, 13 walk-forward folds, two tiers, calibration, ablations and bootstrap tests) took {{ m.experiment_runtime_s }} s in the recorded `creaseiq train` run.

The cross-platform requirement is verified locally on Windows 11, including a clean-clone install and run. The GitHub Actions workflow is configured to run on Ubuntu, Windows and macOS with Python 3.12 and 3.13, and it executes on every push once the repository is published.
