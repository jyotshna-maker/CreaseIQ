"""CreaseIQ dashboard: home page (KPIs, data freshness, quality and model status)."""

from __future__ import annotations

import streamlit as st

from creaseiq.app.components import analytics, footer, friendly_errors, get_ctx, page_header

st.set_page_config(page_title="CreaseIQ", page_icon="🏏", layout="wide")
page_header(
    "🏏 CreaseIQ: IPL Match Intelligence",
    "Validated IPL data · honest analytics · leakage-safe win probabilities",
)

with friendly_errors():
    ctx = get_ctx()
    k = analytics().kpis()
    cols = st.columns(5)
    cols[0].metric(
        "Matches",
        f"{k['matches']:,}",
        help="All matches in the dataset, including ties and no-results",
    )
    cols[1].metric(
        "Decided", f"{k['decided']:,}", help="Matches with a winner (used for modelling)"
    )
    cols[2].metric("Seasons", k["seasons"])
    cols[3].metric(
        "Franchises",
        k["franchises"],
        help="After merging renames, e.g. Delhi Daredevils → Delhi Capitals",
    )
    cols[4].metric("Venues", k["venues"], help="After canonicalising 60 raw venue spellings")
    st.markdown(
        f"**Data covers** {k['first_date']} → {k['last_date']} · **latest champion:** {k['latest_champion']}"
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Data quality")
        q = ctx.report("data_quality")
        if q:
            fixes = q["fixes"]
            st.success(
                f"Validated: {q['validation']['quarantined']} rows quarantined out of {q['raw']['rows']:,}."
            )
            st.markdown(
                f"- {fixes.get('venue_alias_canonicalised', 0)} venue spellings canonicalised\n"
                f"- {fixes.get('team_alias_canonicalised', 0)} team-name cells mapped to franchises\n"
                f"- {fixes.get('tie_innings_corrected_super_over_removed', 0)} tie rows corrected (super-over runs removed)\n"
                f"- {fixes.get('dls_flag_total', 0)} D/L-affected results flagged"
            )
            st.caption(
                f"Raw file SHA-256 `{q['raw']['sha256'][:16]}…` (immutable). Full report: docs/data_quality_report.md"
            )
        else:
            st.info("Run `creaseiq validate` to generate the data-quality report.")
    with right:
        st.subheader("Model status")
        metrics = ctx.report("metrics")
        if metrics:
            for tier, t in metrics["tiers"].items():
                h = t["holdout"]["model"]
                st.markdown(
                    f"**{tier.replace('_', '-')}** · {t['selection']['chosen']} · holdout log-loss **{h['log_loss']:.3f}** (coin flip 0.693) · accuracy {h['accuracy']:.0%}"
                )
            st.caption(
                "Honest result: pre-match IPL outcomes are close to unpredictable. See the Model Lab for details."
            )
        else:
            st.info("No trained models yet. Run `creaseiq train`.")

    st.subheader("Where to go next")
    st.markdown(
        "- **Data Explorer**: filter, export or append matches\n"
        "- **Team Analytics**: records, titles, head-to-head, Elo\n"
        "- **Venue & Toss**: does the toss matter? Chasing, venues, the Impact Player era\n"
        "- **Predict Match**: pick two teams and a venue, then click Predict\n"
        "- **Model Lab**: evaluation, calibration, baselines, drift\n"
        "- **What-If**: how the toss, the venue or the opponent changes the odds"
    )
footer()
