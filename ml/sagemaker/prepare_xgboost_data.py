"""Write the frozen XGBoost training set in the format SageMaker's built-in XGBoost expects.

Same Gold input, same training window and same six features as ml/forecasting, so a
SageMaker training job reproduces the locally validated model (parity check).

Variables:
    TRAIN_START, TRAIN_END  - training window, imported from the frozen local validation
    HYPERPARAMETERS         - built-in XGBoost names for the frozen XGBRegressor settings
    COLUMNS                 - CSV column order: target first, then FEATURE_COLUMNS

Usage:
    python -m ml.sagemaker.prepare_xgboost_data --input gold.parquet --output out_dir
"""

import argparse
import json
from pathlib import Path

from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.input_data import load_hourly_consumption
from ml.forecasting.run_xgboost_validation import TRAIN_END, TRAIN_START
from ml.forecasting.training_data import build_training_rows

# Built-in algorithm names for the XGBRegressor settings in ml/forecasting/xgboost_model.py.
HYPERPARAMETERS = {
    "objective": "reg:squarederror",
    "num_round": "200",
    "max_depth": "4",
    "eta": "0.05",
    "subsample": "0.9",
    "colsample_bytree": "0.9",
    "tree_method": "hist",
    "seed": "42",
}

# Built-in XGBoost reads CSV with the target in the first column and no header row.
COLUMNS = ["target_kwh", *FEATURE_COLUMNS]


def write_training_csv(gold_path: Path, output_dir: Path) -> int:
    """Build the frozen training rows and write train.csv; return the row count."""
    consumption = load_hourly_consumption(gold_path)
    train = build_training_rows(consumption, TRAIN_START, TRAIN_END)

    output_dir.mkdir(parents=True, exist_ok=True)
    # Missing historical features stay empty, which XGBoost treats as missing values.
    train[COLUMNS].to_csv(output_dir / "train.csv", header=False, index=False)
    (output_dir / "hyperparameters.json").write_text(json.dumps(HYPERPARAMETERS, indent=2) + "\n")
    return len(train)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = write_training_csv(args.input, args.output)
    print(f"Training rows: {rows} ({TRAIN_START} to {TRAIN_END})")
    print(f"Columns: {', '.join(COLUMNS)} (no header)")
    print(f"Written: {args.output / 'train.csv'}, {args.output / 'hyperparameters.json'}")


if __name__ == "__main__":
    main()
