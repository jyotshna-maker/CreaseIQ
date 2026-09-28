# Raw data (immutable)

| File | Rows | Columns | SHA-256 |
|---|---|---|---|
| `ipl_matches.csv` | 1,243 | 31 | `db81a92c740ef6d936f4f2361b4b4120468ae0acbcaed352a9707cfd0873d99c` |

- One row per IPL match, 2008-04-18 → 2026-05-31, 19 season labels.
- Provided by the student as `ipl_matches.csv.csv`, renamed on import. **Never edit this file.**
  Every cleaning step happens in code (`src/creaseiq/data/`) and is logged in
  `docs/data_quality_report.md`.
- The pipeline verifies this hash on ingest and records it in every model run
  (`models/registry.json`), so any silent change to the raw data is detected.
- Provenance and license: see `docs/research_notes.md` (R5) and the README's *Data attribution* section.
