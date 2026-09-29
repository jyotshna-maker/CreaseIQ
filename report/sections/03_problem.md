# 3. Problem Statement

## 3.1 The problem
Working with seventeen years of historical cricket scorecards quickly reveals that public sports datasets are riddled with subtle irregularities. Inexperienced modelling workflows frequently produce invalid inferences due to four core complications:

- **Organizational mutations and franchise continuity:** Franchises in the IPL frequently rebrand, merge, or exit. For instance, Delhi Daredevils simply underwent a corporate name change to Delhi Capitals in 2019 while retaining squad continuity and historical rights. In contrast, Deccan Chargers and Sunrisers Hyderabad represent distinct legal and historical entities despite sharing a home base, because the former was terminated by the league before the latter was auctioned as a new franchise.
- **Venue fragmentation and orthographic variance:** Stadiums appear under varying transcriptions, local vernaculars, commercial sponsorship names, or following major renovations. Treating "Sardar Patel Stadium, Motera" and "Narendra Modi Stadium" as unrelated venues destroys sample size for ground-specific priors.
- **Inconsistent temporal nomenclature:** Tournament logs mix raw single-year integers (`2019`) with multi-year formats (`2007/08`, `2020/21`) created by pandemic rescheduling and calendar quirks.
- **Latent semantic shifts:** The most treacherous bugs in sports data are structural shifts that carry no explicit warning in column headers. For instance, the sequence in which teams are listed in raw scorecard schemas often changes silently across historical epochs.

Because existing open-source IPL notebooks typically ignore these traps, public predictions often report overfitted accuracies exceeding 85%. In practice, these models inadvertently exploit information leakage—such as peeking into post-innings run differentials or training across future time boundaries. 

CreaseIQ establishes an open, reproducible framework addressing these gaps:
1. Constructing an auditable, canonical dataset where every correction and identity mapping is documented in code.
2. Delivering inferential statistical tests that quantify uncertainty rather than asserting overconfident conclusions.
3. Establishing a strictly leak-free probabilistic classification pipeline evaluated under honest temporal holdouts.

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
- Processing the complete 2008–2026 scorecard corpus, alongside support for validated user additions.
- Normalized relational database storage backing interactive analytical queries.
- Empirical statistical testing covering the toss, chasing biases, venue scoring baselines, and tournament rule changes.
- Pre-match and post-toss probabilistic outcome estimation.
- Expected first-innings total score regression.
- Interactive what-if scenario exploration and full-season Monte Carlo projections.
- Multi-interface delivery via a responsive Streamlit dashboard and Typer CLI, validated by test automation.

**Out of scope:**
- Real-time in-play ball-by-ball micro-predictions during live broadcasts.
- Gambling odds estimation or financial betting recommendation tools.
- Granular player-level stroke analysis or wagon wheels (which are absent in aggregate match scorecards).
- Multi-tenant authentication systems. Because the project operates as a local analytical tool on public sports records, adding complex credential management would introduce security overhead without analytical utility.

## 3.4 Target users
{{ tab("Target users and their needs") }}

| User | Need | Served by |
|---|---|---|
| Students / analysts | Clean data; honest statistics with confidence intervals | Data Explorer, Team Analytics, Venue & Toss, CSV export |
| Cricket fans | Evidence-based previews; "what if we win the toss?" | Predict Match, What-If |
| Maintainers / data engineers | Add seasons and sources safely; retrain reproducibly | CLI (`ingest`, `all`, `train`), tests, CI, ADRs |
