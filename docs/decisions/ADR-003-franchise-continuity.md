# ADR-003: Franchise continuity and canonical identities

- **Status:** Accepted, 2026-09-28
- **Context:** The raw data uses 19 team strings. Some are renames of one franchise: Delhi Daredevils → Delhi Capitals, Kings XI Punjab → Punjab Kings, Royal Challengers Bangalore → Bengaluru, and Rising Pune Supergiants → Supergiant. Others are different franchises that share a city or owner: Deccan Chargers vs Sunrisers Hyderabad, Gujarat Lions vs Gujarat Titans, and Rising Pune Supergiant vs Lucknow Super Giants. The choice affects team history, head-to-head records, Elo carry-over and "titles" counts (R2).

## Options

1. Merge by city, so Hyderabad = DCH + SRH.
2. Merge by legal franchise, where renames share an identity and new ownership or a new contract means a new identity.
3. Never merge any strings.

## Decision

Option 2, encoded in `configs/team_lineage.yaml`:

- 19 strings map to **15 `franchise_id`s**.
- Each alias has `valid_from` and `valid_to` years. A test fails if an alias appears outside its validity window, which catches data errors such as "Delhi Capitals" showing up in 2012.
- Deccan Chargers, Gujarat Lions, Rising Pune Supergiant, Pune Warriors and Kochi Tuskers are separate, now-defunct franchises.
- New franchises start Elo at the league mean of 1500.

## Consequences

- Titles are counted per franchise: RCB has 2 (2025 and 2026), and the 2009 title belongs to Deccan Chargers, not SRH.
- A **sensitivity check** in the modelling phase re-runs Elo with DCH → SRH treated as continuous and reports the change in log-loss, so the choice is shown empirically to matter little or not.
- CSK and RR have a two-year gap (2016–17). Season carry-over shrinks each gap season toward the mean, so ratings reach the regressed value after the gap.
