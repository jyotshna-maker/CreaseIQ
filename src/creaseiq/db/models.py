"""Relational schema (FR-04, PLAN §8). The ER diagram in the docs is drawn from these models.

The schema is in 3NF. Every non-key attribute depends on the whole key and only on it:
franchise names live only in ``franchise``, venue attributes only in ``venue``, player and
official names only in their own tables, and ``match`` holds just foreign keys plus facts
that belong to the match itself.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all tables."""


class Franchise(Base):
    """A franchise (renames share one row, ADR-003)."""

    __tablename__ = "franchise"
    franchise_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(80), unique=True)
    short_code: Mapped[str] = mapped_column(String(8))
    active: Mapped[bool] = mapped_column(Boolean)
    lineage_note: Mapped[str | None] = mapped_column(Text)


class TeamAlias(Base):
    """A raw team string and the seasons in which it denotes a franchise."""

    __tablename__ = "team_alias"
    alias: Mapped[str] = mapped_column(String(80), primary_key=True)
    franchise_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    valid_from_year: Mapped[int] = mapped_column(Integer)
    valid_to_year: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("valid_from_year <= valid_to_year", name="ck_alias_window"),)


class Venue(Base):
    """A canonical venue."""

    __tablename__ = "venue"
    venue_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(60))
    country: Mapped[str] = mapped_column(String(40))


class Season(Base):
    """One IPL season."""

    __tablename__ = "season"
    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_year: Mapped[int] = mapped_column(Integer, unique=True)
    raw_label: Mapped[str] = mapped_column(String(10))
    host_note: Mapped[str | None] = mapped_column(Text)
    n_matches: Mapped[int] = mapped_column(Integer)
    champion_id: Mapped[str | None] = mapped_column(ForeignKey("franchise.franchise_id"))


class Player(Base):
    """A player, identified by the exact Cricsheet name string."""

    __tablename__ = "player"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Official(Base):
    """A match official (umpire or referee)."""

    __tablename__ = "official"
    official_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Match(Base):
    """One match. The natural key is (date, team1_id, team2_id)."""

    __tablename__ = "match"
    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.season_id"))
    date: Mapped[date] = mapped_column(Date)
    match_number: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(16))
    venue_id: Mapped[str] = mapped_column(ForeignKey("venue.venue_id"))
    team1_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    team2_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    toss_winner_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    toss_decision: Mapped[str] = mapped_column(String(5))
    bat_first_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    team1_runs: Mapped[int] = mapped_column(Integer)
    team1_wkts: Mapped[int] = mapped_column(Integer)
    team2_runs: Mapped[int] = mapped_column(Integer)
    team2_wkts: Mapped[int] = mapped_column(Integer)
    first_innings_runs: Mapped[float | None] = mapped_column(Float)
    second_innings_runs: Mapped[float | None] = mapped_column(Float)
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("franchise.franchise_id"))
    super_over_winner_id: Mapped[str | None] = mapped_column(ForeignKey("franchise.franchise_id"))
    result_type: Mapped[str] = mapped_column(String(10))
    margin_type: Mapped[str | None] = mapped_column(String(8))
    margin_value: Mapped[float | None] = mapped_column(Float)
    dls_flag: Mapped[bool] = mapped_column(Boolean)
    voided: Mapped[bool] = mapped_column(Boolean)
    team1_home: Mapped[bool] = mapped_column(Boolean)
    team2_home: Mapped[bool] = mapped_column(Boolean)
    potm_player_id: Mapped[int | None] = mapped_column(ForeignKey("player.player_id"))
    referee_id: Mapped[int | None] = mapped_column(ForeignKey("official.official_id"))
    umpire1_id: Mapped[int | None] = mapped_column(ForeignKey("official.official_id"))
    umpire2_id: Mapped[int | None] = mapped_column(ForeignKey("official.official_id"))
    tv_umpire_id: Mapped[int | None] = mapped_column(ForeignKey("official.official_id"))
    reserve_umpire_id: Mapped[int | None] = mapped_column(ForeignKey("official.official_id"))
    __table_args__ = (
        UniqueConstraint("date", "team1_id", "team2_id", name="uq_match_natural_key"),
        CheckConstraint("toss_decision IN ('bat', 'field')", name="ck_toss_decision"),
        CheckConstraint("result_type IN ('complete', 'tie', 'no result')", name="ck_result_type"),
        CheckConstraint("team1_id <> team2_id", name="ck_distinct_teams"),
        CheckConstraint(
            "(result_type = 'complete') = (winner_id IS NOT NULL)", name="ck_winner_iff_complete"
        ),
        Index("ix_match_season", "season_id"),
        Index("ix_match_venue", "venue_id"),
        Index("ix_match_date", "date"),
    )


