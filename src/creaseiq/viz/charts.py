"""Plotly chart builders for the dashboard and notebooks (FR-06..FR-11, FR-16, FR-19).

Every builder takes plain DataFrames or dicts (outputs of the analytics and model layers)
and returns a :class:`plotly.graph_objects.Figure`. Titles state the sample size.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from creaseiq.viz.theme import ACCENT, LAYOUT, NEGATIVE, NEUTRAL, POSITIVE, team_color


def _fig(title: str, **kw: Any) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title={"text": title, "x": 0.01}, **LAYOUT, **kw)
    return fig


def probability_bar(
    p_a: float, name_a: str, name_b: str, id_a: str = "", id_b: str = ""
) -> go.Figure:
    """Horizontal split bar of the two teams' win probabilities."""
    fig = _fig("Win probability", height=180, showlegend=False)
    fig.add_bar(
        y=[""],
        x=[p_a],
        orientation="h",
        marker_color=team_color(id_a) if id_a else ACCENT,
        name=name_a,
        text=[f"{name_a} {p_a:.0%}"],
        textposition="inside",
        insidetextanchor="start",
    )
    fig.add_bar(
        y=[""],
        x=[1 - p_a],
        orientation="h",
        marker_color=team_color(id_b) if id_b else NEUTRAL,
        name=name_b,
        text=[f"{name_b} {1 - p_a:.0%}"],
        textposition="inside",
        insidetextanchor="end",
    )
    fig.update_layout(
        barmode="stack",
        xaxis={"range": [0, 1], "tickformat": ".0%"},
        margin={"l": 10, "r": 10, "t": 40, "b": 20},
    )
    fig.update_traces(textfont={"color": "white", "size": 14})
    return fig


def drivers_bar(drivers: list[dict[str, Any]], name_a: str) -> go.Figure:
    """Top feature contributions to the logit (positive favours team A)."""
    df = pd.DataFrame(drivers)
    fig = _fig(f"What drives the prediction (positive = favours {name_a})", height=320)
    if df.empty:
        return fig
    df = df.iloc[::-1]
    fig.add_bar(
        x=df["contribution"],
        y=df["label"],
        orientation="h",
        marker_color=[POSITIVE if c > 0 else NEGATIVE for c in df["contribution"]],
        hovertemplate="%{y}: %{x:+.3f} logit<extra></extra>",
    )
    fig.update_layout(xaxis_title="contribution to log-odds")
    return fig


def team_season_lines(form: pd.DataFrame, teams: list[str], labels: dict[str, str]) -> go.Figure:
    """Season win% per team, with the Impact Player era marked."""
    fig = _fig(f"Win % by season ({len(teams)} teams)", yaxis_tickformat=".0%")
    for t in teams:
        d = form[form["team"] == t].sort_values("season_year")
        fig.add_scatter(
            x=d["season_year"],
            y=d["win_pct"],
            mode="lines+markers",
            name=labels.get(t, t),
            line={"color": team_color(t)},
            customdata=d[["wins", "decided"]],
            hovertemplate="%{x}: %{y:.0%} (%{customdata[0]}/%{customdata[1]})<extra>"
            + labels.get(t, t)
            + "</extra>",
        )
    fig.add_vrect(
        x0=2022.5,
        x1=float(form["season_year"].max()) + 0.5,
        fillcolor=NEUTRAL,
        opacity=0.1,
        line_width=0,
        annotation_text="Impact Player era",
        annotation_position="top left",
    )
    return fig


def h2h_heatmap(matrix: pd.DataFrame, labels: dict[str, str], min_meetings: int) -> go.Figure:
    """Row team's win% against column team (blank below the meeting threshold)."""
    names = [labels.get(c, c) for c in matrix.columns]
    rows = [labels.get(r, r) for r in matrix.index]
    fig = _fig(f"Head-to-head win % (row vs column, ≥ {min_meetings} decided meetings)", height=560)
    fig.add_heatmap(
        z=matrix.to_numpy(),
        x=names,
        y=rows,
        colorscale="RdBu",
        zmid=0.5,
        zmin=0,
        zmax=1,
        hovertemplate="%{y} vs %{x}: %{z:.0%}<extra></extra>",
        colorbar={"tickformat": ".0%"},
    )
    fig.update_layout(xaxis={"tickangle": -40})
    return fig


