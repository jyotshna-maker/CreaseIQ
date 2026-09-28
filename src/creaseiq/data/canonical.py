"""Canonical identities for teams, venues and home grounds (FR-02, ADR-003).

The YAML files under ``configs/`` act as a small declarative knowledge base. Lookups
**fail loudly**: an unknown team or venue string raises :class:`DataValidationError`
rather than silently producing an unmapped value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from creaseiq.config import Settings, load_yaml
from creaseiq.exceptions import ConfigError, DataValidationError


@dataclass(frozen=True)
class TeamAlias:
    """One raw team string and the franchise it denotes over a range of seasons."""

    alias: str
    franchise_id: str
    valid_from: int
    valid_to: int


@dataclass(frozen=True)
class CanonicalMaps:
    """Loaded canonical maps with lookup helpers."""

    franchises: dict[str, dict[str, Any]]
    team_aliases: dict[str, TeamAlias]
    venues: dict[str, dict[str, Any]]
    venue_aliases: dict[str, str]
    homes: dict[str, list[dict[str, Any]]]
    neutral_seasons: dict[int, str]

    # -- teams ---------------------------------------------------------------------------
    def team_id(self, raw: str, season_year: int | None = None) -> str:
        """Map a raw team string to its franchise id.

        Args:
            raw: Team name exactly as in the source.
            season_year: When given, the alias must be valid for that season.

        Raises:
            DataValidationError: Unknown alias, or an alias used outside its validity window.
        """
        alias = self.team_aliases.get(raw)
        if alias is None:
            raise DataValidationError(f"Unmapped team name: {raw!r}")
        if season_year is not None and not alias.valid_from <= season_year <= alias.valid_to:
            raise DataValidationError(
                f"Team alias {raw!r} used in {season_year}, outside its validity window "
                f"{alias.valid_from}-{alias.valid_to}"
            )
        return alias.franchise_id

    def team_name(self, franchise_id: str) -> str:
        """Current display name of a franchise."""
        return str(self.franchises[franchise_id]["name"])

    def team_short(self, franchise_id: str) -> str:
        """Short code (e.g. ``CSK``)."""
        return str(self.franchises[franchise_id]["short"])

    # -- venues --------------------------------------------------------------------------
    def venue_id(self, raw: str) -> str:
        """Map a raw venue string to its canonical id.

        Raises:
            DataValidationError: If the venue string is not in the alias map.
        """
        vid = self.venue_aliases.get(raw)
        if vid is None:
            raise DataValidationError(f"Unmapped venue: {raw!r}")
        return vid

    def venue_attr(self, venue_id: str, attr: str) -> str:
        """Venue attribute: ``name``, ``city`` or ``country``."""
        return str(self.venues[venue_id][attr])

    # -- home grounds --------------------------------------------------------------------
    def is_neutral_season(self, season_year: int) -> bool:
        """True for seasons played entirely at neutral or overseas venues."""
        return season_year in self.neutral_seasons

    def is_home(self, franchise_id: str, venue_id: str, season_year: int) -> bool:
        """True if ``venue_id`` is a home ground of the franchise in that season."""
        if self.is_neutral_season(season_year):
            return False
        for spell in self.homes.get(franchise_id, []):
            if spell["from"] <= season_year <= spell["to"] and venue_id in spell["venues"]:
                return True
        return False


def load_canonical_maps(settings: Settings) -> CanonicalMaps:
    """Load and cross-check ``team_lineage``, ``venue_canonical`` and ``home_grounds`` YAML.

    Raises:
        ConfigError: If a file is malformed or references an unknown id.
    """
    return build_canonical_maps(
        load_yaml(settings.path("team_lineage")),
        load_yaml(settings.path("venue_canonical")),
        load_yaml(settings.path("home_grounds")),
    )


def load_canonical_maps_from(root: Path) -> CanonicalMaps:
    """Convenience loader from a project root (tests, notebooks)."""
    cfg = root / "configs"
    return build_canonical_maps(
        load_yaml(cfg / "team_lineage.yaml"),
        load_yaml(cfg / "venue_canonical.yaml"),
        load_yaml(cfg / "home_grounds.yaml"),
    )


def build_canonical_maps(
    lineage: dict[str, Any], venues: dict[str, Any], homes: dict[str, Any]
) -> CanonicalMaps:
    """Validate raw YAML mappings and build :class:`CanonicalMaps`."""
    try:
        franchises = dict(lineage["franchises"])
        team_aliases = {
            alias: TeamAlias(alias, v["franchise"], int(v["valid_from"]), int(v["valid_to"]))
            for alias, v in lineage["aliases"].items()
        }
        venue_defs = dict(venues["venues"])
        venue_aliases = {str(k): str(v) for k, v in venues["aliases"].items()}
        home_spells = {k: list(v) for k, v in homes["homes"].items()}
        neutral = {int(k): str(v) for k, v in (homes.get("neutral_seasons") or {}).items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"Malformed canonical config: {exc}") from exc

    unknown_fr = {a.franchise_id for a in team_aliases.values()} - set(franchises)
    if unknown_fr:
        raise ConfigError(f"Team aliases reference unknown franchises: {sorted(unknown_fr)}")
    unknown_v = set(venue_aliases.values()) - set(venue_defs)
    if unknown_v:
        raise ConfigError(f"Venue aliases reference unknown venue ids: {sorted(unknown_v)}")
    for fid, spells in home_spells.items():
        if fid not in franchises:
            raise ConfigError(f"home_grounds references unknown franchise {fid!r}")
        for spell in spells:
            missing = set(spell["venues"]) - set(venue_defs)
            if missing:
                raise ConfigError(f"home_grounds[{fid}] references unknown venues {missing}")
    return CanonicalMaps(franchises, team_aliases, venue_defs, venue_aliases, home_spells, neutral)
