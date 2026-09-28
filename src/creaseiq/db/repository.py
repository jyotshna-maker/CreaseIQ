"""Read/write API over the database. All SQL is built with SQLAlchemy Core (parameterised,
never f-strings), so user input can never change a query's structure (NFR-03)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import Engine, delete, func, insert, select, text
from sqlalchemy.orm import Session

from creaseiq.db.models import (
    Franchise,
    Match,
    MatchPlayer,
    ModelRun,
    Player,
    PredictionLog,
    Season,
    Venue,
)


class MatchRepository:
    """Query helpers returning DataFrames (FR-04, FR-21)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _frame(self, stmt: Any) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(stmt, conn)

    # -- reads ------------------------------------------------------------------------------
    def franchises(self) -> pd.DataFrame:
        """All franchises."""
        return self._frame(select(Franchise).order_by(Franchise.canonical_name))

    def venues(self) -> pd.DataFrame:
        """All venues."""
        return self._frame(select(Venue).order_by(Venue.canonical_name))

    def seasons(self) -> pd.DataFrame:
        """All seasons with champion."""
        return self._frame(select(Season).order_by(Season.season_year))

    def matches(
        self,
        season_from: int | None = None,
        season_to: int | None = None,
        team_id: str | None = None,
    ) -> pd.DataFrame:
        """Matches, optionally filtered by season range and team (bound parameters)."""
        stmt = select(Match, Season.season_year).join(Season, Season.season_id == Match.season_id)
        if season_from is not None:
            stmt = stmt.where(Season.season_year >= season_from)
        if season_to is not None:
            stmt = stmt.where(Season.season_year <= season_to)
        if team_id is not None:
            stmt = stmt.where((Match.team1_id == team_id) | (Match.team2_id == team_id))
        return self._frame(stmt.order_by(Match.date, Match.match_id))

    def match_players(self, match_id: int) -> pd.DataFrame:
        """Squads for one match."""
        stmt = (
            select(MatchPlayer.team_id, MatchPlayer.slot_no, Player.name)
            .join(Player, Player.player_id == MatchPlayer.player_id)
            .where(MatchPlayer.match_id == match_id)
            .order_by(MatchPlayer.team_id, MatchPlayer.slot_no)
        )
        return self._frame(stmt)

    def team_season_summary(self) -> pd.DataFrame:
        """Rows of the ``v_team_season_summary`` view."""
        return self._frame(
            text("SELECT * FROM v_team_season_summary ORDER BY season_year, franchise_id")
        )

    def head_to_head(self, team_id: str | None = None) -> pd.DataFrame:
        """Rows of the ``v_head_to_head`` view, optionally for one team (bound parameter)."""
        if team_id is None:
            return self._frame(text("SELECT * FROM v_head_to_head ORDER BY team_id, opponent_id"))
        stmt = text(
            "SELECT * FROM v_head_to_head WHERE team_id = :team ORDER BY opponent_id"
        ).bindparams(team=team_id)
        return self._frame(stmt)

    def match_count(self) -> int:
        """Number of matches stored."""
        with Session(self.engine) as s:
            return int(s.execute(select(func.count()).select_from(Match)).scalar_one())

    # -- operational writes -----------------------------------------------------------------
    def log_prediction(
        self,
        *,
        run_id: str | None,
        tier: str,
        team_a: str,
        team_b: str,
        venue_id: str,
        stage: str,
        toss: dict[str, Any] | None,
        p_a: float,
        latency_ms: float,
    ) -> None:
        """Append one row to ``prediction_log`` (FR-21)."""
        with self.engine.begin() as conn:
            conn.execute(
                insert(PredictionLog).values(
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    run_id=run_id,
                    tier=tier,
                    team_a_id=team_a,
                    team_b_id=team_b,
                    venue_id=venue_id,
                    stage=stage,
                    toss_json=None if toss is None else json.dumps(toss, sort_keys=True),
                    p_a=float(p_a),
                    latency_ms=float(latency_ms),
                )
            )

    def prediction_log(self, limit: int = 100) -> pd.DataFrame:
        """Most recent predictions."""
        return self._frame(
            select(PredictionLog).order_by(PredictionLog.prediction_id.desc()).limit(limit)
        )

    def record_model_run(self, record: dict[str, Any]) -> None:
        """Insert or replace a ``model_run`` row (FR-18)."""
        with self.engine.begin() as conn:
            conn.execute(delete(ModelRun).where(ModelRun.run_id == record["run_id"]))
            conn.execute(insert(ModelRun).values(**record))

    def model_runs(self) -> pd.DataFrame:
        """All registered model runs."""
        return self._frame(select(ModelRun).order_by(ModelRun.created_at))
