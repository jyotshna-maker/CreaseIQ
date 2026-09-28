"""Cleaning and derived columns validated against research ground truth (FR-02, R8, R10)."""

from __future__ import annotations

import pandas as pd
import pytest

from creaseiq.data.cleaning import clean_matches, load_external_facts, season_year_map
from creaseiq.data.ingest import validate_raw
from creaseiq.data.pipeline import DataPipelineResult

# Ground truth from docs/research_notes.md (R10), keyed by franchise id.
CHAMPIONS = {
    2008: "rr", 2009: "deccan_chargers", 2010: "csk", 2011: "csk", 2012: "kkr", 2013: "mi",
    2014: "kkr", 2015: "mi", 2016: "srh", 2017: "mi", 2018: "csk", 2019: "mi", 2020: "mi",
    2021: "csk", 2022: "gt", 2023: "csk", 2024: "kkr", 2025: "rcb", 2026: "rcb",
}  # fmt: skip


def test_champions_match_ground_truth(matches: pd.DataFrame) -> None:
    derived = matches.groupby("season_year")["season_champion"].first().to_dict()
    assert derived == CHAMPIONS


def test_season_year_mapping(raw_df: pd.DataFrame) -> None:
    smap = season_year_map(raw_df)
    assert smap["2007/08"] == 2008
    assert smap["2009"] == 2009
    assert smap["2009/10"] == 2010
    assert smap["2020/21"] == 2020
    assert smap["2021"] == 2021
    assert len(set(smap.values())) == 19


def test_stage_counts_by_era(matches: pd.DataFrame) -> None:
    po = matches[matches["is_playoff"]]
    assert len(po) == 74
    assert po.groupby("season_year").size().to_dict()[2008] == 3
    s2010 = po[po["season_year"] == 2010].sort_values("date")["stage"].tolist()
    assert s2010 == ["semi_final", "semi_final", "third_place", "final"]
    s2025 = po[po["season_year"] == 2025].sort_values("date")["stage"].tolist()
    assert s2025 == ["qualifier_1", "eliminator", "qualifier_2", "final"]
    assert matches["is_final"].sum() == 19


def test_bat_first_derived_from_toss(matches: pd.DataFrame) -> None:
    bats = matches["toss_decision"] == "bat"
    assert (matches.loc[bats, "bat_first"] == matches.loc[bats, "toss_winner"]).all()
    assert (matches.loc[~bats, "bat_first"] != matches.loc[~bats, "toss_winner"]).all()
    assert (matches["bat_first"] != matches["chasing_team"]).all()
    # From 2018 the raw team1 always batted first; before that it did not (plan finding 1).
    share = matches.groupby("season_year")["team1_bats_first"].mean()
    assert (share[share.index >= 2018] == 1.0).all()
    assert (share[share.index < 2018] < 0.7).all()


def test_base_rates(matches: pd.DataFrame) -> None:
    decided = matches[matches["is_decided"]]
    assert len(decided) == 1218
    assert decided["bat_first_won"].astype(float).mean() == pytest.approx(0.4532, abs=1e-4)
    assert decided["toss_winner_won"].astype(float).mean() == pytest.approx(0.5156, abs=1e-4)


def test_tie_rows_corrected(matches: pd.DataFrame, pipeline: DataPipelineResult) -> None:
    ties = matches[matches["result_type"] == "tie"]
    assert len(ties) == 16
    assert (ties["first_innings_runs"] == ties["second_innings_runs"]).all()
    assert ties["super_over_winner"].notna().all()
    assert ties["first_innings_wickets"].isna().all()
    gl_mi = ties[ties["date_raw"] == "29-04-2017"].iloc[0]
    assert gl_mi["team2_wickets"] == 12  # raw kept for audit
    assert gl_mi["first_innings_runs"] == 153  # regulation tied score (R8)
    assert gl_mi["super_over_winner"] == "mi"
    assert pipeline.clean.notes["super_over_records_unmatched"] == 0


def test_dls_flags(matches: pd.DataFrame, pipeline: DataPipelineResult) -> None:
    assert matches["dls_heuristic"].sum() == 14
    assert matches["dls_external"].sum() == 16
    assert matches["dls_flag"].sum() == 19
    assert pipeline.clean.notes["dls_external_unmatched"] == 0
    # Every heuristic hit in the externally covered years (<= 2017) is confirmed externally.
    covered = matches[matches["season_year"] <= 2017]
    assert (covered["dls_external"] | ~covered["dls_heuristic"]).all()
    final_2023 = matches[(matches["season_year"] == 2023) & matches["is_final"]].iloc[0]
    assert final_2023["dls_flag"]


def test_voided_and_no_result(matches: pd.DataFrame) -> None:
    v = matches[matches["voided"]]
    assert len(v) == 1 and v.iloc[0]["date_raw"] == "08-05-2025"
    assert (~matches.loc[matches["result_type"] == "no result", "scores_usable"]).all()


def test_canonical_columns(matches: pd.DataFrame) -> None:
    assert matches["venue_id"].nunique() == 37
    assert (matches["city"] != "Unknown").all()
    assert set(matches.loc[matches["venue_id"] == "dy_patil", "city"]) == {"Navi Mumbai"}
    assert matches["match_id"].is_unique and matches["date"].is_monotonic_increasing
    assert matches["impact_era"].sum() == (matches["season_year"] >= 2023).sum()
    assert not (matches["neutral_season"] & (matches["team1_home"] | matches["team2_home"])).any()


def test_players_long_table(pipeline: DataPipelineResult) -> None:
    p = pipeline.clean.players
    assert p["player"].nunique() == 811
    counts = p.groupby(["match_id", "team"]).size()
    assert counts.between(11, 13).all()
    assert not p.duplicated(["match_id", "team", "player"]).any()


def test_subset_cleans_without_error(sample_raw: pd.DataFrame, maps, settings) -> None:
    facts = load_external_facts(settings.path("external_dir"), settings.get("data.voided_matches"))
    res = clean_matches(validate_raw(sample_raw).valid, maps, facts)
    assert len(res.matches) == 60
    assert res.notes["super_over_records_unmatched"] == 15  # fixture holds 1 of 16 ties
    assert res.matches.loc[res.matches["season_year"] == 2008, "season_champion"].iloc[0] == "rr"
