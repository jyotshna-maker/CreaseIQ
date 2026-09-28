"""Recent-form state per team (FR-12): smoothed win rates, rolling runs, season record, rest."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import pandas as pd

from creaseiq.analytics.hypothesis_tests import shrunk_rate

REST_CAP_DAYS = 30.0


@dataclass
class TeamForm:
    """Rolling history for one franchise."""

    results: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    runs_for: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    runs_against: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    season: int | None = None
    season_wins: int = 0
    season_games: int = 0
    last_date: pd.Timestamp | None = None


@dataclass
class FormState:
    """Form state for all teams; ``prior_m`` is the smoothing strength toward 0.5."""

    prior_m: float = 2.0
    teams: dict[str, TeamForm] = field(default_factory=lambda: defaultdict(TeamForm))

    def features(
        self, team: str, date: pd.Timestamp, season_year: int, global_runs: float
    ) -> dict[str, float]:
        """Pre-match form features for ``team`` as of ``date`` (all strictly earlier matches)."""
        t = self.teams[team]
        last5 = list(t.results)[-5:]
        last10 = list(t.results)
        same_season = t.season == season_year
        wins_s = t.season_wins if same_season else 0
        games_s = t.season_games if same_season else 0
        rest = (
            REST_CAP_DAYS
            if t.last_date is None
            else min(REST_CAP_DAYS, float((date - t.last_date).days))
        )
        return {
            "form5": shrunk_rate(sum(last5), len(last5), 0.5, self.prior_m),
            "form10": shrunk_rate(sum(last10), len(last10), 0.5, self.prior_m),
            "runs_for10": sum(t.runs_for) / len(t.runs_for) if t.runs_for else global_runs,
            "runs_against10": sum(t.runs_against) / len(t.runs_against)
            if t.runs_against
            else global_runs,
            "season_winpct": shrunk_rate(wins_s, games_s, 0.5, self.prior_m),
            "season_games": float(games_s),
            "rest_days": rest,
        }

    def update(
        self,
        team: str,
        date: pd.Timestamp,
        season_year: int,
        result: float | None,
        runs_for: float | None,
        runs_against: float | None,
    ) -> None:
        """Record one match for ``team``. ``result`` is 1/0/0.5, or None if undecided."""
        t = self.teams[team]
        if t.season != season_year:
            t.season, t.season_wins, t.season_games = season_year, 0, 0
        if result is not None:
            t.results.append(result)
            t.season_games += 1
            t.season_wins += int(result == 1.0)
        if runs_for is not None and runs_against is not None:
            t.runs_for.append(runs_for)
            t.runs_against.append(runs_against)
        t.last_date = date
