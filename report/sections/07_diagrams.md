# 7. Design Diagrams

All diagrams are written as Mermaid sources in `docs/diagrams/` and drawn from the actual code: class names, table columns and import rules match the source files.

## 7.1 Use case diagram
Three actors use the system:

- **Analyst / student:** explore, analyse and export.
- **Cricket fan:** predict, what-if and simulate.
- **Maintainer:** ingest, append, rebuild, train and benchmark.

Each use case carries its FR identifiers. Mermaid has no native use-case notation, so actors are drawn as circles and use cases as rounded shapes inside the system boundary.

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

**Schema summary.** The schema has ten tables and two views:

- **Dimension tables:** `franchise`, `team_alias`, `venue`, `season`, `player`, `official`.
- **Fact tables:** `match` and the associative `match_player`.
- **Operational tables:** `model_run` and `prediction_log`.
- **Views:** `v_team_season_summary` and `v_head_to_head`.

**Constraints.** The database enforces:

- a natural key, `UNIQUE(date, team1_id, team2_id)`;
- `CHECK`s on the toss decision, result type, distinct teams, "winner present iff complete" and probabilities in [0, 1];
- foreign keys, with `PRAGMA foreign_keys=ON`.

The full DDL is generated from the models into `docs/schema.sql`.

**Normalisation (3NF).** Every non-key attribute depends on the key, the whole key and nothing but the key:

- Franchise names live only in `franchise`, and aliases (with validity years) in `team_alias`.
- Venue attributes live only in `venue`.
- Player and official names live in their own tables, referenced by surrogate ids.
- Squads form a many-to-many relation (`match_player`, composite key `match_id, team_id, player_id`), not a repeating group.
- `match` holds only foreign keys and attributes of the match itself.

The one deliberate redundancy is `season.champion_id`, which can be derived from the season's final. It is kept as a documented, test-verified convenience.

## 7.6 Model lifecycle
{{ fig("docs/diagrams/D12_model_lifecycle.png", "Model lifecycle state diagram (D12)", "70%") }}
