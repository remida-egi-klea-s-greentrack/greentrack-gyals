"""Leakage-safe features for 24-hour electricity forecasting."""

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "month",
    "lag_24h_kwh",
    "lag_168h_kwh",
    "mean_last_24h_kwh",
]


def build_forecast_features(
    consumption: pd.Series,
    day: str | pd.Timestamp,
) -> pd.DataFrame:
    """Build 24 target-hour feature rows using origin-available data."""
    if not isinstance(consumption.index, pd.DatetimeIndex):
        raise TypeError("Consumption must have a DatetimeIndex")
    if consumption.index.has_duplicates:
        raise ValueError("Duplicate timestamps")
    if consumption.index.tz is not None:
        raise ValueError("Expected timezone-naive timestamps")
    if not (consumption.index == consumption.index.floor("h")).all():
        raise ValueError("Timestamps must be aligned to whole hours")

    day = pd.Timestamp(day)
    if day.tz is not None or day != day.normalize():
        raise ValueError("Forecast day must be a timezone-naive midnight")

    targets = pd.date_range(day, periods=24, freq="h")
    origin = day - pd.Timedelta(hours=1)

    # Nothing after the origin may enter historical features.
    history = consumption.loc[consumption.index <= origin]

    daily_reference = targets - pd.Timedelta(hours=24)
    weekly_reference = targets - pd.Timedelta(hours=168)

    last_24_hours = pd.date_range(
        end=origin, periods=24, freq="h"
    )
    recent = history.reindex(last_24_hours)

    recent_values = recent.to_numpy(dtype=float)
    recent_mean = (
        float(recent_values.mean())
        if np.isfinite(recent_values).all()
        else np.nan
    )

    return pd.DataFrame({
        "timestamp": targets,
        "hour": targets.hour,
        "day_of_week": targets.day_of_week,
        "month": targets.month,
        "lag_24h_kwh": history.reindex(
            daily_reference
        ).to_numpy(dtype=float),
        "lag_168h_kwh": history.reindex(
            weekly_reference
        ).to_numpy(dtype=float),
        "mean_last_24h_kwh": recent_mean,
    })
