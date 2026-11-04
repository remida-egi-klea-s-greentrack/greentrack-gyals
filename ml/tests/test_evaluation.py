"""Tests for rolling seasonal baseline evaluation."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.evaluation import rolling_baseline_predictions


@pytest.fixture
def consumption():
    """Twelve days of complete, deterministic hourly observations."""
    hours = pd.date_range("2010-01-01", periods=12 * 24, freq="h")
    return pd.Series(np.arange(len(hours), dtype=float), index=hours)


def test_predictions_match_historical_references(consumption):
    predictions, exclusions = rolling_baseline_predictions(
        consumption, "2010-01-10", "2010-01-11"
    )

    assert len(predictions) == 48
    assert exclusions.empty

    targets = pd.DatetimeIndex(predictions["timestamp"])

    np.testing.assert_array_equal(
        predictions["actual_kwh"],
        consumption.reindex(targets).to_numpy(),
    )
    np.testing.assert_array_equal(
        predictions["daily_pred_kwh"],
        consumption.reindex(targets - pd.Timedelta(hours=24)).to_numpy(),
    )
    np.testing.assert_array_equal(
        predictions["weekly_pred_kwh"],
        consumption.reindex(targets - pd.Timedelta(hours=168)).to_numpy(),
    )


@pytest.mark.parametrize(
    ("reason", "missing_at"),
    [
        ("actual", "2010-01-10 09:00"),
        ("daily", "2010-01-09 09:00"),
        ("weekly", "2010-01-03 09:00"),
    ],
)
def test_incomplete_windows_are_excluded(consumption, reason, missing_at):
    consumption = consumption.copy()
    consumption.loc[pd.Timestamp(missing_at)] = np.nan

    predictions, exclusions = rolling_baseline_predictions(
        consumption, "2010-01-10", "2010-01-10"
    )

    assert predictions.empty
    assert len(exclusions) == 1
    assert exclusions.iloc[0]["missing"] == reason


def test_future_values_cannot_change_predictions(consumption):
    original, _ = rolling_baseline_predictions(
        consumption, "2010-01-10", "2010-01-10"
    )

    changed = consumption.copy()
    changed.loc["2010-01-10 00:00":"2010-01-10 23:00"] += 10000

    modified, _ = rolling_baseline_predictions(
        changed, "2010-01-10", "2010-01-10"
    )

    for column in ("daily_pred_kwh", "weekly_pred_kwh"):
        np.testing.assert_array_equal(
            original[column], modified[column]
        )


def test_invalid_date_range_is_rejected(consumption):
    with pytest.raises(ValueError, match="Start date"):
        rolling_baseline_predictions(
            consumption, "2010-01-11", "2010-01-10"
        )