def elo_lines(history: pd.DataFrame, teams: list[str], labels: dict[str, str]) -> go.Figure:
    """Post-match Elo rating over time."""
    fig = _fig("Elo rating history (tuned, margin-aware)")
    for t in teams:
        h = history[history["team"] == t].sort_values("date")
        fig.add_scatter(
            x=h["date"],
            y=h["rating_before"] + h["delta"],
            mode="lines",
            name=labels.get(t, t),
            line={"color": team_color(t)},
        )
    fig.add_hline(y=1500, line_dash="dot", line_color=NEUTRAL)
    return fig


def venue_scatter(profiles: pd.DataFrame, min_matches: int = 10) -> go.Figure:
    """Shrunk venue scoring vs chase win rate; bubble size = matches."""
    d = profiles[profiles["matches"] >= min_matches]
    fig = _fig(f"Venue profiles ({len(d)} venues with ≥ {min_matches} matches; shrunk estimates)")
    fig.add_scatter(
        x=d["avg_first_innings_shrunk"],
        y=d["chase_win_rate_shrunk"],
        mode="markers+text",
        text=d["venue"].str.split(",").str[0],
        textposition="top center",
        textfont={"size": 9},
        marker={"size": np.sqrt(d["matches"]) * 3, "color": ACCENT, "opacity": 0.6},
        customdata=d[["matches"]],
        hovertemplate="%{text}<br>avg 1st inns %{x:.0f}<br>chase win %{y:.0%}<br>n=%{customdata[0]}<extra></extra>",
    )
    fig.add_hline(y=0.5, line_dash="dot", line_color=NEUTRAL)
    fig.update_layout(
        xaxis_title="avg first-innings score (shrunk)",
        yaxis_title="chasing side win rate (shrunk)",
        yaxis_tickformat=".0%",
        height=520,
    )
    return fig


def chase_rate_by_season(by_season: pd.DataFrame) -> go.Figure:
    """Chasing side's win rate per season with 95% Wilson intervals."""
    n = int(by_season["n"].sum())
    fig = _fig(
        f"Chasing side win rate by season (95% CI; n = {n} decided matches)", yaxis_tickformat=".0%"
    )
    fig.add_scatter(
        x=by_season["season_year"],
        y=by_season["rate"],
        mode="markers",
        marker={"color": ACCENT, "size": 9},
        error_y={
            "type": "data",
            "symmetric": False,
            "array": by_season["ci_high"] - by_season["rate"],
            "arrayminus": by_season["rate"] - by_season["ci_low"],
        },
        customdata=by_season[["successes", "n"]],
        hovertemplate="%{x}: %{y:.0%} (%{customdata[0]}/%{customdata[1]})<extra></extra>",
        name="chasing side",
    )
    fig.add_hline(y=0.5, line_dash="dot", line_color=NEUTRAL)
    return fig


def scoring_trend(scoring: pd.DataFrame) -> go.Figure:
    """Mean first-innings score and share of 200+ totals per season."""
    fig = _fig(f"First-innings scoring by season (n = {int(scoring['matches'].sum())} innings)")
    fig.add_bar(
        x=scoring["season_year"],
        y=scoring["share_200_plus"],
        name="share ≥ 200",
        marker_color=NEGATIVE,
        opacity=0.45,
        yaxis="y2",
        hovertemplate="%{x}: %{y:.0%} of innings ≥ 200<extra></extra>",
    )
    fig.add_scatter(
        x=scoring["season_year"],
        y=scoring["mean_first_innings"],
        mode="lines+markers",
        name="mean score",
        line={"color": ACCENT},
    )
    fig.update_layout(
        yaxis={"title": "runs"},
        yaxis2={
            "overlaying": "y",
            "side": "right",
            "tickformat": ".0%",
            "showgrid": False,
            "title": "share ≥ 200",
        },
    )
    fig.add_vrect(
        x0=2022.5,
        x1=float(scoring["season_year"].max()) + 0.5,
        fillcolor=NEUTRAL,
        opacity=0.1,
        line_width=0,
    )
    return fig


