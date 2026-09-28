"""Database: idempotent rebuild, constraints, parameterised queries (FR-04, NFR-03)."""

from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import Engine, insert, text
from sqlalchemy.exc import IntegrityError

from creaseiq.data.pipeline import DataPipelineResult
from creaseiq.db.loader import load_database, table_counts
from creaseiq.db.models import Base, Match, Venue
from creaseiq.db.repository import MatchRepository
from creaseiq.db.session import make_engine, session_scope


@pytest.fixture(scope="module")
def engine(pipeline: DataPipelineResult) -> Engine:
    eng = make_engine("sqlite:///:memory:")
    load_database(eng, pipeline.clean.matches, pipeline.clean.players, pipeline.maps)
    return eng


def _checksum(engine: Engine) -> str:
    digest = hashlib.sha256()
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            df = pd.read_sql(table.select(), conn)
            df = df.sort_values(list(df.columns)).reset_index(drop=True)
            digest.update(table.name.encode())
            digest.update(pd.util.hash_pandas_object(df.astype(str), index=False).values.tobytes())
    return digest.hexdigest()


def test_counts(engine: Engine) -> None:
    counts = table_counts(engine)
    assert counts["match"] == 1243
    assert counts["franchise"] == 15
    assert counts["venue"] == 37
    assert counts["season"] == 19
    assert counts["player"] == 811
    assert counts["match_player"] == 27909


def test_rebuild_is_idempotent(pipeline: DataPipelineResult, tmp_path) -> None:
    eng = make_engine(f"sqlite:///{(tmp_path / 'x.db').as_posix()}")
    load_database(eng, pipeline.clean.matches, pipeline.clean.players, pipeline.maps)
    first = _checksum(eng)
    load_database(eng, pipeline.clean.matches, pipeline.clean.players, pipeline.maps)
    assert _checksum(eng) == first


def test_operational_tables_survive_rebuild(pipeline: DataPipelineResult) -> None:
    eng = make_engine("sqlite:///:memory:")
    load_database(eng, pipeline.clean.matches, pipeline.clean.players, pipeline.maps)
    repo = MatchRepository(eng)
    repo.log_prediction(
        run_id="r1",
        tier="pre_toss",
        team_a="mi",
        team_b="csk",
        venue_id="wankhede",
        stage="league",
        toss=None,
        p_a=0.55,
        latency_ms=3.2,
    )
    load_database(eng, pipeline.clean.matches, pipeline.clean.players, pipeline.maps)
    assert len(repo.prediction_log()) == 1


def test_foreign_keys_enforced(engine: Engine) -> None:
    with pytest.raises(IntegrityError), session_scope(engine) as s:
        s.execute(
            insert(Venue).values(venue_id="x", canonical_name="Eden Gardens", city="c", country="c")
        )
    row = {
        "match_id": 99999, "season_id": 2008, "date": date(2030, 1, 1), "stage": "league",
        "venue_id": "no_such_venue", "team1_id": "mi", "team2_id": "csk", "toss_winner_id": "mi",
        "toss_decision": "bat", "bat_first_id": "mi", "team1_runs": 1, "team1_wkts": 0,
        "team2_runs": 0, "team2_wkts": 0, "winner_id": "mi", "result_type": "complete",
        "dls_flag": False, "voided": False, "team1_home": False, "team2_home": False,
    }  # fmt: skip
    with pytest.raises(IntegrityError), session_scope(engine) as s:
        s.execute(insert(Match).values(**row))
    row["venue_id"] = "wankhede"
    row["toss_decision"] = "bowl"
    with pytest.raises(IntegrityError), session_scope(engine) as s:
        s.execute(insert(Match).values(**row))
    row["toss_decision"] = "bat"
    row["winner_id"] = None
    with pytest.raises(IntegrityError), session_scope(engine) as s:
        s.execute(insert(Match).values(**row))


def test_repository_queries(engine: Engine) -> None:
    repo = MatchRepository(engine)
    assert repo.match_count() == 1243
    assert len(repo.franchises()) == 15 and len(repo.venues()) == 37
    seasons = repo.seasons()
    assert seasons.set_index("season_year").loc[2026, "champion_id"] == "rcb"
    rcb_2025 = repo.matches(2025, 2025, "rcb")
    assert len(rcb_2025) == 15
    squads = repo.match_players(int(rcb_2025.iloc[0]["match_id"]))
    assert squads["team_id"].nunique() == 2
    h2h = repo.head_to_head("mi")
    assert (h2h["team_id"] == "mi").all()
    summary = repo.team_season_summary()
    assert summary.groupby("season_year")["matches"].sum().loc[2026] == 74 * 2
    assert len(repo.head_to_head()) > len(h2h)


@pytest.mark.parametrize(
    "payload", ["mi' OR '1'='1", "mi; DROP TABLE match; --", "' UNION SELECT * FROM player --"]
)
def test_injection_strings_are_inert(engine: Engine, payload: str) -> None:
    repo = MatchRepository(engine)
    assert repo.matches(team_id=payload).empty
    assert repo.head_to_head(payload).empty
    assert repo.match_count() == 1243  # nothing was dropped


def test_model_run_upsert(engine: Engine) -> None:
    repo = MatchRepository(engine)
    rec = {
        "run_id": "abc",
        "created_at": pd.Timestamp("2026-09-29").to_pydatetime(),
        "model_name": "logreg",
        "tier": "pre_toss",
        "params_json": "{}",
        "data_sha256": "0" * 64,
        "git_commit": "x",
        "metrics_json": "{}",
        "artifact_path": "m.joblib",
        "artifact_sha256": "1" * 64,
    }
    repo.record_model_run(rec)
    repo.record_model_run({**rec, "model_name": "hgb"})
    runs = repo.model_runs()
    assert len(runs) == 1 and runs.iloc[0]["model_name"] == "hgb"


def test_views_exist(engine: Engine) -> None:
    with engine.connect() as conn:
        names = {
            r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='view'"))
        }
    assert {"v_team_season_summary", "v_head_to_head"} <= names
