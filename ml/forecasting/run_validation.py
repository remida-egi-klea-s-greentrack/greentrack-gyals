"""Generate a reproducible seasonal-baseline validation report."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from ml.forecasting.input_data import load_hourly_consumption
from ml.forecasting.evaluation import rolling_baseline_predictions
from ml.forecasting.metrics import baseline_error_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    consumption = load_hourly_consumption(args.input)

    start = "2010-01-01"
    end = "2010-05-31"

    predictions, exclusions = rolling_baseline_predictions(
        consumption, start, end
    )
    per_day, overall = baseline_error_metrics(predictions)

    args.output.mkdir(parents=True, exist_ok=True)

    predictions.to_csv(args.output / "predictions.csv", index=False)
    per_day.to_csv(args.output / "per_day_metrics.csv", index=False)
    overall.to_csv(args.output / "overall_metrics.csv", index=False)
    exclusions.to_csv(args.output / "exclusions.csv", index=False)

    manifest = {
        "period": "validation",
        "start": start,
        "end": end,
        "horizon_hours": 24,
        "season_hours": {"daily": 24, "weekly": 168},
        "source_sha256": hashlib.sha256(
            args.input.read_bytes()
        ).hexdigest(),
        "eligible_days": int(predictions["day"].nunique()),
        "excluded_days": len(exclusions),
        "forecast_hours": len(predictions),
    }

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    print("Validation report saved to:", args.output)
    print("Eligible days:", manifest["eligible_days"])
    print("Excluded days:", manifest["excluded_days"])
    print("\nOverall metrics:")
    print(overall.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
