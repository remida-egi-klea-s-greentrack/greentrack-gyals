"""Reproducible local anomaly validation report."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly.global_log_mad import GlobalLogMADDetector
from ml.forecasting.input_data import load_hourly_consumption


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    consumption = load_hourly_consumption(args.input)

    train = consumption.loc[:"2009-12-31 23:00"]
    validation = consumption.loc[
        "2010-01-01 00:00":"2010-05-31 23:00"
    ]

    if train.dropna().empty or validation.dropna().empty:
        raise ValueError("Training and validation must be nonempty")

    detector = GlobalLogMADDetector().fit(train)
    scores = detector.score(validation)

    scores["flagged"] = scores["severity"].notna()
    alerts = scores.loc[scores["flagged"]].copy()
    scored = scores.loc[scores["anomaly_score"].notna()].copy()

    # Monthly alert rates: only scored observations in denominator.
    scored["month"] = scored["timestamp"].dt.strftime("%Y-%m")
    monthly = scored.groupby("month").agg(
        scored_hours=("anomaly_score", "size"),
        alerts=("flagged", "sum"),
    )
    monthly["alert_rate_pct"] = (
        100 * monthly["alerts"] / monthly["scored_hours"]
    )
    monthly = monthly.reset_index()

    # Consecutive flagged hours form one episode.
    alerts = alerts.sort_values("timestamp")
    alerts["episode_id"] = (
        alerts["timestamp"]
        .diff()
        .ne(pd.Timedelta(hours=1))
        .cumsum()
    )

    episodes = alerts.groupby("episode_id").agg(
        start=("timestamp", "min"),
        end=("timestamp", "max"),
        flagged_hours=("timestamp", "size"),
        peak_score=("anomaly_score", "max"),
    ).reset_index()

    # Training-only calibration diagnostics.
    training_scores = detector.score(train)
    training_z = (
        training_scores["robust_z"]
        .dropna()
        .abs()
        .to_numpy()
    )
    z_thresholds = np.percentile(
        training_z, [99, 99.5, 99.9]
    )

    checksum = hashlib.sha256(
        args.input.read_bytes()
    ).hexdigest()

    summary = {
        "method": "global_hour_of_week_log_mad",
        "input_sha256": checksum,
        "train_end": "2009-12-31 23:00",
        "validation_start": "2010-01-01 00:00",
        "validation_end": "2010-05-31 23:00",
        "test_period_evaluated": False,
        "training_valid_hours": int(train.notna().sum()),
        "validation_valid_hours": int(validation.notna().sum()),
        "validation_scored_hours": int(len(scored)),
        "alert_hours": int(len(alerts)),
        "alert_rate_pct": float(
            100 * len(alerts) / len(scored)
        ),
        "episodes": int(len(episodes)),
        "severity_counts": {
            level: int((alerts["severity"] == level).sum())
            for level in ("low", "medium", "high")
        },
        "severity_percentiles": {
            "low": 0.99,
            "medium": 0.995,
            "high": 0.999,
        },
        "training_abs_z_thresholds": {
            "p99": float(z_thresholds[0]),
            "p99_5": float(z_thresholds[1]),
            "p99_9": float(z_thresholds[2]),
        },
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "limitations": [
            "No verified ground-truth anomaly labels.",
            "Monthly seasonal effects remain.",
            "Validation excludes August holiday behavior.",
            "Training percentiles use in-sample deviations.",
            "Alert hours are not confirmed anomalous events.",
        ],
    }

    args.output.mkdir(parents=True, exist_ok=True)

    scores.to_csv(args.output / "scores.csv", index=False)

    alerts[
        ["timestamp", "consumption_kwh",
         "anomaly_score", "severity"]
    ].to_csv(args.output / "anomalies.csv", index=False)

    monthly.to_csv(
        args.output / "monthly_summary.csv", index=False
    )
    episodes.to_csv(
        args.output / "episodes.csv", index=False
    )

    (args.output / "manifest.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
