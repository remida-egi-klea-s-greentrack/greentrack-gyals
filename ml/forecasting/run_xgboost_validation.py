"""Reproduce the fixed XGBoost versus naive-baseline validation."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import xgboost

from ml.forecasting.evaluation import rolling_baseline_predictions
from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.input_data import load_hourly_consumption
from ml.forecasting.metrics import forecast_error_metrics
from ml.forecasting.training_data import build_training_rows
from ml.forecasting.xgboost_evaluation import add_xgboost_predictions
from ml.forecasting.xgboost_model import train_xgboost


TRAIN_START = "2006-12-17"
TRAIN_END = "2009-12-31"
VALIDATION_START = "2010-01-01"
VALIDATION_END = "2010-05-31"

MODEL_COLUMNS = {
    "daily": "daily_pred_kwh",
    "weekly": "weekly_pred_kwh",
    "xgboost": "xgboost_pred_kwh",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    consumption = load_hourly_consumption(args.input)

    train = build_training_rows(
        consumption, TRAIN_START, TRAIN_END
    )
    model = train_xgboost(train)

    baseline, exclusions = rolling_baseline_predictions(
        consumption, VALIDATION_START, VALIDATION_END
    )

    predictions = add_xgboost_predictions(
        model, consumption, baseline
    )

    per_day, overall = forecast_error_metrics(
        predictions, MODEL_COLUMNS
    )

    args.output.mkdir(parents=True, exist_ok=True)

    predictions.to_csv(
        args.output / "predictions.csv", index=False
    )
    per_day.to_csv(
        args.output / "per_day_metrics.csv", index=False
    )
    overall.to_csv(
        args.output / "overall_metrics.csv", index=False
    )
    exclusions.to_csv(
        args.output / "exclusions.csv", index=False
    )

    model.save_model(args.output / "model.ubj")

    manifest = {
        "model": "XGBRegressor",
        "training_start": TRAIN_START,
        "training_end": TRAIN_END,
        "validation_start": VALIDATION_START,
        "validation_end": VALIDATION_END,
        "forecast_horizon_hours": 24,
        "features": FEATURE_COLUMNS,
        "training_rows": len(train),
        "eligible_days": int(predictions["day"].nunique()),
        "excluded_days": len(exclusions),
        "prediction_hours": len(predictions),
        "model_parameters": model.get_params(),
        "xgboost_version": xgboost.__version__,
        "pandas_version": pd.__version__,
        "input_sha256": hashlib.sha256(
            args.input.read_bytes()
        ).hexdigest(),
    }

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    print("Report saved to:", args.output)
    print("Training rows:", len(train))
    print("Validation days:", manifest["eligible_days"])
    print("Excluded days:", len(exclusions))

    print("\nMODEL COMPARISON")
    print(overall.round(4).to_string(index=False))

    scores = overall.set_index("model")
    weekly_rmse = scores.loc["weekly", "rmse_kwh"]
    xgb_rmse = scores.loc["xgboost", "rmse_kwh"]

    improvement = (weekly_rmse - xgb_rmse) / weekly_rmse * 100
    print(f"\nXGBoost RMSE improvement: {improvement:+.2f}%")

    daily_rmse = per_day.pivot(
        index="day", columns="model", values="rmse_kwh"
    )

    wins = int(
        (daily_rmse["xgboost"] < daily_rmse["weekly"]).sum()
    )

    print(f"Days XGBoost beats weekly: {wins}/{len(daily_rmse)}")


if __name__ == "__main__":
    main()
