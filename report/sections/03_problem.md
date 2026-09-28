# 3. Problem Statement

## 3.1 The problem
IPL data is rich but inconsistent. Several failure modes make naive analysis wrong:

- **Renamed and replaced franchises.** For example, Delhi Daredevils became Delhi Capitals. Deccan Chargers and Sunrisers Hyderabad, however, are *different* franchises.
- **One stadium, many spellings.** A stadium can appear under several spellings or under old and new names.
- **Season labels that are not years.**
- **Hidden semantic traps** that the raw columns never announce.

Students, analysts and fans lack a clean, validated, reproducible dataset. They also lack a principled way to quantify the toss, venue, form and era effects. On top of that, many machine-learning "IPL predictors" published online leak post-match information or ignore time order. They report accuracies that cannot be reproduced on genuinely unseen matches.

CreaseIQ therefore sets out to deliver three things:

1. A validated, canonical dataset with an auditable record of every change.
2. Statistically sound analytics that report uncertainty.
3. A leakage-safe, calibrated pre-match win-probability engine whose accuracy is measured honestly.

## 3.2 Data traps discovered (and handled)
{{ tab("Data problems found during profiling and research, and how they are handled") }}

| Trap | Evidence | Handling |
|---|---|---|
| `team1` means "batting first" only from 2018 | share of matches with raw team1 batting first: 1.00 every season from 2018; 0.45–0.62 before | Batting order is derived from the toss; orientation uses a hash-seeded coin flip (ADR-005) |
| Tie rows include super-over runs and wickets | {{ q.results.ties }} ties; e.g. a side "losing 12 wickets" (10 + 2 in the super over) | Regulation scores restored from verified external data (ADR-004) |
| Voided and replayed match stored as "no result" | {{ q.results.voided }} match (08-05-2025, security blackout) | `voided` flag; excluded from scoring statistics |
| D/L-affected results | {{ q.fixes.dls_flag_heuristic }} flagged by margin logic, {{ q.fixes.dls_flag_external }} from a verified list | `dls_flag` = heuristic OR list ({{ q.fixes.dls_flag_total }} rows) |
| {{ q.identity.raw_team_strings }} team strings for {{ q.identity.franchises }} franchises | renames and spelling variants | Lineage map with validity years (ADR-003) |
| {{ q.identity.raw_venue_strings }} venue strings for {{ q.identity.venues }} venues | suffixes, renames, rebuilt stadiums | Canonical venue map, fail-loud |
| City "Unknown" in {{ q.fixes.city_unknown_imputed }} rows | Dubai and Sharjah venues | Imputed from the canonical venue |

## 3.3 Scope
**In scope:**
- The supplied match file (2008–2026) and validated uploads of new matches.
- A relational database.
- Analytics: toss, chasing, teams, venues, scoring eras, player-of-the-match.
- Two-tier win probability: pre-toss and post-toss.
- First-innings score regression.
- What-if scenarios and a season simulation.
- A dashboard, CLI, tests, CI and documentation.

**Out of scope:**
- Ball-by-ball or live in-play prediction.
- Betting odds or betting advice.
- Player batting and bowling statistics, which are not in the data.
- Multi-user accounts. CreaseIQ is a single-user local application holding only public match records, so authentication would add risk without benefit.

## 3.4 Target users
{{ tab("Target users and their needs") }}

| User | Need | Served by |
|---|---|---|
| Students / analysts | Clean data; honest statistics with confidence intervals | Data Explorer, Team Analytics, Venue & Toss, CSV export |
| Cricket fans | Evidence-based previews; "what if we win the toss?" | Predict Match, What-If |
| Maintainers / data engineers | Add seasons and sources safely; retrain reproducibly | CLI (`ingest`, `all`, `train`), tests, CI, ADRs |
