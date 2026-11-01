"""Tests for XGBoost evaluation alignment and validation."""

import numpy as np
import pandas as pd
import pytest

from ml.forecasting.evaluation import rolling_baseline_predictions
from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.xgboost_evaluation import add_xgboost_predictions


class Lag24Model:
    """Fake model returning the historical 24-hour lag."""

    def predict(self, features):
        assert list(features.columns) == FEATURE_COLUMNS
        return features["lag_24h_kwh"].to_numpy(dtype=float)


@pytest.fixture
def scenario():
    hours = pd.date_range(
        "2010-01-01", periods=14 * 24, freq="h"
    )
    consumption = pd.Series(
        np.arange(len(hours), dtype=float) + 1,
        index=hours,
    )

    baseline, exclusions = rolling_baseline_predictions(
        consumption, "2010-01-10", "2010-01-11"
    )

    assert exclusions.empty
    return consumption, baseline


def test_predictions_align_with_baseline(scenario):
    consumption, baseline = scenario

    result = add_xgboost_predictions(
        Lag24Model(), consumption, baseline
    )

    assert len(result) == 48
    assert result["day"].nunique() == 2

    pd.testing.assert_frame_equal(
        result[baseline.columns], baseline
    )

    np.testing.assert_array_equal(
        result["xgboost_pred_kwh"],
        result["daily_pred_kwh"],
    )


def test_future_consumption_does_not_change_forecast(scenario):
    consumption, baseline = scenario
    first_day = baseline.loc[
        baseline["day"] == pd.Timestamp("2010-01-10")
    ].copy()

    original = add_xgboost_predictions(
        Lag24Model(), consumption, first_day
    )

    changed = consumption.copy()
    changed.loc["2010-01-10":] += 10000

    modified = add_xgboost_predictions(
        Lag24Model(), changed, first_day
    )

    np.testing.assert_array_equal(
        original["xgboost_pred_kwh"],
        modified["xgboost_pred_kwh"],
    )


@pytest.mark.parametrize("problem", ["missing_hour", "out_of_order"])
def test_invalid_day_coverage_is_rejected(scenario, problem):
    consumption, baseline = scenario

    if problem == "missing_hour":
        malformed = baseline.iloc[:-1].copy()
    else:
        malformed = pd.concat(
            [
                baseline.iloc[[1]],
                baseline.iloc[[0]],
                baseline.iloc[2:],
            ],
            ignore_index=True,
        )

    with pytest.raises(ValueError, match="Invalid evaluation day"):
        add_xgboost_predictions(
            Lag24Model(), consumption, malformed
        )


@pytest.mark.parametrize("problem", ["short", "nan", "inf"])
def test_invalid_model_predictions_are_rejected(scenario, problem):
    consumption, baseline = scenario

    class BadModel:
        def predict(self, features):
            if problem == "short":
                return np.zeros(23)

            values = np.ones(24)
            values[0] = np.nan if problem == "nan" else np.inf
            return values

    with pytest.raises(ValueError, match="Invalid XGBoost"):
        add_xgboost_predictions(
            BadModel(), consumption, baseline
        )


def test_missing_baseline_columns_are_rejected(scenario):
    consumption, baseline = scenario
    malformed = baseline.drop(columns=["weekly_pred_kwh"])

    with pytest.raises(ValueError, match="Missing baseline"):
        add_xgboost_predictions(
            Lag24Model(), consumption, malformed
        )


def test_empty_evaluation_is_rejected(scenario):
    consumption, baseline = scenario

    with pytest.raises(ValueError, match="No evaluation days"):
        add_xgboost_predictions(
            Lag24Model(), consumption, baseline.iloc[:0]
        )


def test_duplicate_timestamps_are_rejected(scenario):
    consumption, baseline = scenario
    malformed = pd.concat(
        [baseline, baseline.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate evaluation"):
        add_xgboost_predictions(
            Lag24Model(), consumption, malformed
        )