def toss_decision_bars(by_decision: pd.DataFrame) -> go.Figure:
    """Toss winners' win rate by their decision (associational)."""
    fig = _fig(
        "Toss winner's win rate by decision (associational, 95% CI)",
        yaxis_tickformat=".0%",
        height=360,
    )
    fig.add_bar(
        x=by_decision["toss_decision"],
        y=by_decision["rate"],
        marker_color=ACCENT,
        error_y={
            "type": "data",
            "symmetric": False,
            "array": by_decision["ci_high"] - by_decision["rate"],
            "arrayminus": by_decision["rate"] - by_decision["ci_low"],
        },
        text=[f"n={n}" for n in by_decision["n"]],
        textposition="outside",
    )
    fig.add_hline(y=0.5, line_dash="dot", line_color=NEUTRAL)
    return fig


def reliability(rows: list[dict[str, Any]], title: str) -> go.Figure:
    """Reliability diagram from equal-mass bins."""
    df = pd.DataFrame(rows)
    fig = _fig(title, xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=380)
    fig.add_scatter(
        x=[0.3, 0.7],
        y=[0.3, 0.7],
        mode="lines",
        line={"dash": "dash", "color": NEUTRAL},
        name="perfect",
    )
    if not df.empty:
        fig.add_scatter(
            x=df["mean_pred"],
            y=df["observed"],
            mode="lines+markers",
            name="model",
            marker={"size": 4 + df["n"] / df["n"].max() * 8, "color": ACCENT},
            customdata=df[["n"]],
            hovertemplate="pred %{x:.0%} → obs %{y:.0%} (n=%{customdata[0]})<extra></extra>",
        )
    fig.update_layout(xaxis_title="predicted", yaxis_title="observed")
    return fig


def what_if_tornado(table: pd.DataFrame, name_a: str) -> go.Figure:
    """Δ P(team A wins) for each scenario against the baseline."""
    d = table[table["scenario"] != "baseline"].iloc[::-1]
    base = float(table.loc[table["scenario"] == "baseline", "p_a"].iloc[0])
    fig = _fig(
        f"What-if: change in P({name_a} wins) from baseline {base:.1%}",
        height=max(300, 40 * len(d) + 120),
    )
    fig.add_bar(
        x=d["delta"],
        y=d["scenario"],
        orientation="h",
        marker_color=[POSITIVE if v > 0 else NEGATIVE for v in d["delta"]],
        customdata=d[["p_a"]],
        hovertemplate="%{y}<br>Δ %{x:+.1%} → %{customdata[0]:.1%}<extra></extra>",
    )
    fig.update_layout(xaxis={"tickformat": "+.1%", "title": "Δ probability"})
    return fig


def title_odds(df: pd.DataFrame) -> go.Figure:
    """Hypothetical title and top-4 odds from the season simulation."""
    d = df.iloc[::-1]
    fig = _fig(
        "Hypothetical season simulation (10,000 runs): title and top-4 odds",
        height=420,
        xaxis_tickformat=".0%",
    )
    fig.add_bar(
        x=d["p_top4"],
        y=d["team_name"],
        orientation="h",
        name="top 4",
        marker_color=NEUTRAL,
        opacity=0.5,
    )
    fig.add_bar(
        x=d["p_title"],
        y=d["team_name"],
        orientation="h",
        name="title",
        marker_color=[team_color(t) for t in d["team"]],
    )
    fig.update_layout(barmode="overlay")
    return fig


def drift_bar(table: list[dict[str, Any]]) -> go.Figure:
    """Population Stability Index per feature (latest season vs development seasons)."""
    df = pd.DataFrame(table).sort_values("psi")
    colors = {"stable": POSITIVE, "warn": "#E69F00", "alert": NEGATIVE}
    fig = _fig(
        "Feature drift (PSI): latest season vs training period", height=max(320, 22 * len(df) + 100)
    )
    fig.add_bar(
        x=df["psi"].clip(upper=3),
        y=df["feature"],
        orientation="h",
        marker_color=[colors[s] for s in df["status"]],
        customdata=df[["psi", "status"]],
        hovertemplate="%{y}: PSI %{customdata[0]:.2f} (%{customdata[1]})<extra></extra>",
    )
    fig.add_vline(x=0.1, line_dash="dot", line_color=NEUTRAL)
    fig.add_vline(x=0.25, line_dash="dot", line_color=NEGATIVE)
    fig.update_layout(xaxis_title="PSI (capped at 3 for display)")
    return fig
