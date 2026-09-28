"""Team analytics: records, titles, season form, head-to-head and Elo (FR-06, FR-10)."""

from __future__ import annotations

import streamlit as st

from creaseiq.app.components import (
    analytics,
    empty_state,
    footer,
    friendly_errors,
    get_ctx,
    page_header,
    sidebar_filters,
    team_options,
)
from creaseiq.viz import charts

st.set_page_config(page_title="Team Analytics · CreaseIQ", page_icon="📊", layout="wide")
page_header(
    "📊 Team Analytics",
    "Franchise records with 95% intervals, titles, form by season, head-to-head and ratings.",
)

with friendly_errors():
    ctx = get_ctx()
    svc = analytics()
    f = sidebar_filters(with_team=False)
    m = svc.filtered(**f)
    labels = {fid: ctx.team_label(fid) for fid in ctx.maps.franchises}
    if m.empty:
        empty_state("No matches in this range.")
    else:
        table = svc.team_table(m)
        table.insert(0, "franchise", table["team"].map(labels))
        st.subheader("All-time records")
        st.caption(
            "Win % excludes no-results and ties. The interval is a 95% Wilson CI. Renamed franchises are merged (ADR-003)."
        )
        st.dataframe(
            table.drop(columns=["team"]).style.format(
                {"win_pct": "{:.1%}", "ci_low": "{:.1%}", "ci_high": "{:.1%}"}
            ),
            width="stretch",
            hide_index=True,
        )

        st.subheader("Form by season")
        options = team_options(active_only=False)
        default = [n for n, i in options.items() if i in ("csk", "mi", "rcb", "kkr")]
        chosen = st.multiselect("Teams", list(options), default=default)
        if chosen:
            st.plotly_chart(
                charts.team_season_lines(svc.season_form(m), [options[c] for c in chosen], labels),
                width="stretch",
            )

        st.subheader("Head-to-head")
        min_meet = st.slider("Minimum decided meetings", 1, 30, 8)
        matrix = svc.h2h_matrix(m, min_meet)
        if matrix.dropna(how="all").empty:
            empty_state("No pair has that many meetings in this range.")
        else:
            st.plotly_chart(charts.h2h_heatmap(matrix, labels, min_meet), width="stretch")

        st.subheader("Elo ratings")
        hist = svc.elo_history()
        if hist.empty:
            empty_state("Run `creaseiq train` to compute the tuned Elo history.")
        else:
            st.plotly_chart(
                charts.elo_lines(hist, [options[c] for c in chosen] or ["csk", "mi"], labels),
                width="stretch",
            )

        st.subheader("Player of the Match leaders")
        st.dataframe(svc.potm(m, 15), width="stretch", hide_index=True)
footer()
