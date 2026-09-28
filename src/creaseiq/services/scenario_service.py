"""Scenario service: what-if analysis (FR-19) and hypothetical season simulation (FR-20)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from creaseiq.data.canonical import CanonicalMaps
from creaseiq.models.predict import Fixture
from creaseiq.services.context import AppContext
from creaseiq.services.prediction_service import PredictionRequest, PredictionService
from creaseiq.simulation.season_monte_carlo import simulate_season
from creaseiq.simulation.what_if import (
    opponent_scenarios,
    run_what_if,
    toss_scenarios,
    venue_scenarios,
)


def primary_home(maps: CanonicalMaps, team: str, season_year: int) -> str | None:
    """The first listed home venue of ``team`` valid in ``season_year``."""
    for spell in maps.homes.get(team, []):
        if spell["from"] <= season_year <= spell["to"]:
            return str(spell["venues"][0])
    return None


class ScenarioService:
    """What-if and Monte Carlo on top of the prediction service."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.predictions = PredictionService(ctx)

    def what_if(self, req: PredictionRequest, include_opponents: bool = False) -> pd.DataFrame:
        """Δ-probability table for toss outcomes, home/neutral venues and (optionally) opponents."""
        base = self.predictions.validate(req)
        season = int(base.date.year)
        venues = {}
        for team in (base.team_a, base.team_b):
            home = primary_home(self.ctx.maps, team, season)
            if home:
                venues[f"{self.ctx.team_label(team)} home ({self.ctx.venue_label(home)})"] = home
        venues["a neutral ground (Dubai)"] = "dubai_ics"
        scenarios = toss_scenarios(base) + venue_scenarios(base, venues)
        if include_opponents:
            scenarios += opponent_scenarios(base, self.ctx.active_franchises())
        labels = {t: self.ctx.team_label(t) for t in self.ctx.maps.franchises}

        def predict(fx: Fixture) -> float:
            return float(self.ctx.predictor.predict(fx)["p_a"])

        table = run_what_if(base, scenarios, predict)
        for fid, name in labels.items():
            table["scenario"] = (
                table["scenario"]
                .str.replace(f"vs {fid}", f"vs {name}", regex=False)
                .str.replace(f"{fid} wins toss", f"{name} wins toss", regex=False)
            )
        return table

    def season_odds(self, n_sims: int = 10_000) -> pd.DataFrame:
        """Hypothetical title odds for the active franchises (pre-toss model, home venues)."""
        teams = self.ctx.active_franchises()
        date = self.ctx.matches["date"].max() + pd.Timedelta(days=1)
        season = int(date.year)
        p = np.full((len(teams), len(teams)), 0.5)
        for i, a in enumerate(teams):
            venue = primary_home(self.ctx.maps, a, season) or "dubai_ics"
            for j, b in enumerate(teams):
                if i != j:
                    p[i, j] = self.ctx.predictor.predict(Fixture(a, b, venue, date))["p_a"]
        out = simulate_season(teams, p, n_sims, self.ctx.settings.seed)
        out["team_name"] = out["team"].map(self.ctx.team_label)
        return out
