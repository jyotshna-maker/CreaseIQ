"""Prediction service (FR-16, FR-21, NFR-02, NFR-03).

Inputs are checked against **allow-lists** (known franchise ids, venue ids, stages, toss
decisions) before anything else runs. Every served prediction is timed and written to the
``prediction_log`` table and the structured log.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from creaseiq.exceptions import InputError
from creaseiq.logging_setup import get_logger, log_event
from creaseiq.models.predict import Fixture
from creaseiq.services.context import AppContext

logger = get_logger(__name__)
STAGES = ("league", "qualifier_1", "eliminator", "qualifier_2", "final")
TOSS_DECISIONS = ("bat", "field")


@dataclass
class PredictionRequest:
    """Raw user input (strings), validated by :meth:`PredictionService.validate`."""

    team_a: str
    team_b: str
    venue_id: str
    date: str | pd.Timestamp | None = None
    stage: str = "league"
    toss_winner: str | None = None
    toss_decision: str | None = None


class PredictionService:
    """Validates requests, predicts, explains and logs."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    def validate(self, req: PredictionRequest) -> Fixture:
        """Turn a request into a :class:`Fixture` or raise :class:`InputError`."""
        teams = set(self.ctx.maps.franchises)
        if req.team_a not in teams or req.team_b not in teams:
            raise InputError("Unknown team. Choose franchises from the list.")
        if req.team_a == req.team_b:
            raise InputError("A team cannot play itself. Pick two different teams.")
        if req.venue_id not in self.ctx.maps.venues:
            raise InputError("Unknown venue. Choose a venue from the list.")
        if req.stage not in STAGES:
            raise InputError(f"Stage must be one of {', '.join(STAGES)}.")
        toss_given = req.toss_winner is not None or req.toss_decision is not None
        if toss_given:
            if req.toss_winner not in (req.team_a, req.team_b):
                raise InputError("The toss winner must be one of the two teams.")
            if req.toss_decision not in TOSS_DECISIONS:
                raise InputError("Toss decision must be 'bat' or 'field'.")
        try:
            date = (
                pd.Timestamp(req.date)
                if req.date is not None
                else self.ctx.matches["date"].max() + pd.Timedelta(days=1)
            )
        except (ValueError, TypeError) as exc:
            raise InputError("Date must look like YYYY-MM-DD.") from exc
        if pd.isna(date) or not pd.Timestamp("2008-04-18") <= date <= pd.Timestamp("2100-01-01"):
            raise InputError("Date must be between the first IPL match (2008-04-18) and 2100.")
        return Fixture(
            req.team_a,
            req.team_b,
            req.venue_id,
            pd.Timestamp(date),
            req.stage,
            req.toss_winner if toss_given else None,
            req.toss_decision if toss_given else None,
        )

    def predict(self, req: PredictionRequest, log: bool = True) -> dict[str, Any]:
        """Validated, logged prediction with latency in milliseconds."""
        fx = self.validate(req)
        start = time.perf_counter()
        out = self.ctx.predictor.predict(fx)
        latency_ms = (time.perf_counter() - start) * 1000
        out.update(
            {
                "team_a": fx.team_a,
                "team_b": fx.team_b,
                "team_a_name": self.ctx.team_label(fx.team_a),
                "team_b_name": self.ctx.team_label(fx.team_b),
                "venue": self.ctx.venue_label(fx.venue_id),
                "date": fx.date.strftime("%Y-%m-%d"),
                "latency_ms": latency_ms,
            }
        )
        if log:
            toss = (
                {"winner": fx.toss_winner, "decision": fx.toss_decision}
                if fx.tier == "post_toss"
                else None
            )
            self.ctx.repo.log_prediction(
                run_id=out["model_run_id"],
                tier=fx.tier,
                team_a=fx.team_a,
                team_b=fx.team_b,
                venue_id=fx.venue_id,
                stage=fx.stage,
                toss=toss,
                p_a=out["p_a"],
                latency_ms=latency_ms,
            )
            log_event(
                logger,
                "prediction",
                tier=fx.tier,
                team_a=fx.team_a,
                team_b=fx.team_b,
                venue=fx.venue_id,
                p_a=round(out["p_a"], 4),
                latency_ms=round(latency_ms, 2),
            )
        return out
