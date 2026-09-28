"""Model Lab: evaluation, baselines, calibration, ablation, drift and the prediction log (FR-15, FR-21)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from creaseiq.app.components import empty_state, footer, friendly_errors, get_ctx, page_header
from creaseiq.viz import charts

st.set_page_config(page_title="Model Lab · CreaseIQ", page_icon="🧪", layout="wide")
page_header(
    "🧪 Model Lab",
    "How good are the models really? Walk-forward validation, a one-shot holdout, baselines and calibration.",
)

with friendly_errors():
    ctx = get_ctx()
    metrics = ctx.report("metrics")
    if metrics is None:
        empty_state("No evaluation yet. Run `creaseiq train`.")
    else:
        tier = st.radio(
            "Tier",
            list(metrics["tiers"]),
            horizontal=True,
            format_func=lambda t: t.replace("_", "-"),
        )
        t = metrics["tiers"][tier]
        h = t["holdout"]["model"]
        ci = h["ci"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Holdout log-loss",
            f"{h['log_loss']:.4f}",
            f"{h['log_loss'] - 0.6931:+.4f} vs coin",
            delta_color="inverse",
        )
        c2.metric(
            "Accuracy",
            f"{h['accuracy']:.1%}",
            help=f"95% CI {ci['accuracy']['low']:.1%}–{ci['accuracy']['high']:.1%}",
        )
        c3.metric(
            "AUC", f"{h['auc']:.3f}", help=f"95% CI {ci['auc']['low']:.3f}–{ci['auc']['high']:.3f}"
        )
        c4.metric("ECE (equal-mass)", f"{h['ece']:.3f}")
        acc = t["holdout_access"]
        st.caption(
            f"Holdout = 2025-26 (n = {h['n']}). Selection frozen and hashed ({acc['selection_hash']}) before evaluation; evaluations of this selection: {acc['evaluations_of_this_selection']}."
        )

        st.subheader("Holdout vs baselines (paired bootstrap; negative Δ = model better)")
        rows = [
            {
                "baseline": k,
                "Δ log-loss": v["diff"],
                "95% CI low": v["ci_low"],
                "95% CI high": v["ci_high"],
                "P(model not better)": v["p_not_better"],
                "DM p-value": v["diebold_mariano"]["p_value"],
            }
            for k, v in t["holdout_vs_baselines"].items()
        ]
        st.dataframe(pd.DataFrame(rows).style.format(precision=4), width="stretch", hide_index=True)

        left, right = st.columns(2)
        left.plotly_chart(
            charts.reliability(t["holdout_reliability"], "Holdout reliability (equal-mass bins)"),
            width="stretch",
        )
        with right:
            st.markdown("**Model selection (walk-forward, development seasons)**")
            fam = pd.DataFrame(
                [
                    {"model": k, "mean log-loss": v["mean_log_loss"], "std": v["std_log_loss"]}
                    for k, v in t["best_per_family"].items()
                ]
            )
            base = pd.DataFrame(
                [
                    {"model": k, "mean log-loss": v["mean_log_loss"], "std": v["std_log_loss"]}
                    for k, v in t["baselines_walk_forward"].items()
                ]
            )
            st.dataframe(
                pd.concat([fam, base]).sort_values("mean log-loss").style.format(precision=4),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                f"Chosen: **{t['selection']['chosen']}** by the {t['selection']['rule']} rule; calibration: **{t['calibration']['chosen']}**."
            )

        st.subheader("Ablation")
        st.dataframe(
            pd.DataFrame(t["ablation"]).style.format({"mean_log_loss": "{:.4f}"}),
            width="stretch",
            hide_index=True,
        )
        st.subheader("Feature drift")
        st.plotly_chart(charts.drift_bar(metrics["drift"]["table"]), width="stretch")
        st.caption(
            "PSI > 0.25 means a major shift. The Impact Player era moved scoring features far outside their training range."
        )

    st.subheader("Recent predictions")
    log = ctx.repo.prediction_log(20)
    if log.empty:
        empty_state("No predictions logged yet.")
    else:
        st.dataframe(log, width="stretch", hide_index=True)
footer()
