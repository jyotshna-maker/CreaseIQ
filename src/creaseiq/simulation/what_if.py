"""What-if scenarios (FR-19): change the toss, venue or opponent and see how P(A wins) moves.

Each scenario is a modified :class:`Fixture`, predicted with the same registered models.
The result is a tornado-style table of scenario, probability and Δ against the baseline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pandas as pd

from creaseiq.models.predict import Fixture

PredictFn = Callable[[Fixture], float]


def toss_scenarios(base: Fixture) -> list[tuple[str, Fixture]]:
    """All four toss outcomes (winner × decision), which switch to the post-toss tier."""
    out = []
    for winner in (base.team_a, base.team_b):
        for decision in ("bat", "field"):
            out.append(
                (
                    f"{winner} wins toss, chooses to {decision}",
                    replace(base, toss_winner=winner, toss_decision=decision),
                )
            )
    return out


def venue_scenarios(base: Fixture, venues: dict[str, str]) -> list[tuple[str, Fixture]]:
    """Alternative venues, given as ``{label: venue_id}`` (e.g. each side's home, a neutral ground)."""
    return [
        (f"played at {label}", replace(base, venue_id=vid))
        for label, vid in venues.items()
        if vid != base.venue_id
    ]


def opponent_scenarios(base: Fixture, opponents: list[str]) -> list[tuple[str, Fixture]]:
    """Same team A and conditions against a different opponent."""
    return [
        (f"vs {opp}", replace(base, team_b=opp))
        for opp in opponents
        if opp not in (base.team_a, base.team_b)
    ]


def run_what_if(
    base: Fixture, scenarios: list[tuple[str, Fixture]], predict: PredictFn
) -> pd.DataFrame:
    """Probability for the baseline and each scenario, sorted by |Δ| (tornado order)."""
    p0 = predict(base)
    rows = [{"scenario": "baseline", "tier": base.tier, "p_a": p0, "delta": 0.0}]
    for label, fx in scenarios:
        p = predict(fx)
        rows.append({"scenario": label, "tier": fx.tier, "p_a": p, "delta": p - p0})
    df = pd.DataFrame(rows)
    head, rest = df.iloc[:1], df.iloc[1:]
    rest = rest.reindex(rest["delta"].abs().sort_values(ascending=False).index)
    return pd.concat([head, rest], ignore_index=True)
