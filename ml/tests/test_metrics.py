"""Tests for forecasting error metrics."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.metrics import baseline_error_metrics


@pytest.fixture
def predictions():
    return pd.DataFrame({
        "day": ["day1", "day1", "day2", "day2"],
        "actual_kwh": [1.0, 2.0, 3.0, 4.0],
        "daily_pred_kwh": [2.0, 3.0, 4.0, 5.0],
        "weekly_pred_kwh": [1.0, 2.0, 3.0, 6.0],
    })


def test_overall_metrics_match_known_values(predictions):
    _, overall = baseline_error_metrics(predictions)
    scores = overall.set_index("model")

    assert scores.loc["daily", "n_hours"] == 4
    assert scores.loc["daily", "n_days"] == 2

    assert scores.loc["daily", "rmse_kwh"] == pytest.approx(1.0)
    assert scores.loc["daily", "mae_kwh"] == pytest.approx(1.0)
    assert scores.loc["daily", "mape_pct"] == pytest.approx(52.0833333333)

    assert scores.loc["weekly", "rmse_kwh"] == pytest.approx(1.0)
    assert scores.loc["weekly", "mae_kwh"] == pytest.approx(0.5)
    assert scores.loc["weekly", "mape_pct"] == pytest.approx(12.5)


def test_daily_metrics_and_pooled_rmse(predictions):
    daily, overall = baseline_error_metrics(predictions)
    scores = daily.set_index(["model", "day"])

    assert scores.loc[("daily", "day1"), "mape_pct"] == pytest.approx(75.0)
    assert scores.loc[("daily", "day2"), "mape_pct"] == pytest.approx(
        29.1666666667
    )

    assert scores.loc[("weekly", "day1"), "rmse_kwh"] == pytest.approx(0.0)
    assert scores.loc[("weekly", "day2"), "rmse_kwh"] == pytest.approx(
        np.sqrt(2)
    )
    assert scores.loc[("weekly", "day2"), "mape_pct"] == pytest.approx(25.0)

    weekly_overall = overall.set_index("model").loc["weekly", "rmse_kwh"]

    # Pooled RMSE differs from the average of daily RMSE values.
    mean_daily_rmse = scores.loc["weekly", "rmse_kwh"].mean()
    assert weekly_overall == pytest.approx(1.0)
    assert weekly_overall != pytest.approx(mean_daily_rmse)


@pytest.mark.parametrize("invalid_actual", [0.0, -1.0])
def test_nonpositive_actual_is_rejected(predictions, invalid_actual):
    predictions.loc[0, "actual_kwh"] = invalid_actual

    with pytest.raises(ValueError, match="MAPE requires positive"):
        baseline_error_metrics(predictions)


@pytest.mark.parametrize("invalid_forecast", [np.nan, np.inf])
def test_invalid_forecast_is_rejected(predictions, invalid_forecast):
    predictions.loc[0, "daily_pred_kwh"] = invalid_forecast

    with pytest.raises(ValueError):
        baseline_error_metrics(predictions)


def test_missing_columns_are_rejected(predictions):
    predictions = predictions.drop(columns=["weekly_pred_kwh"])

    with pytest.raises(ValueError, match="Missing required"):
        baseline_error_metrics(predictions)


def test_empty_predictions_are_rejected(predictions):
    with pytest.raises(ValueError, match="No predictions"):
        baseline_error_metrics(predictions.iloc[:0])
