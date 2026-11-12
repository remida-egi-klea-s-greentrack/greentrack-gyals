"""Construct chronological training rows for electricity forecasting."""

import numpy as np
import pandas as pd

from ml.forecasting.features import build_forecast_features


def build_training_rows(
    consumption: pd.Series,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Build hourly training examples using origin-safe features."""
    start_day = pd.Timestamp(start)
    end_day = pd.Timestamp(end)

    if (
        start_day.tz is not None
        or end_day.tz is not None
        or start_day != start_day.normalize()
        or end_day != end_day.normalize()
    ):
        raise ValueError("Start and end must be timezone-naive dates")

    if start_day > end_day:
        raise ValueError("Start date must not exceed end date")

    frames = []

    for day in pd.date_range(start_day, end_day, freq="D"):
        features = build_forecast_features(consumption, day)

        targets = pd.DatetimeIndex(features["timestamp"])
        actual = consumption.reindex(targets).to_numpy(dtype=float)

        if np.isinf(actual).any():
            raise ValueError("Training targets must be finite")

        features["target_kwh"] = actual

        # Missing targets cannot be used for supervised training.
        # Missing historical features are retained for XGBoost.
        valid = features.loc[features["target_kwh"].notna()]
        if not valid.empty:
            frames.append(valid)

    if not frames:
        raise ValueError("No valid training targets in date range")

    return pd.concat(frames, ignore_index=True)
