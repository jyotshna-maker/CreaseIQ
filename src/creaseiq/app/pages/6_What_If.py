"""What-If: how the toss, venue or opponent shifts the odds; hypothetical season simulation (FR-19, FR-20)."""

from __future__ import annotations

import streamlit as st

from creaseiq.app.components import (
    footer,
    friendly_errors,
    page_header,
    scenarios,
    team_options,
    venue_options,
)
from creaseiq.services.prediction_service import PredictionRequest
from creaseiq.viz import charts

st.set_page_config(page_title="What-If · CreaseIQ", page_icon="🔀", layout="wide")
page_header("🔀 What-If", "Change one thing at a time and see how the win probability moves.")

with friendly_errors():
    teams, venues = team_options(), venue_options()
    names, vnames = list(teams), list(venues)
    c1, c2, c3 = st.columns(3)
    team_a = c1.selectbox(
        "Team A",
        names,
        index=names.index("Royal Challengers Bengaluru")
        if "Royal Challengers Bengaluru" in names
        else 0,
    )
    team_b = c2.selectbox(
        "Team B", names, index=names.index("Gujarat Titans") if "Gujarat Titans" in names else 1
    )
    venue = c3.selectbox(
        "Venue",
        vnames,
        index=next((i for i, v in enumerate(vnames) if v.startswith("Narendra")), 0),
    )
    opponents = st.checkbox("Also compare every other opponent")
    if st.button("Run what-if", type="primary"):
        table = scenarios().what_if(
            PredictionRequest(teams[team_a], teams[team_b], venues[venue]),
            include_opponents=opponents,
        )
        st.plotly_chart(charts.what_if_tornado(table, team_a), width="stretch")
        st.dataframe(
            table.style.format({"p_a": "{:.1%}", "delta": "{:+.1%}"}),
            width="stretch",
            hide_index=True,
        )

    st.subheader("Hypothetical season simulation")
    st.caption(
        "A double round-robin plus IPL playoffs, simulated 10,000 times with the pre-toss model. Illustrative only: squads change every auction."
    )
    if st.button("Simulate a season"):
        odds = scenarios().season_odds()
        st.plotly_chart(charts.title_odds(odds), width="stretch")
footer()
