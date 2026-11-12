"""Steps of the SageMaker forecast pipeline (Challenge 3 MLOps): prepare and evaluate.

Both run as SageMaker Processing jobs in the built-in XGBoost container (it has pandas, xgboost
and boto3). Terraform copies this package to S3; the job gets it in CODE_DIR, which is on PYTHONPATH.

    prepare   reads every Gold hour through Athena and writes the frozen XGBoost training set
              (same rows and window as ml/forecasting) plus the hourly series for evaluation
    evaluate  scores the validation window (Jan-May 2010; never the held-out test period) with the
              trained model and both seasonal naive baselines, and writes evaluation.json, which the
              pipeline condition reads and the Model Registry stores as model quality

Variables:
    BASE              - SageMaker Processing root; inputs and outputs are folders below it
    SQL               - read-only query of the whole Gold hourly table ({db} filled from the environment)
    TRAINING_COLUMNS  - built-in XGBoost CSV order: target first, then FEATURE_COLUMNS, no header
    HOURS_FILE        - hourly series handed from prepare to evaluate
"""

import json
import sys
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

from ml.forecasting.evaluation import rolling_baseline_predictions
from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.input_data import hourly_series
from ml.forecasting.metrics import forecast_error_metrics
from ml.forecasting.run_xgboost_validation import (
    MODEL_COLUMNS,
    TRAIN_END,
    TRAIN_START,
    VALIDATION_END,
    VALIDATION_START,
)
from ml.forecasting.training_data import build_training_rows
from ml.forecasting.xgboost_evaluation import add_xgboost_predictions

BASE = Path("/opt/ml/processing")
SQL = 'SELECT "timestamp", global_active_power_kwh, complete FROM {db}.gold_hourly_consumption ORDER BY "timestamp"'
TRAINING_COLUMNS = ["target_kwh", *FEATURE_COLUMNS]
HOURS_FILE = "hours.csv"


def hourly_frame(rows):
    """Athena rows (strings) as the Gold hourly frame; incomplete hours get no kWh, as in the contract."""
    frame = pd.DataFrame(rows, columns=["timestamp", "global_active_power_kwh", "complete"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["complete"] = frame["complete"].str.lower().eq("true")
    kwh = pd.to_numeric(frame["global_active_power_kwh"])
    frame["global_active_power_kwh"] = kwh.where(frame["complete"])
    return frame


def prepare(rows, out_dir):
    """Write train/train.csv and hours/hours.csv; return the number of training rows."""
    frame = hourly_frame(rows)
    train = build_training_rows(hourly_series(frame), TRAIN_START, TRAIN_END)
    (out_dir / "train").mkdir(parents=True, exist_ok=True)
    (out_dir / "hours").mkdir(parents=True, exist_ok=True)
    # Missing lag features stay empty, which XGBoost reads as missing values.
    train[TRAINING_COLUMNS].to_csv(out_dir / "train" / "train.csv", header=False, index=False)
    frame.to_csv(out_dir / "hours" / HOURS_FILE, index=False)
    return len(train)


def read_hours(path):
    return hourly_series(pd.read_csv(path, parse_dates=["timestamp"]))


class BoosterModel:
    """A raw xgboost.Booster with the .predict(DataFrame) used by add_xgboost_predictions.

    The built-in container trains on unnamed CSV columns, so features go in FEATURE_COLUMNS order.
    """

    def __init__(self, booster):
        self.booster = booster

    def predict(self, features):
        import xgboost

        values = features[FEATURE_COLUMNS].to_numpy(dtype=float)
        return self.booster.predict(xgboost.DMatrix(values, missing=np.nan))


def load_model(model_dir):
    """Booster from the training job's model.tar.gz (the built-in container names the file xgboost-model)."""
    import xgboost

    # Read the one file from the archive instead of extracting it (no paths written to disk).
    with tarfile.open(Path(model_dir) / "model.tar.gz") as archive:
        raw = archive.extractfile("xgboost-model").read()
    booster = xgboost.Booster()
    booster.load_model(bytearray(raw))
    return BoosterModel(booster)


def evaluate(model, consumption):
    """Validation metrics of XGBoost and both baselines on the same days."""
    baseline, exclusions = rolling_baseline_predictions(consumption, VALIDATION_START, VALIDATION_END)
    predictions = add_xgboost_predictions(model, consumption, baseline)
    _, overall = forecast_error_metrics(predictions, MODEL_COLUMNS)
    rmse = dict(zip(overall["model"], overall["rmse_kwh"]))
    mae = dict(zip(overall["model"], overall["mae_kwh"]))
    return {
        "xgboost_rmse": rmse["xgboost"],
        "baseline_rmse": min(rmse["daily"], rmse["weekly"]),
        "validation": {"start": VALIDATION_START, "end": VALIDATION_END,
                       "days": int(predictions["day"].nunique()), "excluded_days": len(exclusions)},
        "rmse_kwh": rmse,
        "mae_kwh": mae,
        # Model Registry model-quality format.
        "regression_metrics": {"rmse": {"value": rmse["xgboost"]}, "mae": {"value": mae["xgboost"]}},
    }


def main(argv):
    import os

    command = argv[1] if len(argv) > 1 else ""
    if command == "prepare":
        import boto3

        from ml.inference.aws import run_query

        rows = run_query(boto3.client("athena"), SQL.format(db=os.environ["ATHENA_DATABASE"]),
                         os.environ["ATHENA_WORKGROUP"], timeout_seconds=600)
        print(f"Gold hours: {len(rows)}; training rows: {prepare(rows, BASE)} ({TRAIN_START} to {TRAIN_END})")
    elif command == "evaluate":
        result = evaluate(load_model(BASE / "model"), read_hours(BASE / "hours" / HOURS_FILE))
        (BASE / "evaluation").mkdir(parents=True, exist_ok=True)
        (BASE / "evaluation" / "evaluation.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    else:
        sys.exit("usage: python -m ml.pipeline.steps prepare|evaluate")


if __name__ == "__main__":
    main(sys.argv)
