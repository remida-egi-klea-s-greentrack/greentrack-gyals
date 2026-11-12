"""Write inference/params.json: log-MAD fitted through 2008 and both detectors' 2009 reference scores.

Runs once on a workstation (uses pandas; not part of the Lambda zip), after the serverless RCF
endpoint exists. Same scheme as the RCF confirmation run: fit through 2008, calibrate on 2009.

    python -m ml.inference.calibrate --gold <gold.parquet> --rcf-endpoint <name> \
        --bucket <ml-bucket> [--key inference/params.json] --output params.json

Variables:
    FIT_END                       - last hour used to fit log-MAD (RCF was trained on the same period)
    CALIBRATION_START/END         - 2009: reference scores for percentiles
    hours                         - dict {hour: kWh or None} built from the Gold file
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from ml.anomaly.global_log_mad import GlobalLogMADDetector
from ml.forecasting.input_data import load_hourly_consumption
from ml.inference import aws, core

FIT_END = "2008-12-31 23:00"
CALIBRATION_START = "2009-01-01 00:00"
CALIBRATION_END = "2009-12-31 23:00"


def build_params(consumption, score_rcf, models):
    """params.json content. score_rcf maps a list of 24-value records to raw RCF scores."""
    consumption = consumption.loc[:CALIBRATION_END]
    detector = GlobalLogMADDetector().fit(consumption.loc[:FIT_END])
    calibration = consumption.loc[CALIBRATION_START:CALIBRATION_END]
    mad_reference = detector.score(calibration)["robust_z"].abs().dropna().sort_values()

    hours = {t.to_pydatetime(): (None if v != v else float(v)) for t, v in consumption.items()}  # NaN -> None
    windows = core.shingles(hours, [t.to_pydatetime() for t in calibration.index])
    rcf_reference = sorted(score_rcf(list(windows.values())))

    return {
        "fit_end": FIT_END,
        "calibration": [CALIBRATION_START, CALIBRATION_END],
        "models": models,
        "log_mad": {
            "medians": [float(detector.medians_.loc[slot]) for slot in range(168)],
            "mads": [float(detector.mads_.loc[slot]) for slot in range(168)],
            "reference": [float(v) for v in mad_reference],
        },
        "rcf": {"shingle_hours": core.SHINGLE_HOURS, "reference": [float(v) for v in rcf_reference]},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    parser.add_argument("--rcf-endpoint", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--key", default="inference/params.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import boto3

    runtime = boto3.client("sagemaker-runtime")
    params = build_params(
        load_hourly_consumption(args.gold),
        lambda records: aws.score_rcf(runtime, args.rcf_endpoint, records),
        {"rcf_endpoint": args.rcf_endpoint, "created": datetime.now().isoformat(timespec="seconds")},
    )
    args.output.write_text(json.dumps(params) + "\n")
    boto3.client("s3").upload_file(str(args.output), args.bucket, args.key)
    print(f"log-MAD reference: {len(params['log_mad']['reference'])} hours; RCF reference: {len(params['rcf']['reference'])} windows")
    print(f"Uploaded to s3://{args.bucket}/{args.key}")


if __name__ == "__main__":
    main()
