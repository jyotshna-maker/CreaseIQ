# External reference data

Hand-verified facts that are **not** in the raw CSV. Each row cites two independent sources; they were collected in Phase 0 research (R8, 2026-09-28) and are documented in `docs/research_notes.md`.

| File | Purpose |
|---|---|
| `super_over_winners.csv` | Winners of all 16 tied matches, plus the regulation score at which each match was tied. The raw CSV leaves `winner` empty for ties **and** adds super-over runs and wickets to the innings totals, so `regulation_score_tied` is needed to recover the true first-innings score. |
| `dls_matches.csv` | Matches decided by Duckworth-Lewis(-Stern), 2008-2017. Used to validate the `dls_flag` heuristic. Medium confidence: for 2010, 2012 and 2013, "none found" was not independently cross-checked. |
