"""Write Random Cut Forest inputs: 24-hour shingles of hourly consumption, split FIT / CAL / VAL.

Each record describes one hour t by the kWh of hours t-23 ... t, so RCF can flag an unusual
hour in the context of the day before it. Records that include any missing hour are dropped.
Raw kWh, not log: log shrinks spikes (x5 becomes +1.6) and stretches near-zero hours. With log
inputs RCF caught 0/20 injected x5 spikes and no validation hour passed the 91.5th training
percentile (10 Nov 2026 run).

Thresholds come from out-of-sample 2009 scores, not from training scores: the score tail of
2007-2008 is heavier than 2009-2010, so training-calibrated thresholds were too high for 2010
(offline investigation, 11 Nov 2026).

Variables:
    SHINGLE_HOURS          - window length per record (RCF feature_dim)
    FIT_END                - last hour whose window trains RCF (FIT = data start .. 2008)
    CALIBRATION_START/END  - 2009: scores here set the alert thresholds
    VALIDATION_START/END   - Jan-May 2010; the held-out test period after it is never read

Usage:
    python -m ml.sagemaker.prepare_rcf_data --input gold.parquet --output out_dir
"""

import argparse
from pathlib import Path

import pandas as pd

from ml.forecasting.input_data import load_hourly_consumption

SHINGLE_HOURS = 24
FIT_END = "2008-12-31 23:00"
CALIBRATION_START = "2009-01-01 00:00"
CALIBRATION_END = "2009-12-31 23:00"
VALIDATION_START = "2010-01-01 00:00"
VALIDATION_END = "2010-05-31 23:00"


def build_shingles(consumption: pd.Series, hours: int = SHINGLE_HOURS) -> pd.DataFrame:
    """One row per hour t with columns lag_{hours-1} ... lag_0 holding kWh; incomplete windows dropped.

    load_hourly_consumption guarantees a gap-free hourly index (missing hours are NaN),
    so a positional shift of k rows is exactly k hours.
    """
    columns = {f"lag_{k}": consumption.shift(k) for k in range(hours - 1, -1, -1)}
    return pd.DataFrame(columns).dropna()


def split_shingles(consumption: pd.Series) -> dict:
    """Shingles per period; the series is cut at VALIDATION_END first, so later hours are never read."""
    shingles = build_shingles(consumption.loc[:VALIDATION_END])
    return {
        "train": shingles.loc[:FIT_END],
        "calibration": shingles.loc[CALIBRATION_START:CALIBRATION_END],
        "validation": shingles.loc[VALIDATION_START:VALIDATION_END],
    }


def write_rcf_inputs(gold_path: Path, output_dir: Path) -> dict:
    """Write <period>.csv for train/calibration/validation (+ index files for the scored ones); return row counts."""
    parts = split_shingles(load_hourly_consumption(gold_path))

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in parts.items():
        # RCF reads CSV without a header; records carry no label.
        frame.to_csv(output_dir / f"{name}.csv", header=False, index=False)
        if name != "train":
            # Row i of <name>.csv scores the hour in row i of this file.
            pd.Series(frame.index, name="timestamp").to_csv(output_dir / f"{name}_index.csv", index=False)
    return {name: len(frame) for name, frame in parts.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    counts = write_rcf_inputs(args.input, args.output)
    print(f"Shingle length: {SHINGLE_HOURS} hours (feature_dim={SHINGLE_HOURS})")
    print(f"Training records:    {counts['train']} (through {FIT_END})")
    print(f"Calibration records: {counts['calibration']} ({CALIBRATION_START} to {CALIBRATION_END})")
    print(f"Validation records:  {counts['validation']} ({VALIDATION_START} to {VALIDATION_END})")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
