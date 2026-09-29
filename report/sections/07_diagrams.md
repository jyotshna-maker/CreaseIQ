# 7. Design Diagrams

All system schematics are maintained as version-controlled Mermaid text specifications under `docs/diagrams/`. The diagrams are generated straight from our codebase—ensuring class interfaces, database schemas, and module import constraints reflect actual source code rather than conceptual sketches.

## 7.1 Use case diagram
The platform addresses three distinct user roles:

- **Statistical analysts and students:** Exploring cleaned datasets, evaluating causal hypotheses, and exporting filtered records.
- **Cricket followers and enthusiasts:** Running pre-match win projections, investigating what-if scenarios, and simulating entire seasons.
- **System maintainers:** Managing data ingestion, executing schema migrations, retraining models, and auditing benchmarks.

Each interaction scenario maps back to our functional requirements (FR). Because standard Mermaid lacks an explicit UML use-case palette, actors are rendered as circular terminal nodes while functional capabilities appear as bounded subgraphs.

{{ fig("docs/diagrams/D4_use_case.png", "Use case diagram (D4)", "62%") }}

## 7.2 Workflow diagrams
{{ fig("docs/diagrams/D2_data_pipeline.png", "Process flow: the data and modelling pipeline run by `creaseiq all` (D2)") }}

{{ fig("docs/diagrams/D3_user_workflow.png", "User workflow (activity diagram): analyst, predictor and maintainer paths (D3)", "80%") }}

## 7.3 Sequence diagrams
{{ fig("docs/diagrams/D5_sequence_predict.png", "Sequence: serving one prediction, from validation to the prediction log (D5)") }}

{{ fig("docs/diagrams/D6_sequence_train.png", "Sequence: training, selection, one-shot holdout evaluation and registration (D6)") }}

## 7.4 Class and component diagrams
{{ fig("docs/diagrams/D7_class.png", "Class diagram of the key classes (D7)") }}

{{ fig("docs/diagrams/D8_components.png", "Component / package diagram; arrows are the only allowed imports (D8)") }}

## 7.5 ER diagram and schema
{{ fig("docs/diagrams/D9_er.png", "Entity-relationship diagram generated from the ORM models (D9)") }}

**Relational architecture:** The database schema organizes IPL match dynamics across ten tables and two analytical SQL views:

- **Dimension tables:** `franchise`, `team_alias`, `venue`, `season`, `player`, `official`.
- **Fact tables:** `match` (recording individual contest metadata) and `match_player` (associating squads per fixture).
- **Audit tables:** `model_run` and `prediction_log` (retaining operational telemetry and prediction latency).
- **Pre-aggregated views:** `v_team_season_summary` and `v_head_to_head`.

**Relational constraints:** Data consistency is enforced at the database engine level via:

- Natural composite unique keying across `UNIQUE(date, team1_id, team2_id)`.
- Explicit `CHECK` constraints on toss decisions, result categories, team distinctions, complete-match winner presence, and unit-interval probabilities.
- Mandatory foreign key validation enabled via SQLite's `PRAGMA foreign_keys=ON`.

The complete schema definition file is generated directly from our SQLAlchemy declarative models into `docs/schema.sql`.

**Relational normalization (3NF):** Every table satisfies Third Normal Form requirements:
- Franchise naming history is isolated in `franchise`, while historical renames are captured with explicit active windows in `team_alias`.
- Ground metadata resides entirely within `venue`.
- Individual participants and match umpires reside in distinct tables indexed by surrogate keys.
- Match day lineups are modelled through the associative `match_player` relation (`match_id, team_id, player_id`), eliminating repeating squad arrays.
- The `match` entity records only foreign references and properties unique to that specific fixture.

The single intentional denormalization is `season.champion_id`, caching the tournament winner rather than recalculating the playoff final winner on every query. This tradeoff is explicitly guarded by automated unit tests.

## 7.6 Model lifecycle
{{ fig("docs/diagrams/D12_model_lifecycle.png", "Model lifecycle state diagram (D12)", "70%") }}
