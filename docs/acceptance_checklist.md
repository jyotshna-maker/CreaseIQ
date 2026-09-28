# Final acceptance checklist (PLAN §15)

Status as of the v1.0.0 release, 2026-09-29. It was produced after an independent review pass and a clean-clone verification.

## Assignment compliance

| Item | Status | Evidence |
|---|---|---|
| Course relevance demonstrated | ✅ | `docs/course_mapping.md`, ADR-001, report §2.4 |
| ≥ 3 major functional modules with clear I/O and workflow | ✅ (5) | `statement.md`, report §4 (module I/O table), D3 |
| ≥ 4 NFRs specified and verified | ✅ (8, all pass) | `docs/nfr_verification.md`, `reports/nfr.json` |
| ≥ 5–10 modules, package structure, tests, validation and error handling, Git | ✅ | `src/creaseiq/` (11 subpackages), `tests/` (393 tests), `exceptions.py`, git history |
| Problem statement, objectives, FR, NFR | ✅ | `statement.md`, report §2–5 |
| Architecture, workflow, use case, class/component, sequence and ER diagrams, plus schema | ✅ | `docs/diagrams/D1–D12`, `docs/schema.sql` |
| Dataset description, model selection rationale, evaluation methodology | ✅ | report §9.1, §9.4, §9.5; ADR-006; `docs/data_dictionary.md` |
| README has all 7 required items; statement.md has all 4 | ✅ | `README.md`, `statement.md`, `tests/validation/test_docs.py` |
| PDF report has all 15 sections, in order | ✅ | `report/CreaseIQ_Project_Report.pdf`, `tests/validation/test_report_structure.py` |

## Rubric mapping

| Criterion | Status | Evidence |
|---|---|---|
| Problem understanding & requirements (10) | ✅ | `statement.md`, FR/NFR tables, `docs/rubric_traceability.md` |
| Design & documentation (20) | ✅ | D1–D12, ADR-001…006, data dictionary, model card, research notes, plan review |
| Implementation quality (25) | ✅ locally, ⏳ CI | ruff, mypy, import contract and bandit clean; coverage in `reports/coverage.json`. CI runs once the repository is pushed. |
| Innovation, depth & complexity (15) | ✅ | as-of engine plus leakage tests, symmetric models, tuned Elo, one-SE rule, ledger-logged holdout, paired bootstrap and Diebold–Mariano, causal toss test, data-trap discoveries, what-if, Monte Carlo, PSI |
| GitHub & version control (10) | ✅ history, ⏳ remote | Conventional Commits on feature branches, `--no-ff` merges, tags v0.1.0…v1.0.0, `CHANGELOG.md`. **Push pending `gh auth login` by the student.** |
| Project report (20) | ✅ | 50-page PDF generated from `reports/*.json`; 14/14 references resolve |

## Integrity

| Item | Status | Evidence |
|---|---|---|
| No fabricated metrics, screenshots or references | ✅ | Report and README numbers are rendered from JSON; screenshots are Playwright captures; `reports/reference_check.json` |
| Holdout touched only for one frozen selection, and logged | ✅ (with disclosure) | `reports/holdout_ledger.json` shows 1 distinct selection per tier; deterministic re-runs are counted; the earlier ledger reset is disclosed in ADR-006 |
| All leakage tests pass; holdout results plausible | ✅ | `tests/validation/test_leakage.py`; the too-good guard was not triggered (holdout AUC is well below 0.72) |
| Clean-clone install and run | ✅ Windows | Fresh clone → venv → `creaseiq all` → full test suite (Phase 9). macOS/Ubuntu will be checked by CI once the repository is pushed. |
| Data attribution and disclaimer | ✅ | README "Data attribution" and "Disclaimer"; app footer; model card |

## Remaining actions for the student
1. Revoke the GitHub token that was pasted into the original plan.
2. Run `gh auth login`. Then create and push the repository:
   - `gh repo create creaseiq --public --source=. --remote=origin --push`
   - `git push origin --tags`
3. Run `python scripts/set_repo_url.py <your-github-username>`, then `creaseiq report`, and commit the result.
4. Fill in `section:` in `report/report_config.yaml`, then run `creaseiq report` again.
