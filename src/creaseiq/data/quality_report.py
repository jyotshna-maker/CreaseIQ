"""Data-quality report and data dictionary (FR-03).

Both are generated from the pipeline's own outputs, so their numbers are never typed by hand.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from creaseiq.data.cleaning import CleanResult
from creaseiq.data.ingest import ValidationResult
from creaseiq.data.schema import CONSTANT_COLUMNS, RAW_COLUMNS
from creaseiq.utils import write_json

FIX_DESCRIPTIONS: dict[str, str] = {
    "season_label_mapped": "Rows whose season label is not a plain year (2007/08, 2009/10, 2020/21) mapped to season_year",
    "team_alias_canonicalised": "Team cells written under a former franchise name, mapped to the franchise id",
    "venue_alias_canonicalised": "Rows whose raw venue string differs from the canonical stadium name",
    "city_unknown_imputed": "City 'Unknown' (Dubai/Sharjah) imputed from the canonical venue",
    "city_corrected": "City corrected from the venue (Bangalore→Bengaluru, Chandigarh→Mohali, Mumbai→Navi Mumbai, ...)",
    "tie_innings_corrected_super_over_removed": "Tied rows whose innings totals included super-over runs, reset to the regulation tied score",
    "voided_flagged": "Matches voided and replayed in full, flagged and excluded from scoring stats",
    "no_result_scores_excluded": "No-result or voided rows whose partial scores are excluded from scoring statistics",
    "dls_flag_heuristic": "Decided matches whose margin or totals imply a revised (D/L) target",
    "dls_flag_external": "Matches in the externally verified D/L list (2008-2017)",
    "dls_flag_total": "Rows with dls_flag set (heuristic OR external)",
    "stage_derived_playoff": "Playoff fixtures (null match_number) labelled with an era-specific stage",
    "player_lists_parsed": "Squad lists parsed into the long match_player table",
}  # fmt: skip


def build_quality_summary(
    raw: pd.DataFrame,
    validation: ValidationResult,
    clean: CleanResult,
    raw_sha256: str,
) -> dict[str, Any]:
    """Assemble the machine-readable quality summary."""
    m = clean.matches
    decided = m[m["is_decided"]]
    seasons = (
        m.groupby("season_year")
        .agg(
            raw_label=("season_raw", "first"),
            matches=("match_id", "size"),
            decided=("is_decided", "sum"),
            ties=("result_type", lambda s: int((s == "tie").sum())),
            no_results=("result_type", lambda s: int((s == "no result").sum())),
            champion=("season_champion", "first"),
            first_match=("date", "min"),
            last_match=("date", "max"),
        )
        .reset_index()
    )
    seasons["first_match"] = seasons["first_match"].dt.strftime("%Y-%m-%d")
    seasons["last_match"] = seasons["last_match"].dt.strftime("%Y-%m-%d")
    squad = pd.crosstab(m["season_year"], m["n_players_t1"]).to_dict(orient="index")
    constants = {c: sorted(map(str, raw[c].dropna().unique())) for c in CONSTANT_COLUMNS}
    return {
        "raw": {
            "sha256": raw_sha256,
            "rows": len(raw),
            "columns": len(raw.columns),
            "column_names": list(RAW_COLUMNS),
            "nulls": {c: int(n) for c, n in raw.isna().sum().items() if n},
            "constant_columns": constants,
        },
        "validation": {
            "quarantined": validation.n_quarantined,
            "reasons": {str(k): v for k, v in validation.reasons.items()},
        },
        "fixes": dict(sorted(clean.fixes.items())),
        "notes": clean.notes,
        "identity": {
            "raw_team_strings": int(pd.concat([m["team1_raw"], m["team2_raw"]]).nunique()),
            "franchises": int(pd.concat([m["team1"], m["team2"]]).nunique()),
            "raw_venue_strings": int(m["venue_raw"].nunique()),
            "venues": int(m["venue_id"].nunique()),
            "players": int(clean.players["player"].nunique()),
        },
        "results": {
            "matches": len(m),
            "decided": len(decided),
            "ties": int((m["result_type"] == "tie").sum()),
            "no_results": int((m["result_type"] == "no result").sum()),
            "voided": int(m["voided"].sum()),
            "bat_first_win_rate": round(float(decided["bat_first_won"].astype(float).mean()), 4),
            "toss_winner_win_rate": round(
                float(decided["toss_winner_won"].astype(float).mean()), 4
            ),
            "toss_decision_counts": m["toss_decision"].value_counts().to_dict(),
            "team1_bats_first_share_by_year": m.groupby("season_year")["team1_bats_first"]
            .mean()
            .round(3)
            .to_dict(),
        },
        "seasons": seasons.to_dict(orient="records"),
        "squad_size_by_season": {int(k): {int(a): int(b) for a, b in v.items()} for k, v in squad.items()},
        "dls_rows": m.loc[m["dls_flag"], ["date_raw", "team1", "team2", "winner", "dls_heuristic", "dls_external"]]
        .to_dict(orient="records"),
        "tie_rows": m.loc[m["result_type"] == "tie", ["date_raw", "team1", "team2", "team1_runs", "team2_runs", "first_innings_runs", "super_over_winner"]]
        .to_dict(orient="records"),
        "voided_rows": m.loc[m["voided"], ["date_raw", "team1", "team2", "venue_id"]].to_dict(orient="records"),
    }  # fmt: skip


def _md_table(rows: list[dict[str, Any]], cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = "".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n" for r in rows)
    return head + body


def render_quality_markdown(summary: dict[str, Any]) -> str:
    """Render the quality summary as Markdown for ``docs/data_quality_report.md``."""
    raw, res, ident = summary["raw"], summary["results"], summary["identity"]
    fixes: Counter[str] = Counter(summary["fixes"])
    fix_rows = [
        {"Fix": k, "Rows": v, "What it means": FIX_DESCRIPTIONS.get(k, "")}
        for k, v in fixes.items()
    ]
    out = [
        "# Data-quality report",
        "",
        "_Generated by `creaseiq validate` (FR-03). Do not edit by hand._",
        "",
        "## Input",
        f"- File SHA-256: `{raw['sha256']}`",
        f"- Rows × columns: **{raw['rows']} × {raw['columns']}**",
        f"- Null counts: {', '.join(f'`{k}`={v}' for k, v in raw['nulls'].items())}",
        f"- Constant columns verified: {', '.join(f'`{k}`={v[0]}' for k, v in raw['constant_columns'].items())}",
        "",
        "## Validation",
        f"- Quarantined rows: **{summary['validation']['quarantined']}** "
        "(lenient mode; reasons in `data/interim/quarantine.csv`)",
        "",
        "## Fixes applied",
        _md_table(fix_rows, ["Fix", "Rows", "What it means"]),
        "## Identity resolution",
        f"- Team strings {ident['raw_team_strings']} → franchises **{ident['franchises']}** (ADR-003)",
        f"- Venue strings {ident['raw_venue_strings']} → venues **{ident['venues']}**",
        f"- Distinct player strings: {ident['players']} (exact-string identity)",
        "",
        "## Results overview",
        f"- Matches {res['matches']} · decided {res['decided']} · ties {res['ties']} · "
        f"no result {res['no_results']} · voided {res['voided']}",
        f"- Team batting first won **{res['bat_first_win_rate']:.1%}** of decided matches; "
        f"toss winner won **{res['toss_winner_win_rate']:.1%}**",
        f"- Toss decisions: {res['toss_decision_counts']}",
        "- Share of matches where raw `team1` batted first, by year "
        "(proves the order is meaningful only from 2018):",
        "",
        _md_table(
            [{"Year": k, "team1 bats first": v} for k, v in res["team1_bats_first_share_by_year"].items()],
            ["Year", "team1 bats first"],
        ),
        "## Seasons",
        _md_table(
            summary["seasons"],
            ["season_year", "raw_label", "matches", "decided", "ties", "no_results", "champion", "first_match", "last_match"],
        ),
        "## Ties (super-over contamination removed)",
        _md_table(
            summary["tie_rows"],
            ["date_raw", "team1", "team2", "team1_runs", "team2_runs", "first_innings_runs", "super_over_winner"],
        ),
        "## D/L-affected results",
        _md_table(summary["dls_rows"], ["date_raw", "team1", "team2", "winner", "dls_heuristic", "dls_external"]),
        "## Voided matches",
        _md_table(summary["voided_rows"], ["date_raw", "team1", "team2", "venue_id"]),
    ]  # fmt: skip
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------
# Data dictionary
# --------------------------------------------------------------------------------------
COLUMN_DOCS: dict[str, tuple[str, str]] = {
    "match_id": ("derived", "Surrogate key, 1..n in date order"),
    "date": ("raw `date`", "Match date (parsed from dd-mm-yyyy)"),
    "date_raw": ("raw `date`", "Original date string (join key for external facts)"),
    "season_raw": ("raw `season`", "Cricsheet season label (e.g. 2009/10)"),
    "season_year": ("derived", "Calendar year of the season's first match"),
    "match_number": ("raw", "League fixture number; null for playoffs"),
    "team1_raw": ("raw `team1`", "Original team1 string"),
    "team2_raw": ("raw `team2`", "Original team2 string"),
    "toss_winner_raw": ("raw", "Original toss winner string"),
    "winner_raw": ("raw", "Original winner string (null unless decided)"),
    "team1": ("derived", "team1 franchise id (order carries NO meaning before 2018)"),
    "team2": ("derived", "team2 franchise id"),
    "toss_winner": ("derived", "Toss winner franchise id"),
    "winner": ("derived", "Winner franchise id (null for ties/no results)"),
    "venue_raw": ("raw `venue`", "Original venue string"),
    "venue_id": ("derived", "Canonical venue id (configs/venue_canonical.yaml)"),
    "venue": ("derived", "Canonical stadium name"),
    "city_raw": ("raw `city`", "Original city (51 'Unknown')"),
    "city": ("derived", "City of the canonical venue"),
    "country": ("derived", "Country of the canonical venue"),
    "toss_decision": ("raw", "'bat' or 'field'"),
    "bat_first": ("derived", "Franchise batting first, from toss winner and decision"),
    "chasing_team": ("derived", "Franchise batting second"),
    "team1_bats_first": ("derived", "Whether team1 batted first"),
    "result_type": ("raw", "'complete', 'tie' or 'no result'"),
    "is_decided": ("derived", "result_type == 'complete' (the classification population)"),
    "win_by_runs": ("raw", "Margin in runs (0 if none)"),
    "win_by_wickets": ("raw", "Margin in wickets (0 if none)"),
    "margin_type": ("derived", "'runs', 'wickets' or null"),
    "margin_value": ("derived", "Margin in its own unit"),
    "bat_first_won": ("derived", "Team batting first won (null unless decided) — POST-MATCH"),
    "toss_winner_won": ("derived", "Toss winner won (null unless decided) — POST-MATCH"),
    "team1_runs": ("raw", "team1 total (ties include super-over runs)"),
    "team1_wickets": ("raw", "team1 wickets (ties include super-over wickets)"),
    "team2_runs": ("raw", "team2 total"),
    "team2_wickets": ("raw", "team2 wickets"),
    "first_innings_runs": ("derived", "Regulation first-innings runs (ties corrected)"),
    "second_innings_runs": ("derived", "Regulation second-innings runs (ties corrected)"),
    "first_innings_wickets": ("derived", "First-innings wickets (null on ties)"),
    "second_innings_wickets": ("derived", "Second-innings wickets (null on ties)"),
    "super_over_winner": ("external", "Super-over winner for ties (data/external)"),
    "voided": ("config", "Match voided and replayed"),
    "scores_usable": ("derived", "False for no-result/voided rows (exclude from scoring stats)"),
    "dls_heuristic": ("derived", "Margin/totals imply a revised D/L target"),
    "dls_external": ("external", "In the verified D/L list"),
    "dls_flag": ("derived", "dls_heuristic OR dls_external"),
    "stage": ("derived", "league, semi_final, third_place, qualifier_1, eliminator, qualifier_2, final"),
    "is_playoff": ("derived", "stage != league"),
    "is_final": ("derived", "stage == final"),
    "season_champion": ("derived", "Winner of the season's final"),
    "impact_era": ("derived", "season_year >= 2023 (Impact Player rule)"),
    "neutral_season": ("config", "Season played at neutral/overseas venues"),
    "team1_home": ("derived", "Venue is a team1 home ground that season"),
    "team2_home": ("derived", "Venue is a team2 home ground that season"),
    "player_of_match": ("raw", "Player of the match — POST-MATCH"),
    "match_referee": ("raw", "Match referee"),
    "umpire1": ("raw", "On-field umpire"),
    "umpire2": ("raw", "On-field umpire"),
    "tv_umpire": ("raw", "TV umpire"),
    "reserve_umpire": ("raw", "Reserve umpire"),
    "n_players_t1": ("derived", "Players listed for team1 (12 = Impact Player era)"),
    "n_players_t2": ("derived", "Players listed for team2"),
}  # fmt: skip


def render_data_dictionary(matches: pd.DataFrame, players: pd.DataFrame) -> str:
    """Render ``docs/data_dictionary.md`` from the real processed frames."""
    lines = [
        "# Data dictionary",
        "",
        "_Generated from `data/processed/matches.parquet` by `creaseiq validate`._",
        "",
        "## `matches` (one row per match)",
        "",
        "| Column | dtype | Source | Description | Example |",
        "|---|---|---|---|---|",
    ]
    for col in matches.columns:
        source, desc = COLUMN_DOCS.get(col, ("derived", ""))
        example = matches[col].dropna().iloc[0] if matches[col].notna().any() else ""
        example_str = str(example)[:40].replace("|", "/")
        lines.append(f"| `{col}` | {matches[col].dtype} | {source} | {desc} | {example_str} |")
    lines += [
        "",
        "## `match_players` (one row per player per match)",
        "",
        "| Column | dtype | Description |",
        "|---|---|---|",
        f"| `match_id` | {players['match_id'].dtype} | FK to matches |",
        f"| `team` | {players['team'].dtype} | Franchise id |",
        f"| `player` | {players['player'].dtype} | Exact Cricsheet name string (identity key) |",
        f"| `slot_no` | {players['slot_no'].dtype} | Position in the listed XI/XII |",
        "",
        "**Post-match columns** (`winner`, runs, wickets, margins, `bat_first_won`, "
        "`toss_winner_won`, `player_of_match`, `result_type`, `dls_*`, `super_over_winner`) "
        "are never used as model features. See the allow-list in `features/builder.py`.",
    ]
    return "\n".join(lines) + "\n"


def write_quality_outputs(summary: dict[str, Any], md_path: Path, json_path: Path) -> None:
    """Write the Markdown and JSON quality reports."""
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_quality_markdown(summary), encoding="utf-8")
    write_json(json_path, summary)
