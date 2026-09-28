"""Predict Match: pick two teams and a venue, then Predict (≤ 3 clicks; FR-16, NFR-04)."""

from __future__ import annotations

import streamlit as st

from creaseiq.app.components import (
    footer,
    friendly_errors,
    page_header,
    predictions,
    team_options,
    venue_options,
)
from creaseiq.services.prediction_service import STAGES, PredictionRequest
from creaseiq.viz import charts

st.set_page_config(page_title="Predict Match · CreaseIQ", page_icon="🎯", layout="wide")
page_header(
    "🎯 Predict Match",
    "Pre-match win probability, calibrated and explained. Add the toss for the post-toss model.",
)

with friendly_errors():
    teams = team_options()
    venues = venue_options()
    names = list(teams)
    c1, c2, c3 = st.columns(3)
    team_a = c1.selectbox(
        "Team A", names, index=names.index("Mumbai Indians") if "Mumbai Indians" in names else 0
    )
    team_b = c2.selectbox(
        "Team B",
        names,
        index=names.index("Chennai Super Kings") if "Chennai Super Kings" in names else 1,
    )
    venue_names = list(venues)
    venue = c3.selectbox(
        "Venue",
        venue_names,
        index=next((i for i, v in enumerate(venue_names) if v.startswith("Wankhede")), 0),
    )
    stage = st.radio(
        "Stage", STAGES, horizontal=True, format_func=lambda s: s.replace("_", " ").title()
    )
    with st.expander("Toss known? (switches to the post-toss model)"):
        toss_known = st.checkbox("Include toss")
        toss_winner = st.radio(
            "Toss winner", [team_a, team_b], horizontal=True, disabled=not toss_known
        )
        toss_decision = st.radio(
            "Decision", ["bat", "field"], horizontal=True, disabled=not toss_known
        )

    if st.button("Predict", type="primary"):
        req = PredictionRequest(
            teams[team_a],
            teams[team_b],
            venues[venue],
            None,
            stage,
            teams[toss_winner] if toss_known else None,
            toss_decision if toss_known else None,
        )
        out = predictions().predict(req)
        st.plotly_chart(
            charts.probability_bar(
                out["p_a"], out["team_a_name"], out["team_b_name"], out["team_a"], out["team_b"]
            ),
            width="stretch",
        )
        st.markdown(
            f"**{out['team_a_name']} {out['p_a']:.1%}** vs **{out['team_b_name']} {out['p_b']:.1%}** at {out['venue']} ({out['tier'].replace('_', '-')} model)."
        )
        st.info(out["explanation"])
        if out["drivers"]:
            st.plotly_chart(charts.drivers_bar(out["drivers"], out["team_a_name"]), width="stretch")
        st.caption(
            f"Model {out['model']} · run {out['model_run_id']} · trained through {out['trained_through']} · {out['latency_ms']:.0f} ms. On the 2025-26 holdout no model beat a coin flip, so treat this as a lean, not a forecast."
        )
footer()
