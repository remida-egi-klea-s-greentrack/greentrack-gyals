"""Tests for chronological, leakage-safe training data."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.training_data import build_training_rows


@pytest.fixture
def consumption():
    hours = pd.date_range(
        "2010-01-01", periods=14 * 24, freq="h"
    )
    return pd.Series(
        np.arange(len(hours), dtype=float) + 1,
        index=hours,
    )


def test_training_dates_and_targets(consumption):
    train = build_training_rows(
        consumption, "2010-01-10", "2010-01-11"
    )

    expected = pd.date_range(
        "2010-01-10", periods=48, freq="h"
    )

    assert len(train) == 48
    assert pd.DatetimeIndex(train["timestamp"]).equals(expected)
    assert train["timestamp"].is_unique

    np.testing.assert_array_equal(
        train["target_kwh"],
        consumption.reindex(expected).to_numpy(),
    )


def test_missing_target_is_excluded(consumption):
    changed = consumption.copy()
    missing_hour = pd.Timestamp("2010-01-10 08:00")
    changed.loc[missing_hour] = np.nan

    train = build_training_rows(
        changed, "2010-01-10", "2010-01-10"
    )

    assert len(train) == 23
    assert missing_hour not in set(train["timestamp"])
    assert train["target_kwh"].notna().all()


def test_missing_historical_features_are_preserved(consumption):
    changed = consumption.copy()
    changed.loc["2010-01-09 08:00"] = np.nan

    train = build_training_rows(
        changed, "2010-01-10", "2010-01-10"
    )

    assert len(train) == 24

    hour_eight = train.loc[train["hour"] == 8].iloc[0]
    assert pd.isna(hour_eight["lag_24h_kwh"])
    assert pd.notna(hour_eight["target_kwh"])
    assert train["mean_last_24h_kwh"].isna().all()


def test_target_day_changes_do_not_change_features(consumption):
    original = build_training_rows(
        consumption, "2010-01-10", "2010-01-10"
    )

    changed = consumption.copy()
    changed.loc["2010-01-10 00:00":"2010-01-10 23:00"] += 1000

    modified = build_training_rows(
        changed, "2010-01-10", "2010-01-10"
    )

    pd.testing.assert_frame_equal(
        original[FEATURE_COLUMNS],
        modified[FEATURE_COLUMNS],
    )

    assert not original["target_kwh"].equals(
        modified["target_kwh"]
    )


def test_later_days_cannot_change_training_rows(consumption):
    original = build_training_rows(
        consumption, "2010-01-10", "2010-01-10"
    )

    changed = consumption.copy()
    changed.loc["2010-01-11":] += 10000

    modified = build_training_rows(
        changed, "2010-01-10", "2010-01-10"
    )

    pd.testing.assert_frame_equal(original, modified)


def test_no_valid_training_targets_raises(consumption):
    changed = consumption.copy()
    changed.loc["2010-01-10"] = np.nan
    changed.loc["2010-01-10 01:00":"2010-01-10 23:00"] = np.nan

    with pytest.raises(ValueError, match="No valid training"):
        build_training_rows(
            changed, "2010-01-10", "2010-01-10"
        )


def test_reversed_dates_raise(consumption):
    with pytest.raises(ValueError, match="Start date"):
        build_training_rows(
            consumption, "2010-01-11", "2010-01-10"
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2010-01-10 01:00", "2010-01-11"),
        ("2010-01-10", "2010-01-11 01:00"),
        ("2010-01-10T00:00:00+00:00", "2010-01-11"),
    ],
)
def test_invalid_date_boundaries(consumption, start, end):
    with pytest.raises(ValueError, match="timezone-naive dates"):
        build_training_rows(consumption, start, end)
