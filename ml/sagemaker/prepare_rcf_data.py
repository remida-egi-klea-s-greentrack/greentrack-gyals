"""Write Random Cut Forest inputs: 24-hour shingles of hourly consumption, same split as log-MAD.

Each record describes one hour t by the kWh of hours t-23 ... t, so RCF can flag an unusual
hour in the context of the day before it. Records that include any missing hour are dropped.
Raw kWh, not log: log shrinks spikes (x5 becomes +1.6) and stretches near-zero hours. With log
inputs RCF caught 0/20 injected x5 spikes and no validation hour passed the 91.5th training
percentile (10 Nov 2026 run).

Variables:
    SHINGLE_HOURS      - window length per record (RCF feature_dim)
    TRAIN_END          - last training hour (log-MAD training window)
    VALIDATION_START/END - validation window (log-MAD validation; held-out test stays untouched)

Usage:
    python -m ml.sagemaker.prepare_rcf_data --input gold.parquet --output out_dir
"""

import argparse
from pathlib import Path

import pandas as pd

from ml.forecasting.input_data import load_hourly_consumption

SHINGLE_HOURS = 24
TRAIN_END = "2009-12-31 23:00"
VALIDATION_START = "2010-01-01 00:00"
VALIDATION_END = "2010-05-31 23:00"


def build_shingles(consumption: pd.Series, hours: int = SHINGLE_HOURS) -> pd.DataFrame:
    """One row per hour t with columns lag_{hours-1} ... lag_0 holding kWh; incomplete windows dropped.

    load_hourly_consumption guarantees a gap-free hourly index (missing hours are NaN),
    so a positional shift of k rows is exactly k hours.
    """
    columns = {f"lag_{k}": consumption.shift(k) for k in range(hours - 1, -1, -1)}
    return pd.DataFrame(columns).dropna()


def write_rcf_inputs(gold_path: Path, output_dir: Path) -> dict:
    """Write train.csv, validation.csv and validation_index.csv; return row counts."""
    shingles = build_shingles(load_hourly_consumption(gold_path))
    train = shingles.loc[:TRAIN_END]
    validation = shingles.loc[VALIDATION_START:VALIDATION_END]

    output_dir.mkdir(parents=True, exist_ok=True)
    # RCF reads CSV without a header; training records carry no label.
    train.to_csv(output_dir / "train.csv", header=False, index=False)
    validation.to_csv(output_dir / "validation.csv", header=False, index=False)
    # Row i of validation.csv scores the hour in row i of this file.
    pd.Series(validation.index, name="timestamp").to_csv(output_dir / "validation_index.csv", index=False)
    return {"train": len(train), "validation": len(validation)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    counts = write_rcf_inputs(args.input, args.output)
    print(f"Shingle length: {SHINGLE_HOURS} hours (feature_dim={SHINGLE_HOURS})")
    print(f"Training records:   {counts['train']} (through {TRAIN_END})")
    print(f"Validation records: {counts['validation']} ({VALIDATION_START} to {VALIDATION_END})")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
