"""Error metrics for hourly electricity consumption forecasts."""

import numpy as np
import pandas as pd


MODEL_COLUMNS = {
    "daily": "daily_pred_kwh",
    "weekly": "weekly_pred_kwh",
}


def baseline_error_metrics(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate per-day and pooled overall RMSE, MAE and MAPE."""
    required = {"day", "actual_kwh", *MODEL_COLUMNS.values()}

    if not required.issubset(predictions.columns):
        raise ValueError("Missing required prediction columns")

    if predictions.empty:
        raise ValueError("No predictions to evaluate")

    if predictions[list(required)].isna().any().any():
        raise ValueError("Predictions contain missing values")

    actual = predictions["actual_kwh"].to_numpy(dtype=float)

    if not np.isfinite(actual).all():
        raise ValueError("Actual consumption must be finite")

    if (actual <= 0).any():
        raise ValueError("MAPE requires positive actual consumption")

    daily_rows = []
    overall_rows = []

    for model, column in MODEL_COLUMNS.items():
        forecast = predictions[column].to_numpy(dtype=float)
        errors = forecast - actual

        if not np.isfinite(errors).all():
            raise ValueError("Forecast errors must be finite")

        ape = np.abs(errors) / actual * 100

        model_errors = pd.DataFrame({
            "day": predictions["day"].to_numpy(),
            "error": errors,
            "ape": ape,
        })

        for day, group in model_errors.groupby("day", sort=True):
            e = group["error"].to_numpy()
            daily_rows.append({
                "day": day,
                "model": model,
                "n_hours": len(e),
                "rmse_kwh": float(np.sqrt(np.mean(e ** 2))),
                "mae_kwh": float(np.mean(np.abs(e))),
                "mape_pct": float(group["ape"].mean()),
            })

        overall_rows.append({
            "model": model,
            "n_days": predictions["day"].nunique(),
            "n_hours": len(errors),
            "rmse_kwh": float(np.sqrt(np.mean(errors ** 2))),
            "mae_kwh": float(np.mean(np.abs(errors))),
            "mape_pct": float(np.mean(ape)),
        })

    return (
        pd.DataFrame(daily_rows),
        pd.DataFrame(overall_rows),
    )
