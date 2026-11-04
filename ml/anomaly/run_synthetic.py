"""Reproducible synthetic-anomaly sensitivity evaluation."""

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
        "2010-01-01":"2010-05-31 23:00"
    ]

    detector = GlobalLogMADDetector().fit(train)
    before = detector.score(validation).set_index("timestamp")

    eligible = before.index[
        before["anomaly_score"].notna()
        & before["severity"].isna()
    ]

    if len(eligible) < 40:
        raise ValueError("Need at least 40 normal validation hours")

    rng = np.random.default_rng(42)
    selected = pd.DatetimeIndex(
        np.sort(
            rng.choice(
                eligible.to_numpy(),
                size=40,
                replace=False,
            )
        )
    )

    high_times = selected[::2]
    low_times = selected[1::2]

    modified = validation.copy()
    modified.loc[high_times] *= 5.0
    modified.loc[low_times] *= 0.2

    after = detector.score(modified).set_index("timestamp")

    other = before.index.difference(selected)
    unchanged = before.loc[
        other, "anomaly_score"
    ].equals(after.loc[other, "anomaly_score"])

    if not unchanged:
        raise AssertionError("Unmodified scores changed")

    details = []

    summary = {
        "method": "global_hour_of_week_log_mad",
        "experiment": "synthetic_multiplicative_changes",
        "seed": 42,
        "test_period_evaluated": False,
        "input_sha256": hashlib.sha256(
            args.input.read_bytes()
        ).hexdigest(),
        "unmodified_scores_unchanged": unchanged,
        "results": {},
    }

    for name, times, factor, sign in [
        ("high_x5", high_times, 5.0, 1),
        ("low_x0_2", low_times, 0.2, -1),
    ]:
        rows = after.loc[times]
        detected = rows["severity"].notna()
        direction_correct = rows["robust_z"] * sign > 0

        summary["results"][name] = {
            "injected": len(times),
            "detected": int(detected.sum()),
            "detection_rate": float(detected.mean()),
            "correct_direction": int(direction_correct.sum()),
            "severity_counts": {
                level: int((rows["severity"] == level).sum())
                for level in ("low", "medium", "high")
            },
        }

        for timestamp in times:
            details.append({
                "timestamp": timestamp,
                "injection": name,
                "factor": factor,
                "original_kwh": float(validation.loc[timestamp]),
                "modified_kwh": float(modified.loc[timestamp]),
                "original_score": float(
                    before.loc[timestamp, "anomaly_score"]
                ),
                "modified_score": float(
                    after.loc[timestamp, "anomaly_score"]
                ),
                "robust_z": float(
                    after.loc[timestamp, "robust_z"]
                ),
                "severity": after.loc[timestamp, "severity"],
            })

    args.output.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(details).to_csv(
        args.output / "injections.csv", index=False
    )

    (args.output / "manifest.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
