"""Shared visual theme (NFR-04).

Team colours come from Paul Tol's colour-blind-safe "muted" scheme plus the Okabe–Ito
palette. Defunct franchises share neutral greys. Colour is never the only carrier of
meaning: charts also label lines, bars and hover text.
"""

from __future__ import annotations

TEAM_COLORS: dict[str, str] = {
    "csk": "#DDCC77",  # sand
    "mi": "#332288",  # indigo
    "kkr": "#882255",  # wine
    "rcb": "#CC6677",  # rose
    "srh": "#E69F00",  # orange
    "rr": "#AA4499",  # purple
    "dc": "#88CCEE",  # cyan
    "pbks": "#117733",  # green
    "gt": "#44AA99",  # teal
    "lsg": "#0072B2",  # blue
    "deccan_chargers": "#999999",
    "gujarat_lions": "#777777",
    "rps": "#555555",
    "pune_warriors": "#BBBBBB",
    "kochi_tuskers": "#666666",
}

ACCENT = "#0072B2"
NEGATIVE = "#D55E00"
POSITIVE = "#009E73"
NEUTRAL = "#7F7F7F"
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"

LAYOUT: dict[str, object] = {
    "font": {"family": FONT, "size": 13},
    "margin": {"l": 50, "r": 20, "t": 50, "b": 45},
    "hoverlabel": {"font_size": 12},
    "legend": {"orientation": "h", "y": -0.2},
}


def team_color(franchise_id: str) -> str:
    """Colour for a franchise (neutral grey if unknown)."""
    return TEAM_COLORS.get(franchise_id, NEUTRAL)
