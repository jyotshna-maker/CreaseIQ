"""Serving-time prediction (FR-16).

:class:`Predictor` loads the registered, hash-verified bundle for each tier. It builds the
feature state **as of** the prediction date (every match strictly before it), featurises
the fixture, and returns a symmetrised, calibrated probability with drivers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from creaseiq.data.canonical import CanonicalMaps
from creaseiq.features.builder import FeatureBuilder, MatchState, Tier, swap_orientation
from creaseiq.models.explain import driver_sentence, linear_contributions, logistic_component
from creaseiq.models.registry import ModelBundle, ModelRegistry


@dataclass
class Fixture:
    """A match to predict. Toss fields switch the prediction to the post-toss tier."""

    team_a: str
    team_b: str
    venue_id: str
    date: pd.Timestamp
    stage: str = "league"
    toss_winner: str | None = None
    toss_decision: str | None = None  # "bat" or "field"
    xi_a: frozenset[str] | None = None
    xi_b: frozenset[str] | None = None

    @property
    def tier(self) -> Tier:
        """``post_toss`` when the toss is known."""
        return "post_toss" if self.toss_winner and self.toss_decision else "pre_toss"

    @property
    def bat_first(self) -> str | None:
        """The team batting first, derived from the toss."""
        if not (self.toss_winner and self.toss_decision):
            return None
        other = self.team_b if self.toss_winner == self.team_a else self.team_a
        return self.toss_winner if self.toss_decision == "bat" else other


class Predictor:
    """Loads models once and predicts fixtures from match history."""

    def __init__(
        self,
        registry: ModelRegistry,
        matches: pd.DataFrame,
        players: pd.DataFrame,
        maps: CanonicalMaps,
    ) -> None:
        self.matches = matches
        self.players = players
        self.maps = maps
        self.bundles: dict[str, tuple[ModelBundle, dict[str, Any]]] = {
            t: registry.load(t) for t in ("pre_toss", "post_toss")
        }
        self._state_cache: dict[tuple[str, pd.Timestamp], MatchState] = {}

    def _state(self, tier: Tier, date: pd.Timestamp) -> MatchState:
        bundle = self.bundles[tier][0]
        last = self.matches["date"].max()
        # Any date after the last match shares one state (all history), so cache by the effective cut-off.
        key_date = min(pd.Timestamp(date), last + pd.Timedelta(days=1))
        key = (tier, key_date)
        if key not in self._state_cache:
            self._state_cache[key] = FeatureBuilder(bundle.feature_params).state_as_of(
                self.matches, self.players, key_date
            )
        return self._state_cache[key]

    def feature_row(self, fx: Fixture) -> pd.DataFrame:
        """Allow-listed features for the fixture from team A's side."""
        tier = fx.tier
        state = self._state(tier, fx.date)
        season = int(pd.Timestamp(fx.date).year)
        row = state.pair_features(
            fx.team_a, fx.team_b, venue_id=fx.venue_id, date=pd.Timestamp(fx.date), season_year=season,
            is_playoff=fx.stage != "league",
            a_home=self.maps.is_home(fx.team_a, fx.venue_id, season), b_home=self.maps.is_home(fx.team_b, fx.venue_id, season),
            toss_winner=fx.toss_winner, bat_first=fx.bat_first, xi_a=fx.xi_a, xi_b=fx.xi_b,
        )  # fmt: skip
        return pd.DataFrame([row])[self.bundles[tier][0].feature_columns].astype(float)

    def predict(self, fx: Fixture) -> dict[str, Any]:
        """Symmetrised, calibrated P(team A wins) plus drivers and model metadata."""
        tier = fx.tier
        bundle, entry = self.bundles[tier]
        x = self.feature_row(fx)
        p_raw = float(bundle.model.predict_proba(x)[0])
        p = float(bundle.calibrator.symmetric_transform(np.array([p_raw]))[0])
        drivers: list[dict[str, Any]] = []
        sentence = "Drivers are unavailable for this model type."
        lin = logistic_component(bundle.model)
        if lin is not None:
            contrib = linear_contributions(lin, x)
            drivers = contrib.head(5).to_dict(orient="records")
            sentence = driver_sentence(
                contrib, self.maps.team_name(fx.team_a), self.maps.team_name(fx.team_b)
            )
        return {
            "p_a": p,
            "p_b": 1.0 - p,
            "tier": tier,
            "model": bundle.model_name,
            "model_run_id": entry["run_id"],
            "trained_through": bundle.trained_through,
            "drivers": drivers,
            "explanation": sentence,
            "features": x.iloc[0].to_dict(),
        }

    def swap_check(self, fx: Fixture) -> float:
        """|p(A,B) − (1 − p(B,A))|; exactly 0 by construction (symmetrisation)."""
        bundle = self.bundles[fx.tier][0]
        x = self.feature_row(fx)
        p_ab = bundle.calibrator.symmetric_transform(bundle.model.predict_proba(x))
        p_ba = bundle.calibrator.symmetric_transform(
            bundle.model.predict_proba(swap_orientation(x, fx.tier))
        )
        return float(abs(p_ab[0] - (1 - p_ba[0])))
