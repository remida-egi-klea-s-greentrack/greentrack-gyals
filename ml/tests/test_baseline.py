"""Tests for seasonal naive forecasting."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.baseline import seasonal_naive_forecast


ORIGIN = pd.Timestamp("2008-09-15 00:00")


@pytest.fixture
def hourly():
    index = pd.date_range(
        "2008-09-01",
        periods=24 * 21,
        freq="h",
    )
    return pd.Series(
        np.arange(len(index), dtype=float),
        index=index,
    )


@pytest.mark.parametrize("season_hours", [168, 24])
def test_predictions_equal_previous_season(hourly, season_hours):
    original = hourly.copy()

    result = seasonal_naive_forecast(
        hourly, ORIGIN, horizon=24, season_hours=season_hours
    )

    expected_index = pd.date_range(
        ORIGIN + pd.Timedelta(hours=1),
        periods=24,
        freq="h",
    )

    expected = hourly[
        expected_index - pd.Timedelta(hours=season_hours)
    ].to_numpy()

    pd.testing.assert_index_equal(result.index, expected_index)
    np.testing.assert_array_equal(result.to_numpy(), expected)
    pd.testing.assert_series_equal(hourly, original)


def test_unsorted_input(hourly):
    shuffled = hourly.sample(frac=1, random_state=0)

    pd.testing.assert_series_equal(
        seasonal_naive_forecast(shuffled, ORIGIN),
        seasonal_naive_forecast(hourly, ORIGIN),
    )


@pytest.mark.parametrize("season_hours", [168, 24])
def test_future_data_does_not_affect_predictions(hourly, season_hours):
    before = seasonal_naive_forecast(
        hourly, ORIGIN,
        horizon=season_hours,
        season_hours=season_hours,
    )

    modified = hourly.copy()
    modified.loc[modified.index > ORIGIN] = 999.0

    after = seasonal_naive_forecast(
        modified, ORIGIN,
        horizon=season_hours,
        season_hours=season_hours,
    )

    pd.testing.assert_series_equal(before, after)


def test_missing_reference_raises(hourly):
    reference = ORIGIN + pd.Timedelta(hours=5) - pd.Timedelta(hours=168)

    with_nan = hourly.copy()
    with_nan.loc[reference] = np.nan

    with pytest.raises(ValueError, match="Missing historical reference"):
        seasonal_naive_forecast(with_nan, ORIGIN)

    with pytest.raises(ValueError, match="Missing historical reference"):
        seasonal_naive_forecast(hourly.drop(reference), ORIGIN)


def test_invalid_inputs(hourly):
    with pytest.raises(ValueError, match="Horizon"):
        seasonal_naive_forecast(hourly, ORIGIN, horizon=169)

    with pytest.raises(ValueError, match="Duplicate"):
        seasonal_naive_forecast(
            pd.concat([hourly, hourly.iloc[:1]]),
            ORIGIN,
        )

    minute_data = pd.Series(
        1.0,
        index=pd.date_range(
            "2008-09-01",
            periods=60 * 24 * 21,
            freq="min",
        ),
    )

    with pytest.raises(ValueError, match="whole hours"):
        seasonal_naive_forecast(minute_data, ORIGIN)

    with pytest.raises(ValueError, match="origin"):
        seasonal_naive_forecast(
            hourly,
            ORIGIN + pd.Timedelta(minutes=30),
        )
