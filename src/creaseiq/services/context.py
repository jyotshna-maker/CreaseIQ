"""Shared application context: settings, canonical data, database and models.

The CLI and the dashboard both create one :class:`AppContext`. Loading happens lazily so a
page that only shows analytics never has to load models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import pandas as pd
from sqlalchemy import Engine

from creaseiq.config import Settings, get_settings
from creaseiq.data.canonical import CanonicalMaps, load_canonical_maps
from creaseiq.data.pipeline import load_processed
from creaseiq.db.loader import create_schema, load_database
from creaseiq.db.repository import MatchRepository
from creaseiq.db.session import make_engine
from creaseiq.models.predict import Predictor
from creaseiq.models.registry import ModelRegistry
from creaseiq.utils import read_json


@dataclass
class AppContext:
    """Lazily loaded shared state."""

    settings: Settings = field(default_factory=get_settings)

    @cached_property
    def data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(matches, players) from the processed cache (built on first use)."""
        return load_processed(self.settings)

    @property
    def matches(self) -> pd.DataFrame:
        """Canonical match table."""
        return self.data[0]

    @property
    def players(self) -> pd.DataFrame:
        """Long squad table."""
        return self.data[1]

    @cached_property
    def maps(self) -> CanonicalMaps:
        """Canonical maps."""
        return load_canonical_maps(self.settings)

    @cached_property
    def engine(self) -> Engine:
        """Database engine; loads the canonical tables if the database is empty."""
        engine = make_engine(self.settings.db_url)
        create_schema(engine)
        if MatchRepository(engine).match_count() == 0:
            load_database(engine, self.matches, self.players, self.maps)
        return engine

    @cached_property
    def repo(self) -> MatchRepository:
        """Repository over :attr:`engine`."""
        return MatchRepository(self.engine)

    @cached_property
    def registry(self) -> ModelRegistry:
        """Model registry."""
        return ModelRegistry(self.settings.path("models_dir"))

    @cached_property
    def predictor(self) -> Predictor:
        """Hash-verified models plus history (raises ModelIntegrityError if not trained)."""
        return Predictor(self.registry, self.matches, self.players, self.maps)

    def report(self, name: str) -> dict[str, Any] | None:
        """A JSON report from ``reports/`` (``metrics``, ``analytics``, ``perf``...), if present."""
        path = self.settings.path("reports_dir") / f"{name}.json"
        if not path.exists():
            return None
        data: dict[str, Any] = read_json(path)
        return data

    def active_franchises(self) -> list[str]:
        """Franchise ids that played in the latest season (valid prediction inputs)."""
        latest = int(self.matches["season_year"].max())
        cur = self.matches[self.matches["season_year"] == latest]
        return sorted(set(cur["team1"]) | set(cur["team2"]))

    def team_label(self, franchise_id: str) -> str:
        """Display name, e.g. ``Mumbai Indians``."""
        return self.maps.team_name(franchise_id)

    def venue_label(self, venue_id: str) -> str:
        """Display name with city."""
        return f"{self.maps.venue_attr(venue_id, 'name')}, {self.maps.venue_attr(venue_id, 'city')}"
