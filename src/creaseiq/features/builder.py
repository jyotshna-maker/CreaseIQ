"""Leakage-safe feature builder with an ``as_of`` contract (FR-12).

**Contract:** a match's features are computed only from matches on *earlier dates*.
Matches are processed in date order, one date at a time. Every match on a date is
featurised from the state *before* that date, and the state is updated only after the
whole date. Same-day double-headers therefore never see each other.

**Orientation (ADR-005):** each match gets ``team_a`` and ``team_b`` from a hash-seeded coin
flip on its own natural key. The raw ``team1`` order is never used because it means
"batting first" only from 2018 onward. Features are either

* **antisymmetric**: they change sign when A and B swap (``elo_diff``, ``form10_diff``, ...), or
* **symmetric context**: they are identical from both sides (``venue_first_innings``, ...).

The declaration lets :func:`swap_orientation` produce the mirrored row, which is used to
symmetrise predictions and to test invariance.

**Allow-list:** :func:`assert_no_leakage` rejects any column not declared here. That
includes all post-match fields, which raise :class:`FeatureLeakageError`.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Literal

import numpy as np
import pandas as pd

from creaseiq.exceptions import FeatureLeakageError, InputError
from creaseiq.features.elo import EloParams, EloRatingSystem
from creaseiq.features.form import FormState
from creaseiq.features.head_to_head import HeadToHeadState
from creaseiq.features.squad import SquadState
from creaseiq.features.venue_effects import VenueState

Tier = Literal["pre_toss", "post_toss"]
TIERS: tuple[Tier, ...] = ("pre_toss", "post_toss")

# -- feature declarations ---------------------------------------------------------------------
ANTISYMMETRIC_PRE: tuple[str, ...] = (
    "elo_diff", "home_diff", "form5_diff", "form10_diff", "runs_for10_diff",
    "runs_against10_diff", "season_winpct_diff", "season_games_diff", "rest_days_diff",
    "h2h_edge", "h2h_recent_edge", "venue_team_edge",
)  # fmt: skip
SYMMETRIC_PRE: tuple[str, ...] = (
    "h2h_meetings", "venue_first_innings", "venue_bat_first_rate", "is_playoff", "impact_era",
)  # fmt: skip
ANTISYMMETRIC_POST_EXTRA: tuple[str, ...] = (
    "a_bats_first", "a_won_toss", "bats_first_x_venue", "bats_first_x_impact",
    "xi_experience_diff", "xi_potm_diff", "xi_debutants_diff", "xi_continuity_diff",
)  # fmt: skip

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "elo": ("elo_diff", "home_diff"),
    "form": ("form5_diff", "form10_diff", "runs_for10_diff", "runs_against10_diff", "season_winpct_diff", "season_games_diff", "rest_days_diff"),
    "h2h": ("h2h_edge", "h2h_recent_edge", "h2h_meetings"),
    "venue": ("venue_team_edge", "venue_first_innings", "venue_bat_first_rate"),
    "context": ("is_playoff", "impact_era"),
    "toss": ("a_bats_first", "a_won_toss", "bats_first_x_venue", "bats_first_x_impact"),
    "squad": ("xi_experience_diff", "xi_potm_diff", "xi_debutants_diff", "xi_continuity_diff"),
}  # fmt: skip

META_COLUMNS: tuple[str, ...] = (
    "match_id", "date", "season_year", "team_a", "team_b", "venue_id", "stage",
    "is_decided", "a_wins", "orientation_flip",
)  # fmt: skip

# Fields that are only known after the match. Their presence in a feature matrix is a bug.
FORBIDDEN_COLUMNS: frozenset[str] = frozenset({
    "winner", "a_wins", "result_type", "win_by_runs", "win_by_wickets", "margin_type",
    "margin_value", "team1_runs", "team2_runs", "team1_wickets", "team2_wickets",
    "first_innings_runs", "second_innings_runs", "player_of_match", "bat_first_won",
    "toss_winner_won", "super_over_winner", "dls_flag", "dls_heuristic", "season_champion",
})  # fmt: skip


def feature_columns(tier: Tier) -> list[str]:
    """Ordered allow-list of model features for a tier."""
    if tier == "pre_toss":
        return [*ANTISYMMETRIC_PRE, *SYMMETRIC_PRE]
    if tier == "post_toss":
        return [*ANTISYMMETRIC_PRE, *SYMMETRIC_PRE, *ANTISYMMETRIC_POST_EXTRA]
    raise InputError(f"Unknown tier {tier!r}; expected one of {TIERS}")


def antisymmetric_columns(tier: Tier) -> list[str]:
    """Columns that flip sign under an A/B swap."""
    return [*ANTISYMMETRIC_PRE] + ([*ANTISYMMETRIC_POST_EXTRA] if tier == "post_toss" else [])


def assert_no_leakage(columns: list[str] | pd.Index, tier: Tier) -> None:
    """Raise :class:`FeatureLeakageError` if any column is post-match or not allow-listed."""
    cols = list(columns)
    forbidden = sorted(set(cols) & FORBIDDEN_COLUMNS)
    if forbidden:
        raise FeatureLeakageError(f"Post-match columns in feature matrix: {forbidden}")
    unknown = sorted(set(cols) - set(feature_columns(tier)))
    if unknown:
        raise FeatureLeakageError(f"Columns not on the {tier} allow-list: {unknown}")


def swap_orientation(x: pd.DataFrame, tier: Tier) -> pd.DataFrame:
    """Return the same matches seen from B's side (antisymmetric columns negated)."""
    out = x.copy()
    for c in antisymmetric_columns(tier):
        if c in out.columns:
            out[c] = -out[c]
    return out


