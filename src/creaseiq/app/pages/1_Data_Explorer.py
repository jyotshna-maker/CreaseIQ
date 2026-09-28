"""Data Explorer: filter, inspect, export (sanitised) and append matches (FR-05, FR-11)."""

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
)
from creaseiq.services.analytics_service import to_safe_csv
from creaseiq.services.ingest_service import process_upload

st.set_page_config(page_title="Data Explorer · CreaseIQ", page_icon="🗂️", layout="wide")
page_header(
    "🗂️ Data Explorer",
    "Every match after validation and canonicalisation. Filter, export, or append new matches.",
)

with friendly_errors():
    f = sidebar_filters(with_team=True, with_venue=True)
    svc = analytics()
    m = svc.filtered(**f)
    if m.empty:
        empty_state("No matches match these filters. Widen the season range or pick 'All teams'.")
    else:
        table = svc.explorer_table(m)
        st.caption(
            f"{len(table):,} matches shown. Scores for tied matches are regulation scores (super-over runs removed)."
        )
        st.dataframe(table, width="stretch", hide_index=True, height=460)
        st.download_button(
            "⬇️ Download CSV",
            to_safe_csv(table),
            "creaseiq_matches.csv",
            "text/csv",
            help="Cells that start with =, +, - or @ are escaped to prevent spreadsheet formula injection.",
        )

    st.subheader("Append new matches")
    st.caption(
        "Upload a CSV with exactly the 31 raw columns (maximum 5 MB). A dry run validates first, and nothing is written unless you confirm. The original raw file is never modified."
    )
    upload = st.file_uploader("Match CSV", type=["csv"], accept_multiple_files=False)
    if upload is not None:
        ctx = get_ctx()
        content = upload.getvalue()
        report = process_upload(ctx.settings, content, upload.name, dry_run=True)
        st.write(report.as_dict())
        if report.rows_new and st.button("Apply upload", type="primary"):
            final = process_upload(ctx.settings, content, upload.name, dry_run=False)
            st.success(" ".join(final.messages))
            st.cache_resource.clear()
footer()
