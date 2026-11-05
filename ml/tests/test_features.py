"""Tests for leakage-safe XGBoost forecasting features."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.features import (
    FEATURE_COLUMNS,
    build_forecast_features,
)


@pytest.fixture
def consumption():
    hours = pd.date_range(
        "2010-01-01", periods=14 * 24, freq="h"
    )
    return pd.Series(
        np.arange(len(hours), dtype=float) + 1,
        index=hours,
    )


def test_calendar_and_historical_features(consumption):
    features = build_forecast_features(consumption, "2010-01-12")

    assert len(features) == 24
    assert set(FEATURE_COLUMNS).issubset(features.columns)
    assert features["hour"].tolist() == list(range(24))
    assert features["month"].eq(1).all()

    targets = pd.DatetimeIndex(features["timestamp"])

    np.testing.assert_array_equal(
        features["lag_24h_kwh"],
        consumption.reindex(
            targets - pd.Timedelta(hours=24)
        ).to_numpy(),
    )
    np.testing.assert_array_equal(
        features["lag_168h_kwh"],
        consumption.reindex(
            targets - pd.Timedelta(hours=168)
        ).to_numpy(),
    )

    expected_mean = consumption.loc[
        "2010-01-11 00:00":"2010-01-11 23:00"
    ].mean()

    assert features["mean_last_24h_kwh"].eq(expected_mean).all()


def test_future_data_does_not_change_features(consumption):
    original = build_forecast_features(
        consumption, "2010-01-12"
    )

    changed = consumption.copy()
    changed.loc["2010-01-12":] += 10000

    modified = build_forecast_features(
        changed, "2010-01-12"
    )

    pd.testing.assert_frame_equal(original, modified)


def test_missing_weekly_reference_uses_timestamp_lookup(consumption):
    changed = consumption.drop(
        pd.Timestamp("2010-01-05 08:00")
    )

    features = build_forecast_features(changed, "2010-01-12")

    assert pd.isna(features.loc[8, "lag_168h_kwh"])
    assert features["lag_168h_kwh"].isna().sum() == 1
    assert pd.notna(features.loc[8, "lag_24h_kwh"])


def test_missing_recent_hour_makes_mean_nan(consumption):
    changed = consumption.copy()
    changed.loc["2010-01-11 10:00"] = np.nan

    features = build_forecast_features(changed, "2010-01-12")

    assert features["mean_last_24h_kwh"].isna().all()
    assert pd.isna(features.loc[10, "lag_24h_kwh"])


def test_unsorted_history_produces_same_features(consumption):
    expected = build_forecast_features(
        consumption, "2010-01-12"
    )
    actual = build_forecast_features(
        consumption.iloc[::-1], "2010-01-12"
    )

    pd.testing.assert_frame_equal(expected, actual)


@pytest.mark.parametrize(
    "problem",
    ["duplicate", "nonhour", "timezone", "notdatetime"],
)
def test_invalid_consumption_index(consumption, problem):
    changed = consumption.copy()

    if problem == "duplicate":
        changed = pd.concat([changed, changed.iloc[[0]]])
    elif problem == "nonhour":
        timestamps = list(changed.index)
        timestamps[0] += pd.Timedelta(minutes=30)
        changed.index = pd.DatetimeIndex(timestamps)
    elif problem == "timezone":
        changed = changed.tz_localize("UTC")
    else:
        changed.index = changed.index.strftime("%Y-%m-%d %H:%M")

    with pytest.raises((TypeError, ValueError)):
        build_forecast_features(changed, "2010-01-12")


@pytest.mark.parametrize(
    "day",
    [
        "2010-01-12 01:00",
        pd.Timestamp("2010-01-12", tz="UTC"),
    ],
)
def test_invalid_forecast_day(consumption, day):
    with pytest.raises(ValueError, match="midnight"):
        build_forecast_features(consumption, day)
