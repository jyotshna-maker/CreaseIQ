"""Venue & Toss: toss effect with CIs, chasing advantage, scoring eras, venue profiles (FR-07..FR-09)."""

from __future__ import annotations

import streamlit as st

from creaseiq.app.components import (
    analytics,
    empty_state,
    footer,
    friendly_errors,
    page_header,
    sidebar_filters,
)
from creaseiq.viz import charts

st.set_page_config(page_title="Venue & Toss · CreaseIQ", page_icon="🪙", layout="wide")
page_header(
    "🪙 Venue & Toss",
    "Does winning the toss matter? Is chasing easier? How the Impact Player era changed scoring.",
)

with friendly_errors():
    svc = analytics()
    f = sidebar_filters(with_team=True, with_venue=True)
    m = svc.filtered(**f)
    if m["is_decided"].sum() < 20:
        empty_state(
            "Fewer than 20 decided matches in this selection: too few for meaningful statistics."
        )
    else:
        res = svc.toss(m)
        toss, chase = res["toss"]["overall"], res["chase"]["overall"]
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Toss winner won",
            f"{toss['rate']:.1%}",
            f"{100 * toss['effect']:+.1f} pp vs 50%",
            delta_color="off",
            help="Exact binomial test; the toss is random, so this is a causal estimate",
        )
        c1.caption(
            f"95% CI {toss['ci_low']:.1%}–{toss['ci_high']:.1%} · p = {toss['p_value']:.2f} · n = {toss['n']}"
        )
        c2.metric(
            "Chasing side won",
            f"{chase['rate']:.1%}",
            f"{100 * chase['effect']:+.1f} pp vs 50%",
            delta_color="off",
        )
        c2.caption(
            f"95% CI {chase['ci_low']:.1%}–{chase['ci_high']:.1%} · p = {chase['p_value']:.3f}"
        )
        c3.metric(
            "Minimum detectable effect",
            f"±{100 * toss['mde']:.1f} pp",
            help="With this many matches, smaller effects cannot be reliably detected (80% power)",
        )
        verdict = "no detectable" if toss["p_value"] >= 0.05 else "a statistically significant"
        st.info(
            f"**Verdict:** {verdict} toss effect in this selection. The data rule out toss advantages larger than about {100 * max(abs(toss['ci_low'] - 0.5), abs(toss['ci_high'] - 0.5)):.0f} pp."
        )

        left, right = st.columns(2)
        left.plotly_chart(charts.toss_decision_bars(res["toss"]["by_decision"]), width="stretch")
        left.caption(
            "Captains who field first win more often, but the decision depends on conditions and team strength. This is association, not causation."
        )
        right.plotly_chart(charts.chase_rate_by_season(res["chase"]["by_season"]), width="stretch")

        st.subheader("Scoring and the Impact Player era")
        st.plotly_chart(charts.scoring_trend(svc.scoring(m)), width="stretch")

        st.subheader("Venue profiles")
        profiles = svc.venue_profiles(m)
        st.plotly_chart(charts.venue_scatter(profiles), width="stretch")
        st.caption(
            "Estimates are shrunk toward league averages (pseudo-count 10), so small-sample venues are not over-interpreted."
        )
        clusters = svc.venue_clusters(svc.filtered())
        st.markdown(
            f"**k-means venue clusters** (all seasons; k = {clusters.k}, chosen by silhouette score {max(clusters.silhouette_by_k.values()):.2f}):"
        )
        st.dataframe(
            clusters.assignments[["venue", "matches", "label"]], width="stretch", hide_index=True
        )
footer()
