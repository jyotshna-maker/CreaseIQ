# Data dictionary

_Generated from `data/processed/matches.parquet` by `creaseiq validate`._

## `matches` (one row per match)

| Column | dtype | Source | Description | Example |
|---|---|---|---|---|
| `match_id` | int64 | derived | Surrogate key, 1..n in date order | 1 |
| `date` | datetime64[us] | raw `date` | Match date (parsed from dd-mm-yyyy) | 2008-04-18 00:00:00 |
| `date_raw` | str | raw `date` | Original date string (join key for external facts) | 18-04-2008 |
| `season_raw` | str | raw `season` | Cricsheet season label (e.g. 2009/10) | 2007/08 |
| `season_year` | int64 | derived | Calendar year of the season's first match | 2008 |
| `match_number` | float64 | raw | League fixture number; null for playoffs | 1.0 |
| `team1_raw` | str | raw `team1` | Original team1 string | Royal Challengers Bangalore |
| `team1` | str | derived | team1 franchise id (order carries NO meaning before 2018) | rcb |
| `team2_raw` | str | raw `team2` | Original team2 string | Kolkata Knight Riders |
| `team2` | str | derived | team2 franchise id | kkr |
| `toss_winner_raw` | str | raw | Original toss winner string | Royal Challengers Bangalore |
| `toss_winner` | str | derived | Toss winner franchise id | rcb |
| `winner_raw` | str | raw | Original winner string (null unless decided) | Kolkata Knight Riders |
| `winner` | str | derived | Winner franchise id (null for ties/no results) | kkr |
| `venue_raw` | str | raw `venue` | Original venue string | M Chinnaswamy Stadium |
| `venue_id` | str | derived | Canonical venue id (configs/venue_canonical.yaml) | chinnaswamy |
| `venue` | str | derived | Canonical stadium name | M. Chinnaswamy Stadium |
| `city_raw` | str | raw `city` | Original city (51 'Unknown') | Bangalore |
| `city` | str | derived | City of the canonical venue | Bengaluru |
| `country` | str | derived | Country of the canonical venue | India |
| `toss_decision` | str | raw | 'bat' or 'field' | field |
| `bat_first` | str | derived | Franchise batting first, from toss winner and decision | kkr |
| `chasing_team` | str | derived | Franchise batting second | rcb |
| `team1_bats_first` | bool | derived | Whether team1 batted first | False |
| `result_type` | str | raw | 'complete', 'tie' or 'no result' | complete |
| `is_decided` | bool | derived | result_type == 'complete' (the classification population) | True |
| `win_by_runs` | int64 | raw | Margin in runs (0 if none) | 140 |
| `win_by_wickets` | int64 | raw | Margin in wickets (0 if none) | 0 |
| `margin_type` | object | derived | 'runs', 'wickets' or null | runs |
| `margin_value` | float64 | derived | Margin in its own unit | 140.0 |
| `bat_first_won` | boolean | derived | Team batting first won (null unless decided) — POST-MATCH | True |
| `toss_winner_won` | boolean | derived | Toss winner won (null unless decided) — POST-MATCH | False |
| `team1_runs` | int64 | raw | team1 total (ties include super-over runs) | 82 |
| `team1_wickets` | int64 | raw | team1 wickets (ties include super-over wickets) | 10 |
| `team2_runs` | int64 | raw | team2 total | 222 |
| `team2_wickets` | int64 | raw | team2 wickets | 3 |
| `first_innings_runs` | float64 | derived | Regulation first-innings runs (ties corrected) | 222.0 |
| `second_innings_runs` | float64 | derived | Regulation second-innings runs (ties corrected) | 82.0 |
| `first_innings_wickets` | float64 | derived | First-innings wickets (null on ties) | 3.0 |
| `second_innings_wickets` | float64 | derived | Second-innings wickets (null on ties) | 10.0 |
| `super_over_winner` | object | external | Super-over winner for ties (data/external) | rr |
| `voided` | bool | config | Match voided and replayed | False |
| `scores_usable` | bool | derived | False for no-result/voided rows (exclude from scoring stats) | True |
| `dls_heuristic` | boolean | derived | Margin/totals imply a revised D/L target | False |
| `dls_external` | bool | external | In the verified D/L list | False |
| `dls_flag` | boolean | derived | dls_heuristic OR dls_external | False |
| `stage` | object | derived | league, semi_final, third_place, qualifier_1, eliminator, qualifier_2, final | league |
| `is_playoff` | bool | derived | stage != league | False |
| `is_final` | bool | derived | stage == final | False |
| `season_champion` | str | derived | Winner of the season's final | rr |
| `impact_era` | bool | derived | season_year >= 2023 (Impact Player rule) | False |
| `neutral_season` | bool | config | Season played at neutral/overseas venues | False |
| `team1_home` | bool | derived | Venue is a team1 home ground that season | True |
| `team2_home` | bool | derived | Venue is a team2 home ground that season | False |
| `player_of_match` | str | raw | Player of the match — POST-MATCH | BB McCullum |
| `match_referee` | str | raw | Match referee | J Srinath |
| `umpire1` | str | raw | On-field umpire | Asad Rauf |
| `umpire2` | str | raw | On-field umpire | RE Koertzen |
| `tv_umpire` | str | raw | TV umpire | AM Saheba |
| `reserve_umpire` | str | raw | Reserve umpire | VN Kulkarni |
| `n_players_t1` | int64 | derived | Players listed for team1 (12 = Impact Player era) | 11 |
| `n_players_t2` | int64 | derived | Players listed for team2 | 11 |

## `match_players` (one row per player per match)

| Column | dtype | Description |
|---|---|---|
| `match_id` | int64 | FK to matches |
| `team` | str | Franchise id |
| `player` | str | Exact Cricsheet name string (identity key) |
| `slot_no` | int64 | Position in the listed XI/XII |

**Post-match columns** (`winner`, runs, wickets, margins, `bat_first_won`, `toss_winner_won`, `player_of_match`, `result_type`, `dls_*`, `super_over_winner`) are never used as model features. See the allow-list in `features/builder.py`.
