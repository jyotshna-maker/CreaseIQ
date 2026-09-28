"""Services: validation, prediction logging, safe export, upload flow, scenarios (FR-05, FR-11,
FR-16, FR-19, FR-20; NFR-02, NFR-03)."""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from creaseiq.config import Settings, load_settings
from creaseiq.exceptions import DataValidationError, InputError
from creaseiq.services.analytics_service import AnalyticsService, sanitize_cell, to_safe_csv
from creaseiq.services.context import AppContext
from creaseiq.services.ingest_service import process_upload, read_upload
from creaseiq.services.prediction_service import PredictionRequest, PredictionService
from creaseiq.services.scenario_service import ScenarioService, primary_home
from creaseiq.simulation.season_monte_carlo import simulate_season
from creaseiq.simulation.what_if import run_what_if, toss_scenarios
from tests.conftest import ROOT


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> AppContext:
    """Real data and models, but a throw-away database for prediction logs."""
    base = load_settings(ROOT)
    db = tmp_path_factory.mktemp("db") / "t.db"
    data = {**base.data, "database": {"url": f"sqlite:///{db.as_posix()}"}}
    return AppContext(Settings(base.root, data))


@pytest.mark.parametrize(
    ("req", "message"),
    [
        (PredictionRequest("mi", "nope", "wankhede"), "Unknown team"),
        (PredictionRequest("mi' OR 1=1 --", "csk", "wankhede"), "Unknown team"),
        (PredictionRequest("mi", "mi", "wankhede"), "cannot play itself"),
        (PredictionRequest("mi", "csk", "lords"), "Unknown venue"),
        (PredictionRequest("mi", "csk", "wankhede", stage="semi"), "Stage"),
        (
            PredictionRequest("mi", "csk", "wankhede", toss_winner="rcb", toss_decision="bat"),
            "toss winner",
        ),
        (PredictionRequest("mi", "csk", "wankhede", toss_winner="mi", toss_decision="bowl"), "bat"),
        (PredictionRequest("mi", "csk", "wankhede", date="not-a-date"), "YYYY-MM-DD"),
        (PredictionRequest("mi", "csk", "wankhede", date="1999-01-01"), "between"),
    ],
)
def test_invalid_requests_rejected(ctx: AppContext, req: PredictionRequest, message: str) -> None:
    with pytest.raises(InputError, match=message):
        PredictionService(ctx).validate(req)


def test_prediction_is_logged_and_symmetric(ctx: AppContext) -> None:
    svc = PredictionService(ctx)
    a = svc.predict(PredictionRequest("mi", "csk", "wankhede"))
    b = svc.predict(PredictionRequest("csk", "mi", "wankhede"))
    assert a["p_a"] == pytest.approx(b["p_b"], abs=1e-9)
    assert a["tier"] == "pre_toss" and a["latency_ms"] >= 0
    post = svc.predict(
        PredictionRequest("mi", "csk", "wankhede", toss_winner="mi", toss_decision="bat")
    )
    assert post["tier"] == "post_toss" and post["drivers"]
    log = ctx.repo.prediction_log()
    assert len(log) >= 3 and set(log["tier"]) == {"pre_toss", "post_toss"}


def test_context_helpers(ctx: AppContext) -> None:
    assert len(ctx.active_franchises()) == 10
    assert ctx.team_label("rcb") == "Royal Challengers Bengaluru"
    assert "Mumbai" in ctx.venue_label("wankhede")
    assert ctx.report("metrics") is not None and ctx.report("nope") is None


@pytest.mark.parametrize("payload", ['=HYPERLINK("http://x")', "+1+1", "-2", "@SUM(A1)", "\tx"])
def test_csv_injection_neutralised(payload: str) -> None:
    assert sanitize_cell(payload) == "'" + payload
    out = to_safe_csv(pd.DataFrame({"a": [payload, "safe"], "=b": [1, 2]})).decode()
    parsed = pd.read_csv(io.StringIO(out))
    assert parsed["a"].iloc[0].startswith("'") and parsed["a"].iloc[1] == "safe"
    assert parsed.columns[1] == "'=b"
    assert sanitize_cell(5) == 5


def test_analytics_service(ctx: AppContext) -> None:
    svc = AnalyticsService(ctx)
    k = svc.kpis()
    assert k["matches"] == 1243 and k["latest_champion"] == "Royal Challengers Bengaluru"
    m = svc.filtered(2025, 2026, "rcb")
    table = svc.explorer_table(m)
    assert len(table) == len(m) and "Royal Challengers Bengaluru" in set(table["team1"]) | set(
        table["team2"]
    )
    assert not svc.team_table(m).empty and not svc.scoring(m).empty and not svc.potm(m).empty
    assert svc.venue_clusters(svc.filtered()).k >= 2
    assert set(svc.toss(svc.filtered())) == {"toss", "chase", "field_share"}
    assert not svc.season_form(m).empty and svc.h2h_matrix(svc.filtered(), 5).shape[0] > 5
    assert not svc.venue_profiles(m).empty
    assert isinstance(svc.elo_history(), pd.DataFrame)


