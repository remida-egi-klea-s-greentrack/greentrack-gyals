"""Evaluate XGBoost on the same days as the seasonal baselines."""

import numpy as np
import pandas as pd

from ml.forecasting.features import (
    FEATURE_COLUMNS,
    build_forecast_features,
)


def add_xgboost_predictions(
    model,
    consumption: pd.Series,
    baseline_predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Attach XGBoost forecasts to existing baseline evaluation rows."""
    required = {
        "day",
        "timestamp",
        "actual_kwh",
        "daily_pred_kwh",
        "weekly_pred_kwh",
    }

    if not required.issubset(baseline_predictions.columns):
        raise ValueError("Missing baseline evaluation columns")

    if baseline_predictions.empty:
        raise ValueError("No evaluation days provided")

    if baseline_predictions["timestamp"].duplicated().any():
        raise ValueError("Duplicate evaluation timestamps")

    forecast_frames = []

    for day, group in baseline_predictions.groupby("day", sort=True):
        features = build_forecast_features(consumption, day)

        expected = pd.DatetimeIndex(features["timestamp"])
        actual_targets = pd.DatetimeIndex(group["timestamp"])

        if len(group) != 24 or not actual_targets.equals(expected):
            raise ValueError("Invalid evaluation day coverage")

        predictions = np.asarray(
            model.predict(features[FEATURE_COLUMNS]),
            dtype=float,
        )

        if predictions.shape != (24,) or not np.isfinite(predictions).all():
            raise ValueError("Invalid XGBoost predictions")

        forecast_frames.append(pd.DataFrame({
            "timestamp": expected,
            "xgboost_pred_kwh": predictions,
        }))

    xgb = pd.concat(forecast_frames, ignore_index=True)

    result = baseline_predictions.merge(
        xgb,
        on="timestamp",
        how="left",
        validate="one_to_one",
    )

    if result["xgboost_pred_kwh"].isna().any():
        raise ValueError("Missing XGBoost forecasts")

    return result
