"""Shared Streamlit components: cached context, friendly errors, filters, footer (NFR-02, NFR-04)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import streamlit as st

from creaseiq.exceptions import CreaseIQError
from creaseiq.logging_setup import get_logger
from creaseiq.services.analytics_service import AnalyticsService
from creaseiq.services.context import AppContext
from creaseiq.services.prediction_service import PredictionService
from creaseiq.services.scenario_service import ScenarioService

logger = get_logger("creaseiq.app")

DISCLAIMER = (
    "CreaseIQ is an educational analytics project. Probabilities are estimates close to a coin flip "
    "and may be wrong. **Not betting, fantasy-sports or financial advice.** Not affiliated with "
    "the BCCI, the IPL, any franchise or Cricsheet. Match data © Cricsheet (cricsheet.org), ODC-BY 1.0."
)


@st.cache_resource(show_spinner="Loading data…")
def get_ctx() -> AppContext:
    """One shared context per server process."""
    return AppContext()


def analytics() -> AnalyticsService:
    """Analytics service over the shared context."""
    return AnalyticsService(get_ctx())


def predictions() -> PredictionService:
    """Prediction service over the shared context."""
    return PredictionService(get_ctx())


def scenarios() -> ScenarioService:
    """Scenario service over the shared context."""
    return ScenarioService(get_ctx())


def page_header(title: str, subtitle: str) -> None:
    """Consistent page title and one-line purpose."""
    st.title(title)
    st.caption(subtitle)


def footer() -> None:
    """Responsible-use disclaimer on every page."""
    st.divider()
    st.caption(DISCLAIMER)


@contextmanager
def friendly_errors() -> Iterator[None]:
    """Show expected errors as messages and unexpected ones generically. Never a stack trace."""
    try:
        yield
    except CreaseIQError as exc:
        st.error(str(exc))
    except Exception:
        logger.exception("Unhandled error in dashboard")
        st.error(
            "Something went wrong while building this view. The details were written to the log."
        )


def team_options(active_only: bool = True) -> dict[str, str]:
    """{display name: franchise id}, sorted by name."""
    ctx = get_ctx()
    ids = ctx.active_franchises() if active_only else list(ctx.maps.franchises)
    return dict(sorted((ctx.team_label(i), i) for i in ids))


def venue_options(recent_only: bool = True) -> dict[str, str]:
    """{display name: venue id}. By default only venues used in the last three seasons."""
    ctx = get_ctx()
    m = ctx.matches
    ids = (
        m.loc[m["season_year"] >= m["season_year"].max() - 2, "venue_id"].unique()
        if recent_only
        else list(ctx.maps.venues)
    )
    return dict(sorted((ctx.venue_label(v), str(v)) for v in ids))


def sidebar_filters(with_team: bool = True, with_venue: bool = False) -> dict[str, Any]:
    """Season range, team, venue and stage filters (FR-11)."""
    ctx = get_ctx()
    lo, hi = int(ctx.matches["season_year"].min()), int(ctx.matches["season_year"].max())
    st.sidebar.header("Filters")
    season = st.sidebar.slider("Seasons", lo, hi, (lo, hi), help="Inclusive season range")
    out: dict[str, Any] = {
        "season_from": season[0],
        "season_to": season[1],
        "team": None,
        "venue_id": None,
        "stage": None,
    }
    if with_team:
        teams = {"All teams": None, **team_options(active_only=False)}
        out["team"] = teams[
            st.sidebar.selectbox("Team", list(teams), help="Matches involving this franchise")
        ]
    if with_venue:
        venues = {"All venues": None, **venue_options(recent_only=False)}
        out["venue_id"] = venues[st.sidebar.selectbox("Venue", list(venues))]
    stages = {"All stages": None, "League": "league", "Playoffs": "playoff", "Finals": "final"}
    out["stage"] = stages[st.sidebar.selectbox("Stage", list(stages))]
    return out


def empty_state(message: str) -> None:
    """Meaningful empty state instead of a blank chart."""
    st.info(message)
