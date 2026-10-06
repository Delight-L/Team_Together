"""Freeze the verified 2025H2 results and monthly processing safeguards."""
from pathlib import Path

import pandas as pd
import pytest

from analysis.sequential import run_month, run_sequential, split_baseline_and_stream
from run_analysis2_sequential import validate_current_month

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def inputs():
    features = pd.read_csv(ROOT / "data/reference/gangnam_analysis2_feature_table_2022_2025.csv")
    features["date"] = pd.to_datetime(features["date"])
    context = pd.read_csv(ROOT / "data/reference/gangnam_analysis1_final_region_typology_2025H2.csv")
    return features, context


@pytest.fixture(scope="module")
def sequential_result(inputs):
    features, context = inputs
    return run_sequential(features, context)


def test_monthly_signal_counts_and_keys(sequential_result):
    result = sequential_result
    expected_months = pd.date_range("2025-07-01", "2025-12-01", freq="MS")
    counts = result.groupby("date")["any_signal"].sum()
    assert counts.index.tolist() == expected_months.tolist()
    assert counts.tolist() == [0, 0, 0, 0, 0, 1]
    assert len(result) == 132
    assert result.groupby("date")["행정동코드"].nunique().tolist() == [22] * 6
    assert not result.duplicated(["date", "행정동코드"]).any()


def test_december_samsung1_new_mobility_signal(sequential_result):
    signals = sequential_result.loc[sequential_result["any_signal"]]
    assert len(signals) == 1
    signal = signals.iloc[0]
    assert signal["date"] == pd.Timestamp("2025-12-01")
    assert signal["행정동"] == "삼성1동"
    assert bool(signal["mobility_signal"])
    assert not bool(signal["communication_signal"])
    assert not bool(signal["combined_signal"])
    assert signal["signal_status"] == "New"


def test_mixed_date_history_matches_december(inputs, sequential_result):
    features, context = inputs
    period = pd.Timestamp("2025-12-01")
    history = features.loc[features["date"] < period].copy()
    history["date"] = history["date"].dt.strftime("%Y-%m-%d")
    history.loc[history.index[::2], "date"] += " 00:00:00"
    current = features.loc[features["date"] == period].copy()
    actual = run_month(history, current, context)
    expected = sequential_result.loc[sequential_result["date"] == period]
    def ordered(frame):
        return frame.sort_values("행정동코드").reset_index(drop=True)
    pd.testing.assert_frame_equal(ordered(actual), ordered(expected))


def test_history_rejects_current_month_leakage(inputs):
    features, context = inputs
    history, stream = split_baseline_and_stream(features)
    current = stream.loc[stream["date"] == pd.Timestamp("2025-07-01")]
    contaminated = pd.concat([history, current], ignore_index=True)
    with pytest.raises(ValueError, match="only months before"):
        run_month(contaminated, current, context)


def test_monthly_runner_rejects_reprocessing_and_skipped_month(inputs):
    features, _ = inputs
    history, stream = split_baseline_and_stream(features)
    july = stream.loc[stream["date"] == pd.Timestamp("2025-07-01")]
    august = stream.loc[stream["date"] == pd.Timestamp("2025-08-01")]
    validate_current_month(history, july, pd.Timestamp("2025-07-01"))
    with pytest.raises(ValueError, match="already exists"):
        validate_current_month(pd.concat([history, july]), july, pd.Timestamp("2025-07-01"))
    with pytest.raises(ValueError, match="Sequential processing violation"):
        validate_current_month(history, august, pd.Timestamp("2025-08-01"))
