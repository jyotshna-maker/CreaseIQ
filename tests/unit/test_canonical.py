"""Canonical maps: full coverage, validity windows, fail-loud lookups (FR-02, ADR-003)."""

from __future__ import annotations

import pandas as pd
import pytest

from creaseiq.data.canonical import CanonicalMaps, build_canonical_maps
from creaseiq.exceptions import ConfigError, DataValidationError


def test_every_raw_team_and_venue_is_mapped(maps: CanonicalMaps, raw_df: pd.DataFrame) -> None:
    for team in set(raw_df["team1"]) | set(raw_df["team2"]):
        assert maps.team_id(team) in maps.franchises
    for venue in set(raw_df["venue"]):
        assert maps.venue_id(venue) in maps.venues


def test_counts_match_research(maps: CanonicalMaps) -> None:
    assert len(maps.team_aliases) == 19
    assert len(maps.franchises) == 15
    assert len(maps.venue_aliases) == 60
    assert len(maps.venues) == 37


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Delhi Daredevils", "dc"),
        ("Delhi Capitals", "dc"),
        ("Kings XI Punjab", "pbks"),
        ("Royal Challengers Bangalore", "rcb"),
        ("Royal Challengers Bengaluru", "rcb"),
        ("Rising Pune Supergiants", "rps"),
        ("Rising Pune Supergiant", "rps"),
        ("Deccan Chargers", "deccan_chargers"),
        ("Sunrisers Hyderabad", "srh"),
        ("Gujarat Lions", "gujarat_lions"),
        ("Gujarat Titans", "gt"),
    ],
)
def test_team_lineage(maps: CanonicalMaps, raw: str, expected: str) -> None:
    assert maps.team_id(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Feroz Shah Kotla", "arun_jaitley"),
        ("Subrata Roy Sahara Stadium", "mca_pune"),
        ("Sheikh Zayed Stadium", "zayed_abu_dhabi"),
        ("Zayed Cricket Stadium, Abu Dhabi", "zayed_abu_dhabi"),
        ("Sardar Patel Stadium, Motera", "motera_old"),
        ("Narendra Modi Stadium, Ahmedabad", "narendra_modi"),
        ("Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur", "mys_mullanpur"),
        ("Punjab Cricket Association Stadium, Mohali", "pca_mohali"),
        ("M.Chinnaswamy Stadium", "chinnaswamy"),
        ("OUTsurance Oval", "mangaung_oval"),
    ],
)
def test_venue_aliases(maps: CanonicalMaps, raw: str, expected: str) -> None:
    assert maps.venue_id(raw) == expected


def test_distinct_franchises_are_not_merged(maps: CanonicalMaps) -> None:
    assert maps.team_id("Deccan Chargers") != maps.team_id("Sunrisers Hyderabad")
    assert maps.team_id("Gujarat Lions") != maps.team_id("Gujarat Titans")
    assert maps.team_id("Rising Pune Supergiant") != maps.team_id("Lucknow Super Giants")


def test_unmapped_names_fail_loudly(maps: CanonicalMaps) -> None:
    with pytest.raises(DataValidationError, match="Unmapped team"):
        maps.team_id("Hyderabad Heroes")
    with pytest.raises(DataValidationError, match="Unmapped venue"):
        maps.venue_id("Lord's")


def test_alias_validity_window(maps: CanonicalMaps) -> None:
    assert maps.team_id("Delhi Capitals", 2019) == "dc"
    with pytest.raises(DataValidationError, match="validity window"):
        maps.team_id("Delhi Capitals", 2012)


def test_home_grounds(maps: CanonicalMaps) -> None:
    assert maps.is_home("mi", "wankhede", 2019)
    assert not maps.is_home("mi", "wankhede", 2020)  # UAE season
    assert maps.is_home("pbks", "pca_mohali", 2019)
    assert maps.is_home("pbks", "mys_mullanpur", 2025)
    assert not maps.is_home("pbks", "mys_mullanpur", 2019)
    assert maps.is_neutral_season(2009)
    assert maps.team_short("rcb") == "RCB"
    assert maps.venue_attr("dy_patil", "city") == "Navi Mumbai"


def test_config_cross_checks() -> None:
    lineage = {
        "franchises": {"a": {"name": "A", "short": "A"}},
        "aliases": {"A": {"franchise": "b", "valid_from": 1, "valid_to": 2}},
    }
    venues = {"venues": {"v": {"name": "V", "city": "C", "country": "X"}}, "aliases": {"V": "v"}}
    homes = {"homes": {}}
    with pytest.raises(ConfigError, match="unknown franchises"):
        build_canonical_maps(lineage, venues, homes)
    lineage["aliases"]["A"]["franchise"] = "a"
    with pytest.raises(ConfigError, match="unknown venue ids"):
        build_canonical_maps(lineage, {**venues, "aliases": {"V": "nope"}}, homes)
    with pytest.raises(ConfigError, match="unknown franchise"):
        build_canonical_maps(lineage, venues, {"homes": {"zz": []}})
    with pytest.raises(ConfigError, match="unknown venues"):
        build_canonical_maps(
            lineage, venues, {"homes": {"a": [{"venues": ["q"], "from": 1, "to": 2}]}}
        )
    with pytest.raises(ConfigError, match="Malformed"):
        build_canonical_maps({}, venues, homes)
