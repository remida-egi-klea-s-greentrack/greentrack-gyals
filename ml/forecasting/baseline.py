"""Seasonal naive forecasting baselines."""

import pandas as pd


def seasonal_naive_forecast(
    consumption: pd.Series,
    origin: pd.Timestamp,
    horizon: int = 24,
    season_hours: int = 168,
) -> pd.Series:
    """Predict each target hour using consumption one season earlier."""

    if not 1 <= horizon <= season_hours:
        raise ValueError("Horizon must be between 1 and season_hours")

    index = consumption.index

    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Consumption must have a DatetimeIndex")

    if index.has_duplicates:
        raise ValueError("Duplicate timestamps")

    if not (index == index.floor("h")).all():
        raise ValueError("Timestamps must be on whole hours")

    origin = pd.Timestamp(origin)

    if origin not in index:
        raise ValueError("Forecast origin is not in the series")

    # Only data available at the time of prediction.
    history = consumption.loc[index <= origin]

    # Create timestamps for the next hours.
    future = pd.date_range(
        start=origin + pd.Timedelta(hours=1),
        periods=horizon,
        freq="h",
    )

    # Find matching timestamps from the previous season.
    reference = future - pd.Timedelta(hours=season_hours)

    predicted = history.reindex(reference)

    if predicted.isna().any():
        raise ValueError("Missing historical reference values")

    return pd.Series(
        predicted.to_numpy(dtype=float),
        index=future,
        name="predicted_kwh",
    )
