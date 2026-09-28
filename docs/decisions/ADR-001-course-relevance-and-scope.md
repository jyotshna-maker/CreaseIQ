# ADR-001: Course relevance and scope

- **Status:** Accepted, 2026-09-28
- **Context:** The assignment awards **0 marks** to a project that is not relevant to its course. The student confirmed the course is *Machine Learning*. The VITyarthi flipped course that other "Build Your Own Project" submissions cite is *Fundamentals of AI & ML* (CSA2001, VIT Bhopal). Its public module list also covers intelligent agents, state-space and heuristic search, knowledge representation and learning, and its blurb mentions supervised and unsupervised learning, preprocessing, evaluation and ethics (R1). The official syllabus sits behind a portal login.

## Options

1. A pure supervised ML project: classification and regression only.
2. An ML-core project that also maps the AI-fundamentals units explicitly.
3. An AI-first project, such as a search-based fantasy-team optimiser.

## Decision

Option 2. Machine learning is the core, and CreaseIQ also shows the AI fundamentals visibly and honestly:

| Unit | Where it appears |
|---|---|
| Data preprocessing | Validation, cleaning and canonicalisation pipeline (M1) |
| Supervised learning | Win-probability classifiers (T1) and first-innings score regression (T2) |
| Unsupervised learning | k-means venue profiling, with k chosen by silhouette score (new, small) |
| Model evaluation | Walk-forward validation, calibration, bootstrap CIs, baselines |
| Search / optimisation | Elo parameter tuning and hyperparameter selection, framed as heuristic grid and local search over a validation-loss landscape |
| Knowledge representation | Declarative YAML knowledge base (lineage, venues, home grounds) plus rule-based validation |
| Intelligent agent | `PredictionService` described as a PEAS agent (percepts: match context; actions: probability and explanation) |
| Ethics | Responsible-use disclaimer, leakage honesty and limitations in the model card |

## Consequences

- `docs/course_mapping.md` becomes a graded deliverable that maps each syllabus topic to a file and a test.
- One small extra module is added (`analytics/venue_clusters.py`). There is no deep learning: the data is 1.2k rows and the plan forbids a GPU dependency.
- If the student adds the official syllabus as `docs/assignment/syllabus.txt`, the course mapping is revised to cite its exact unit names.