class MatchPlayer(Base):
    """Association: a player listed for a team in a match."""

    __tablename__ = "match_player"
    match_id: Mapped[int] = mapped_column(ForeignKey("match.match_id"), primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.player_id"), primary_key=True)
    slot_no: Mapped[int] = mapped_column(Integer)
    __table_args__ = (Index("ix_match_player_player", "player_id"),)


class ModelRun(Base):
    """A registered model training run (FR-18)."""

    __tablename__ = "model_run"
    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    model_name: Mapped[str] = mapped_column(String(60))
    tier: Mapped[str] = mapped_column(String(10))
    params_json: Mapped[str] = mapped_column(Text)
    data_sha256: Mapped[str] = mapped_column(String(64))
    git_commit: Mapped[str] = mapped_column(String(40))
    metrics_json: Mapped[str] = mapped_column(Text)
    artifact_path: Mapped[str] = mapped_column(Text)
    artifact_sha256: Mapped[str] = mapped_column(String(64))


class PredictionLog(Base):
    """Every prediction served (FR-21, NFR-07)."""

    __tablename__ = "prediction_log"
    prediction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    run_id: Mapped[str | None] = mapped_column(String(40))
    tier: Mapped[str] = mapped_column(String(10))
    team_a_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    team_b_id: Mapped[str] = mapped_column(ForeignKey("franchise.franchise_id"))
    venue_id: Mapped[str] = mapped_column(ForeignKey("venue.venue_id"))
    stage: Mapped[str] = mapped_column(String(16))
    toss_json: Mapped[str | None] = mapped_column(Text)
    p_a: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    __table_args__ = (CheckConstraint("p_a >= 0 AND p_a <= 1", name="ck_probability"),)


# Views are static DDL (no user input). They are created by the loader after the tables.
VIEWS: dict[str, str] = {
    "v_team_season_summary": """
        CREATE VIEW v_team_season_summary AS
        SELECT s.season_year, f.franchise_id, f.canonical_name,
               COUNT(*) AS matches,
               SUM(CASE WHEN m.winner_id = f.franchise_id THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN m.result_type = 'complete' AND m.winner_id <> f.franchise_id
                        THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN m.result_type <> 'complete' THEN 1 ELSE 0 END) AS no_decision
        FROM match m
        JOIN season s ON s.season_id = m.season_id
        JOIN franchise f ON f.franchise_id IN (m.team1_id, m.team2_id)
        GROUP BY s.season_year, f.franchise_id, f.canonical_name
    """,
    "v_head_to_head": """
        CREATE VIEW v_head_to_head AS
        SELECT a.franchise_id AS team_id, b.franchise_id AS opponent_id,
               COUNT(*) AS meetings,
               SUM(CASE WHEN m.winner_id = a.franchise_id THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN m.winner_id = b.franchise_id THEN 1 ELSE 0 END) AS losses
        FROM match m
        JOIN franchise a ON a.franchise_id IN (m.team1_id, m.team2_id)
        JOIN franchise b ON b.franchise_id IN (m.team1_id, m.team2_id)
                        AND b.franchise_id <> a.franchise_id
        GROUP BY a.franchise_id, b.franchise_id
    """,
}