def orientation_flip(date: str, t1: str, t2: str, seed: int) -> bool:
    """Deterministic coin flip from the match's own key (independent of any other match)."""
    lo, hi = sorted((t1, t2))
    digest = hashlib.sha256(f"{seed}|{date}|{lo}|{hi}".encode()).digest()
    return bool(digest[0] & 1)


@dataclass(frozen=True)
class FeatureParams:
    """Feature-engineering hyperparameters."""

    elo: EloParams = field(default_factory=EloParams)
    venue_prior_m: float = 10.0
    form_prior_m: float = 2.0
    h2h_recent_seasons: int = 5
    seed: int = 42


@dataclass
class MatchState:
    """All incremental state, advanced one date batch at a time."""

    params: FeatureParams
    elo: EloRatingSystem
    form: FormState
    h2h: HeadToHeadState
    venue: VenueState
    squad: SquadState
    last_date: pd.Timestamp | None = None

    @classmethod
    def fresh(cls, params: FeatureParams) -> MatchState:
        """Empty state (no history)."""
        return cls(
            params,
            EloRatingSystem(params.elo),
            FormState(params.form_prior_m),
            HeadToHeadState(params.h2h_recent_seasons, params.form_prior_m),
            VenueState(params.venue_prior_m),
            SquadState(),
        )

    # -- featurisation ----------------------------------------------------------------------
    def pair_features(
        self,
        a: str,
        b: str,
        *,
        venue_id: str,
        date: pd.Timestamp,
        season_year: int,
        is_playoff: bool,
        a_home: bool,
        b_home: bool,
        toss_winner: str | None = None,
        bat_first: str | None = None,
        xi_a: frozenset[str] | None = None,
        xi_b: frozenset[str] | None = None,
    ) -> dict[str, float]:
        """Features for A vs B from the current state. Post-toss features need toss and XIs."""
        self.elo.start_season(season_year)
        g_runs = self.venue.global_first_innings
        fa = self.form.features(a, date, season_year, g_runs)
        fb = self.form.features(b, date, season_year, g_runs)
        h = self.h2h.features(a, b, season_year)
        v = self.venue.features(venue_id, a, b)
        impact = float(season_year >= 2023)
        row: dict[str, float] = {
            "elo_diff": self.elo.rating(a) - self.elo.rating(b),
            "home_diff": float(int(a_home) - int(b_home)),
            "form5_diff": fa["form5"] - fb["form5"],
            "form10_diff": fa["form10"] - fb["form10"],
            "runs_for10_diff": fa["runs_for10"] - fb["runs_for10"],
            "runs_against10_diff": fa["runs_against10"] - fb["runs_against10"],
            "season_winpct_diff": fa["season_winpct"] - fb["season_winpct"],
            "season_games_diff": fa["season_games"] - fb["season_games"],
            "rest_days_diff": fa["rest_days"] - fb["rest_days"],
            "h2h_edge": h["h2h_edge"],
            "h2h_recent_edge": h["h2h_recent_edge"],
            "venue_team_edge": v["venue_team_edge"],
            "h2h_meetings": h["h2h_meetings"],
            "venue_first_innings": v["venue_first_innings"],
            "venue_bat_first_rate": v["venue_bat_first_rate"],
            "is_playoff": float(is_playoff),
            "impact_era": impact,
        }
        if toss_winner is not None and bat_first is not None:
            bats = 1.0 if bat_first == a else -1.0
            row["a_bats_first"] = bats
            row["a_won_toss"] = 1.0 if toss_winner == a else -1.0
            row["bats_first_x_venue"] = bats * (v["venue_bat_first_rate"] - 0.5)
            row["bats_first_x_impact"] = bats * impact
            sa = self.squad.features(
                a, xi_a if xi_a is not None else self.squad.last_xi.get(a, frozenset())
            )
            sb = self.squad.features(
                b, xi_b if xi_b is not None else self.squad.last_xi.get(b, frozenset())
            )
            for key in ("xi_experience", "xi_potm", "xi_debutants", "xi_continuity"):
                row[f"{key}_diff"] = sa[key] - sb[key]
        return row

    def team_snapshot(self, team: str, date: pd.Timestamp, season_year: int) -> dict[str, float]:
        """Per-team pre-match stats (used by the first-innings score regressor)."""
        self.elo.start_season(season_year)
        f = self.form.features(team, date, season_year, self.venue.global_first_innings)
        return {"elo": self.elo.rating(team), **f}

    # -- state update -----------------------------------------------------------------------
    def update_batch(self, batch: list[Any], xis: dict[tuple[int, str], frozenset[str]]) -> None:
        """Advance the state with every match of one date (after featurising all of them)."""
        deltas: dict[str, float] = {}
        played: list[str] = []
        for r in batch:
            t1, t2, date, season = r.team1, r.team2, r.date, int(r.season_year)
            winner = r.winner if r.is_decided else None
            if r.is_decided or r.result_type == "tie":
                score1 = 0.5 if r.result_type == "tie" else float(winner == t1)
                d1, d2 = self.elo.compute_update(
                    t1, t2, score1, bool(r.team1_home), bool(r.team2_home),
                    r.margin_type if r.is_decided else None,
                    float(r.margin_value) if r.is_decided else None,
                    bool(r.dls_flag),
                )  # fmt: skip
                deltas[t1] = deltas.get(t1, 0.0) + d1
                deltas[t2] = deltas.get(t2, 0.0) + d2
                played += [t1, t2]
                self.elo.history.append(
                    {
                        "match_id": int(r.match_id),
                        "date": date,
                        "season_year": season,
                        "team": t1,
                        "rating_before": self.elo.rating(t1),
                        "delta": d1,
                    }
                )
                self.elo.history.append(
                    {
                        "match_id": int(r.match_id),
                        "date": date,
                        "season_year": season,
                        "team": t2,
                        "rating_before": self.elo.rating(t2),
                        "delta": d2,
                    }
                )
                res1: float | None = score1
            else:
                res1 = None
            usable = bool(r.scores_usable) and r.result_type != "tie"
            self.form.update(
                t1,
                date,
                season,
                res1,
                float(r.team1_runs) if usable else None,
                float(r.team2_runs) if usable else None,
            )
            self.form.update(
                t2,
                date,
                season,
                None if res1 is None else 1.0 - res1,
                float(r.team2_runs) if usable else None,
                float(r.team1_runs) if usable else None,
            )
            self.h2h.update(t1, t2, season, winner)
            first = (
                float(r.first_innings_runs)
                if bool(r.scores_usable) and not pd.isna(r.first_innings_runs)
                else None
            )
            self.venue.update(
                r.venue_id, first, bool(r.bat_first_won) if r.is_decided else None, t1, t2, winner
            )
            potm = None if pd.isna(r.player_of_match) else str(r.player_of_match)
            for team in (t1, t2):
                xi = xis.get((int(r.match_id), team))
                if xi:
                    self.squad.update(team, xi, potm)
            self.last_date = date
        self.elo.apply(deltas, played)


