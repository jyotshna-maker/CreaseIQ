"""Source loading and validation: strict vs lenient, quarantine reasons (FR-01, NFR-03)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from creaseiq.data.ingest import validate_raw, write_quarantine
from creaseiq.data.source import CsvMatchSource, MatchSource
from creaseiq.exceptions import DataValidationError, InputError


def test_real_csv_passes_lenient_with_zero_quarantined(raw_df: pd.DataFrame) -> None:
    # Documented expectation (data_quality_report.md): the real file has 0 invalid rows once
    # tie rows are allowed to carry super-over wickets.
    result = validate_raw(raw_df, "lenient")
    assert result.n_quarantined == 0
    assert len(result.valid) == 1243


def test_real_csv_passes_strict(raw_df: pd.DataFrame) -> None:
    assert len(validate_raw(raw_df, "strict").valid) == 1243


def _corrupt(df: pd.DataFrame) -> pd.DataFrame:
    bad = df.copy()
    bad.loc[1, "toss_decision"] = "bowl"  # schema: not allowed
    bad.loc[2, "toss_winner"] = "Somebody Else"  # rule: toss winner not a participant
    bad.loc[3, "team1_wickets"] = "11"  # rule: >10 on a non-tie
    bad.loc[4, "date"] = "31-02-2020"  # rule: impossible date
    bad.loc[5, "team2"] = bad.loc[5, "team1"]  # rule: same team twice
    bad.loc[6, "winner"] = None  # rule: complete result without winner
    bad.loc[7, "team1_players"] = "A B, C D"  # rule: squad too small
    bad.loc[8, "overs_limit"] = "50"  # schema: constant column
    return bad


def test_lenient_quarantines_with_reasons(sample_raw: pd.DataFrame, tmp_path: Path) -> None:
    result = validate_raw(_corrupt(sample_raw), "lenient")
    assert set(result.reasons) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert "schema:toss_decision" in result.reasons[1][0]
    assert result.reasons[2] == ["rule:toss_winner_in_match"]
    assert "rule:wickets_le_10_unless_tie" in result.reasons[3]
    assert "rule:valid_date" in result.reasons[4]
    assert "rule:distinct_teams" in result.reasons[5]
    assert "rule:winner_iff_complete" in result.reasons[6]
    assert "rule:squad_size" in result.reasons[7]
    assert len(result.valid) == len(sample_raw) - 8
    out = tmp_path / "q.csv"
    write_quarantine(result, out)
    assert "reason" in pd.read_csv(out).columns


def test_strict_raises_with_row_indices(sample_raw: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError) as info:
        validate_raw(_corrupt(sample_raw), "strict")
    assert info.value.row_indices == [1, 2, 3, 4, 5, 6, 7, 8]


def test_column_mismatch_always_raises(sample_raw: pd.DataFrame) -> None:
    with pytest.raises(DataValidationError, match="Missing"):
        validate_raw(sample_raw.drop(columns=["venue"]), "lenient")
    with pytest.raises(DataValidationError, match="unexpected"):
        validate_raw(sample_raw.assign(extra=1), "lenient")


def test_tie_rows_may_exceed_ten_wickets(sample_raw: pd.DataFrame) -> None:
    df = sample_raw.copy()
    tie = df.index[df["result_type"] == "tie"][0]
    df.loc[tie, "team2_wickets"] = "12"
    assert validate_raw(df, "strict").n_quarantined == 0


def test_csv_source_guards(tmp_path: Path, settings) -> None:
    src = CsvMatchSource(settings.path("raw_csv"), expected_sha256=settings.get("paths.raw_sha256"))
    assert isinstance(src, MatchSource)
    assert len(src.load()) == 1243
    with pytest.raises(DataValidationError, match="hash mismatch"):
        CsvMatchSource(settings.path("raw_csv"), expected_sha256="0" * 64).load()
    with pytest.raises(InputError, match="not found"):
        CsvMatchSource(tmp_path / "nope.csv").load()
    txt = tmp_path / "data.txt"
    txt.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(InputError, match=r"\.csv"):
        CsvMatchSource(txt).load()
    big = tmp_path / "big.csv"
    big.write_text("a\n" + "1\n" * 100, encoding="utf-8")
    with pytest.raises(InputError, match="limit"):
        CsvMatchSource(big, max_bytes=10).load()
    broken = tmp_path / "broken.csv"
    broken.write_bytes(b'a,b\n"unterminated,1\n')
    with pytest.raises(DataValidationError, match="parse"):
        CsvMatchSource(broken).load()