def test_upload_guards() -> None:
    with pytest.raises(InputError, match=r"\.csv"):
        read_upload(b"a,b", "matches.xlsx", 100)
    with pytest.raises(InputError, match="limit"):
        read_upload(b"a" * 101, "m.csv", 100)
    with pytest.raises(InputError, match="UTF-8"):
        read_upload(b"\xff\xfe\x00bad", "m.csv", 100)
    with pytest.raises(InputError, match="parse"):
        read_upload(b"", "m.csv", 100)


def _new_row(raw: pd.DataFrame, date: str = "01-04-2027", season: str = "2027") -> pd.DataFrame:
    row = raw[raw["season"] == "2026"].iloc[[0]].copy()
    row["date"], row["season"], row["match_number"] = date, season, "1"
    return row


def _csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def test_upload_flow(full_project: Settings, raw_df: pd.DataFrame) -> None:
    s = full_project
    # Duplicates only: nothing new.
    dup = process_upload(s, _csv(raw_df.head(3)), "dup.csv", dry_run=True)
    assert dup.rows_new == 0 and dup.rows_duplicate == 3
    # Invalid rows reject the whole upload.
    bad = _new_row(raw_df)
    bad["toss_decision"] = "bowl"
    with pytest.raises(DataValidationError):
        process_upload(s, _csv(bad), "bad.csv", dry_run=True)
    # Unknown team fails canonicalisation.
    unknown = _new_row(raw_df)
    unknown["team1"] = unknown["toss_winner"] = unknown["winner"] = "Hyderabad Heroes"
    unknown.loc[:, "winner"] = "Hyderabad Heroes"
    with pytest.raises(DataValidationError, match="Unmapped team"):
        process_upload(s, _csv(unknown), "u.csv", dry_run=True)
    # A valid new match: dry run writes nothing, apply appends and rebuilds.
    good = _new_row(raw_df)
    rep = process_upload(s, _csv(good), "new.csv", dry_run=True)
    assert rep.rows_new == 1 and not rep.applied and not s.path("appended_csv").exists()
    rep = process_upload(s, _csv(good), "new.csv", dry_run=False)
    assert rep.applied and s.path("appended_csv").is_file()
    assert len(pd.read_parquet(s.path("processed_dir") / "matches.parquet")) == 1244
    # Re-uploading the same row is now a duplicate.
    again = process_upload(s, _csv(good), "new.csv", dry_run=False)
    assert again.rows_new == 0
    s.path("appended_csv").unlink()


def test_what_if_and_simulation(ctx: AppContext) -> None:
    table = ScenarioService(ctx).what_if(PredictionRequest("rcb", "gt", "narendra_modi"))
    assert table.iloc[0]["scenario"] == "baseline" and table.iloc[0]["delta"] == 0.0
    assert len(table) >= 6 and table["p_a"].between(0, 1).all()
    assert primary_home(ctx.maps, "rcb", 2026) == "chinnaswamy"
    assert primary_home(ctx.maps, "kochi_tuskers", 2026) is None
    odds = ScenarioService(ctx).season_odds(n_sims=500)
    assert len(odds) == 10 and odds["p_title"].sum() == pytest.approx(1.0)
    assert (odds["p_top4"] >= odds["p_final"]).all() and (odds["p_final"] >= odds["p_title"]).all()


def test_monte_carlo_logic() -> None:
    p = np.full((4, 4), 0.5)
    p[0, :], p[:, 0] = 1.0, 0.0
    p[0, 0] = 0.5
    out = simulate_season(["a", "b", "c", "d"], p, 1000, 1).set_index("team")
    assert out.loc["a", "p_title"] == 1.0 and out.loc["a", "mean_wins"] == 6.0
    assert out["p_top4"].sum() == pytest.approx(4.0)


def test_what_if_runner() -> None:
    from creaseiq.models.predict import Fixture

    base = Fixture("a", "b", "v", pd.Timestamp("2027-01-01"))
    table = run_what_if(
        base, toss_scenarios(base), lambda fx: 0.6 if fx.toss_winner == "a" else 0.5
    )
    assert table.iloc[0]["p_a"] == 0.5 and table.iloc[1]["delta"] == pytest.approx(0.1)
