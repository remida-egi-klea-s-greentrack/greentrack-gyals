"""Tests for the hourly consumption input contract."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.input_data import load_hourly_consumption


@pytest.fixture
def hourly_df():
    return pd.DataFrame({
        "timestamp": pd.date_range(
            "2010-01-01", periods=5, freq="h"
        ),
        "global_active_power_kwh": [
            1.0, 2.0, np.nan, 4.0, 5.0
        ],
        "complete": [True, True, False, True, True],
    })


def load(monkeypatch, df):
    monkeypatch.setattr(
        "ml.forecasting.input_data.pd.read_parquet",
        lambda path: df,
    )
    return load_hourly_consumption(Path("dummy.parquet"))


def test_valid_input(monkeypatch, hourly_df):
    result = load(monkeypatch, hourly_df)

    assert len(result) == 5
    assert result.isna().sum() == 1
    assert result.iloc[0] == 1.0


def test_unsorted_input_is_sorted(monkeypatch, hourly_df):
    result = load(monkeypatch, hourly_df.iloc[::-1].copy())

    assert result.index.is_monotonic_increasing
    assert result.iloc[0] == 1.0


def test_missing_column(monkeypatch, hourly_df):
    df = hourly_df.drop(columns=["complete"])

    with pytest.raises(ValueError, match="Missing input columns"):
        load(monkeypatch, df)


def test_duplicate_timestamps(monkeypatch, hourly_df):
    hourly_df.loc[1, "timestamp"] = hourly_df.loc[0, "timestamp"]

    with pytest.raises(ValueError, match="duplicate timestamps"):
        load(monkeypatch, hourly_df)


def test_missing_hour(monkeypatch, hourly_df):
    df = hourly_df.drop(index=1)

    with pytest.raises(ValueError, match="Missing hours"):
        load(monkeypatch, df)


def test_misaligned_timestamp(monkeypatch, hourly_df):
    hourly_df.loc[0, "timestamp"] += pd.Timedelta(minutes=30)

    with pytest.raises(ValueError, match="whole hours"):
        load(monkeypatch, hourly_df)


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_nonpositive_consumption(monkeypatch, hourly_df, value):
    hourly_df.loc[0, "global_active_power_kwh"] = value

    with pytest.raises(ValueError, match="positive consumption"):
        load(monkeypatch, hourly_df)


def test_complete_hour_cannot_be_missing(monkeypatch, hourly_df):
    hourly_df.loc[0, "global_active_power_kwh"] = np.nan

    with pytest.raises(ValueError, match="finite consumption"):
        load(monkeypatch, hourly_df)


def test_incomplete_hour_must_be_null(monkeypatch, hourly_df):
    hourly_df.loc[2, "global_active_power_kwh"] = 0.8

    with pytest.raises(ValueError, match="null consumption"):
        load(monkeypatch, hourly_df)


def test_complete_flag_must_be_boolean(monkeypatch, hourly_df):
    hourly_df["complete"] = hourly_df["complete"].astype(str)

    with pytest.raises(ValueError, match="must be boolean"):
        load(monkeypatch, hourly_df)