@dataclass
class FeatureSet:
    """Output of :meth:`FeatureBuilder.build`."""

    frame: pd.DataFrame  # META_COLUMNS + all post-toss feature columns
    team_state: pd.DataFrame  # match_id, team, elo, form..., runs_for10, runs_against10
    elo_history: pd.DataFrame
    state: MatchState  # state after the last date (for predicting future matches)

    def xy(self, tier: Tier, decided_only: bool = True) -> tuple[pd.DataFrame, pd.Series]:
        """Feature matrix (allow-listed columns only) and target ``a_wins``."""
        f = self.frame[self.frame["is_decided"]] if decided_only else self.frame
        cols = feature_columns(tier)
        x = f[cols].astype(float)
        assert_no_leakage(x.columns, tier)
        return x, f["a_wins"].astype(float)


def _xis(players: pd.DataFrame | None) -> dict[tuple[int, str], frozenset[str]]:
    if players is None or players.empty:
        return {}
    return {
        (int(mid), str(team)): frozenset(g)
        for (mid, team), g in players.groupby(["match_id", "team"])["player"]
    }


class FeatureBuilder:
    """Builds as-of features for every match and exposes the final state for inference."""

    def __init__(self, params: FeatureParams | None = None) -> None:
        self.params = params or FeatureParams()

    def build(self, matches: pd.DataFrame, players: pd.DataFrame | None = None) -> FeatureSet:
        """Featurise all matches in date order. Each date batch sees only earlier dates.

        Args:
            matches: Canonical match table (``clean.matches``).
            players: Long squad table (needed for post-toss squad features).
        """
        state = MatchState.fresh(self.params)
        xis = _xis(players)
        ordered = matches.sort_values(["date", "match_id"], kind="stable")
        # Plain records: pandas itertuples over many small groups is about 20x slower.
        records = [SimpleNamespace(**d) for d in ordered.to_dict(orient="records")]
        rows: list[dict[str, Any]] = []
        snaps: list[dict[str, Any]] = []
        for _date, group in itertools.groupby(records, key=lambda rec: rec.date):
            batch = list(group)
            for r in batch:
                flip = orientation_flip(r.date_raw, r.team1, r.team2, self.params.seed)
                a, b = (r.team2, r.team1) if flip else (r.team1, r.team2)
                a_home, b_home = (
                    (bool(r.team2_home), bool(r.team1_home))
                    if flip
                    else (bool(r.team1_home), bool(r.team2_home))
                )
                feats = state.pair_features(
                    a, b, venue_id=r.venue_id, date=r.date, season_year=int(r.season_year),
                    is_playoff=bool(r.is_playoff), a_home=a_home, b_home=b_home,
                    toss_winner=r.toss_winner, bat_first=r.bat_first,
                    xi_a=xis.get((int(r.match_id), a)), xi_b=xis.get((int(r.match_id), b)),
                )  # fmt: skip
                rows.append(
                    {
                        "match_id": int(r.match_id), "date": r.date, "season_year": int(r.season_year),
                        "team_a": a, "team_b": b, "venue_id": r.venue_id, "stage": r.stage,
                        "is_decided": bool(r.is_decided),
                        "a_wins": float(r.winner == a) if r.is_decided else np.nan,
                        "orientation_flip": flip, **feats,
                    }
                )  # fmt: skip
                for team in (r.team1, r.team2):
                    snaps.append(
                        {
                            "match_id": int(r.match_id),
                            "team": team,
                            **state.team_snapshot(team, r.date, int(r.season_year)),
                        }
                    )
            state.update_batch(batch, xis)
        frame = pd.DataFrame(rows)
        return FeatureSet(frame, pd.DataFrame(snaps), state.elo.history_frame(), state)

    def state_as_of(
        self, matches: pd.DataFrame, players: pd.DataFrame | None, as_of: pd.Timestamp
    ) -> MatchState:
        """State built from matches strictly before ``as_of`` (the ``as_of`` contract)."""
        history = matches[matches["date"] < pd.Timestamp(as_of)]
        return self.build(history, players).state if len(history) else MatchState.fresh(self.params)
