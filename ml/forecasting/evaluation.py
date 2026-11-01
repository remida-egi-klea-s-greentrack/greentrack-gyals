"""Rolling evaluation data for seasonal naive forecasting baselines."""

import pandas as pd

from ml.forecasting.baseline import seasonal_naive_forecast


def rolling_baseline_predictions(
    consumption: pd.Series,
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return comparable hourly predictions and excluded forecast days."""
    if not isinstance(consumption.index, pd.DatetimeIndex):
        raise TypeError("Consumption must have a DatetimeIndex")
    if consumption.index.has_duplicates:
        raise ValueError("Duplicate timestamps")
    if not (consumption.index == consumption.index.floor("h")).all():
        raise ValueError("Timestamps must be on whole hours")
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Start date must not exceed end date")

    predictions = []
    exclusions = []

    for day in pd.date_range(start, end, freq="D"):
        target = pd.date_range(day, periods=24, freq="h")
        origin = day - pd.Timedelta(hours=1)

        required = {
            "actual": target,
            "daily": target - pd.Timedelta(hours=24),
            "weekly": target - pd.Timedelta(hours=168),
        }

        missing = [
            name
            for name, hours in required.items()
            if consumption.reindex(hours).isna().any()
        ]

        if missing:
            exclusions.append({
                "day": day,
                "missing": ", ".join(missing),
            })
            continue

        # Explicitly prevent future observations entering the predictor.
        history = consumption.loc[consumption.index <= origin]

        daily = seasonal_naive_forecast(
            history, origin, horizon=24, season_hours=24
        )
        weekly = seasonal_naive_forecast(
            history, origin, horizon=24, season_hours=168
        )

        for timestamp in target:
            predictions.append({
                "day": day,
                "timestamp": timestamp,
                "actual_kwh": float(consumption.at[timestamp]),
                "daily_pred_kwh": float(daily.at[timestamp]),
                "weekly_pred_kwh": float(weekly.at[timestamp]),
            })

    prediction_columns = [
        "day", "timestamp", "actual_kwh",
        "daily_pred_kwh", "weekly_pred_kwh",
    ]

    return (
        pd.DataFrame(predictions, columns=prediction_columns),
        pd.DataFrame(exclusions, columns=["day", "missing"]),
    )
