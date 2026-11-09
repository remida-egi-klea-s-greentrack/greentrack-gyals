"""Train SageMaker Random Cut Forest and compare it with the log-MAD baseline on the same hours.

Two commands:
    train    start an RCF training job on rcf/train/ in the ML bucket and wait for it
    compare  deploy a temporary endpoint, score training + validation shingles, delete the endpoint,
             then compare alerts and synthetic-injection detection with log-MAD

Variables:
    HYPERPARAMETERS - RCF settings (feature_dim = shingle length; trees/samples at RCF defaults)
    SEVERITY_LEVELS - training-percentile cut-offs, identical to log-MAD (0.99 / 0.995 / 0.999)
    BATCH_SIZE      - records per InvokeEndpoint call (well under the 6 MB payload limit)

Usage:
    python -m ml.sagemaker.rcf_compare train --bucket B --role-arn R --image-uri I
    python -m ml.sagemaker.rcf_compare compare --gold gold.parquet --model-data s3://.../model.tar.gz \
        --role-arn R --image-uri I --output out_dir
"""

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly.global_log_mad import GlobalLogMADDetector
from ml.forecasting.input_data import load_hourly_consumption
from ml.sagemaker.prepare_rcf_data import (
    SHINGLE_HOURS,
    TRAIN_END,
    VALIDATION_END,
    VALIDATION_START,
    build_shingles,
)

HYPERPARAMETERS = {"feature_dim": str(SHINGLE_HOURS), "num_trees": "100", "num_samples_per_tree": "256"}
SEVERITY_LEVELS = [(0.99, "low"), (0.995, "medium"), (0.999, "high")]
BATCH_SIZE = 500


def training_job_request(job_name, bucket, role_arn, image_uri, instance_type="ml.m5.large"):
    """CreateTrainingJob parameters for built-in RCF (unlabelled CSV, sharded train channel)."""
    return {
        "TrainingJobName": job_name,
        "AlgorithmSpecification": {"TrainingImage": image_uri, "TrainingInputMode": "File"},
        "RoleArn": role_arn,
        "InputDataConfig": [{
            "ChannelName": "train",
            "ContentType": "text/csv;label_size=0",
            "DataSource": {"S3DataSource": {
                "S3DataType": "S3Prefix",
                "S3Uri": f"s3://{bucket}/rcf/train/",
                "S3DataDistributionType": "ShardedByS3Key",
            }},
        }],
        "OutputDataConfig": {"S3OutputPath": f"s3://{bucket}/rcf/models/"},
        "ResourceConfig": {"InstanceType": instance_type, "InstanceCount": 1, "VolumeSizeInGB": 5},
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "HyperParameters": HYPERPARAMETERS,
    }


def train(sagemaker_client, bucket, role_arn, image_uri):
    """Start the RCF training job, wait until it ends, and return its description."""
    job_name = f"greentrack-rcf-{time.strftime('%Y%m%d-%H%M%S')}"
    sagemaker_client.create_training_job(**training_job_request(job_name, bucket, role_arn, image_uri))
    print(f"Started {job_name}; waiting (usually 3-5 minutes)...")
    sagemaker_client.get_waiter("training_job_completed_or_stopped").wait(TrainingJobName=job_name)
    return sagemaker_client.describe_training_job(TrainingJobName=job_name)


@contextmanager
def temporary_endpoint(sagemaker_client, name, image_uri, model_data, role_arn, instance_type="ml.m5.large"):
    """Create model + endpoint config + endpoint; always delete all three afterwards, even on errors."""
    try:
        sagemaker_client.create_model(
            ModelName=name,
            PrimaryContainer={"Image": image_uri, "ModelDataUrl": model_data},
            ExecutionRoleArn=role_arn,
        )
        sagemaker_client.create_endpoint_config(
            EndpointConfigName=name,
            ProductionVariants=[{
                "VariantName": "AllTraffic",
                "ModelName": name,
                "InstanceType": instance_type,
                "InitialInstanceCount": 1,
            }],
        )
        sagemaker_client.create_endpoint(EndpointName=name, EndpointConfigName=name)
        print(f"Creating endpoint {name}; waiting (usually 5-8 minutes)...")
        sagemaker_client.get_waiter("endpoint_in_service").wait(EndpointName=name)
        yield name
    finally:
        # Billing stops only when the endpoint is deleted; each delete is attempted independently.
        for action, kwargs in [
            ("delete_endpoint", {"EndpointName": name}),
            ("delete_endpoint_config", {"EndpointConfigName": name}),
            ("delete_model", {"ModelName": name}),
        ]:
            try:
                getattr(sagemaker_client, action)(**kwargs)
                print(f"{action}: {name}")
            except Exception as error:  # report and continue so the remaining deletes still run
                print(f"{action} failed for {name}: {error}")


def endpoint_scorer(runtime_client, endpoint_name, batch_size=BATCH_SIZE):
    """Return a function that scores an (n, feature_dim) array through the endpoint."""
    def score(records):
        scores = []
        for start in range(0, len(records), batch_size):
            chunk = records[start:start + batch_size]
            body = "\n".join(",".join(f"{value:.6f}" for value in row) for row in chunk)
            response = runtime_client.invoke_endpoint(
                EndpointName=endpoint_name, ContentType="text/csv", Accept="application/json", Body=body,
            )
            scores.extend(item["score"] for item in json.loads(response["Body"].read())["scores"])
        if len(scores) != len(records):
            raise ValueError(f"Expected {len(records)} scores, got {len(scores)}")
        return np.asarray(scores, dtype=float)
    return score


def to_severity(scores, training_scores):
    """Training-percentile of each score and its severity, using the same cut-offs as log-MAD."""
    reference = np.sort(training_scores)
    percentile = np.searchsorted(reference, scores, side="right") / len(reference)
    severity = np.full(len(scores), None, dtype=object)
    for cutoff, level in SEVERITY_LEVELS:
        severity[percentile >= cutoff] = level
    return percentile, severity


def synthetic_times(mad_scores):
    """The 40 hours log-MAD's synthetic evaluation modifies (seed 42; 20 x5 then 20 x0.2)."""
    eligible = mad_scores.index[mad_scores["anomaly_score"].notna() & mad_scores["severity"].isna()]
    rng = np.random.default_rng(42)
    selected = pd.DatetimeIndex(np.sort(rng.choice(eligible.to_numpy(), size=40, replace=False)))
    return selected[::2], selected[1::2]


def compare(consumption, score):
    """Score RCF and log-MAD on the same validation hours; return (summary dict, RCF scores frame).

    `score` maps an (n, feature_dim) array of shingles to n RCF scores (endpoint or fake in tests).
    """
    shingles = build_shingles(consumption)
    train_shingles = shingles.loc[:TRAIN_END]
    validation_shingles = shingles.loc[VALIDATION_START:VALIDATION_END]

    training_scores = score(train_shingles.to_numpy())
    validation_scores = score(validation_shingles.to_numpy())
    percentile, severity = to_severity(validation_scores, training_scores)
    rcf = pd.DataFrame(
        {"score": validation_scores, "percentile": percentile, "severity": severity},
        index=validation_shingles.index,
    )

    detector = GlobalLogMADDetector().fit(consumption.loc[:TRAIN_END])
    validation = consumption.loc[VALIDATION_START:VALIDATION_END]
    mad = detector.score(validation).set_index("timestamp")

    # Compare only hours both methods can score (RCF drops hours within 24 h after a gap).
    common = rcf.index.intersection(mad.index[mad["anomaly_score"].notna()])
    rcf_alerts = set(common[rcf.loc[common, "severity"].notna()])
    mad_alerts = set(common[mad.loc[common, "severity"].notna()])

    def counts(levels):
        return {level: int((levels == level).sum()) for _, level in SEVERITY_LEVELS}

    summary = {
        "hours_compared": len(common),
        "rcf_alerts": len(rcf_alerts),
        "rcf_by_severity": counts(rcf.loc[common, "severity"]),
        "log_mad_alerts": len(mad_alerts),
        "log_mad_by_severity": counts(mad.loc[common, "severity"]),
        "overlap": len(rcf_alerts & mad_alerts),
        "test_period_evaluated": False,
        "synthetic": {},
    }

    # Same 40 modified hours as ml/anomaly/run_synthetic.py; RCF scores the window ending at each.
    high_times, low_times = synthetic_times(mad)
    modified = consumption.copy()
    modified.loc[high_times] *= 5.0
    modified.loc[low_times] *= 0.2
    modified_shingles = build_shingles(modified)
    mad_after = detector.score(modified.loc[VALIDATION_START:VALIDATION_END]).set_index("timestamp")

    for name, times in [("high_x5", high_times), ("low_x0_2", low_times)]:
        scoreable = times.intersection(modified_shingles.index)
        _, rcf_severity = to_severity(score(modified_shingles.loc[scoreable].to_numpy()), training_scores)
        summary["synthetic"][name] = {
            "injected": len(times),
            "rcf_scoreable": len(scoreable),
            "rcf_detected": int(pd.notna(rcf_severity).sum()),
            "log_mad_detected": int(mad_after.loc[times, "severity"].notna().sum()),
        }

    return summary, rcf


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    train_cmd = commands.add_parser("train")
    train_cmd.add_argument("--bucket", required=True)
    train_cmd.add_argument("--role-arn", required=True)
    train_cmd.add_argument("--image-uri", required=True)

    compare_cmd = commands.add_parser("compare")
    compare_cmd.add_argument("--gold", required=True)
    compare_cmd.add_argument("--model-data", required=True)
    compare_cmd.add_argument("--role-arn", required=True)
    compare_cmd.add_argument("--image-uri", required=True)
    compare_cmd.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()

    import boto3

    sagemaker = boto3.client("sagemaker")
    if args.command == "train":
        job = train(sagemaker, args.bucket, args.role_arn, args.image_uri)
        print("Status:", job["TrainingJobStatus"], job.get("FailureReason", ""))
        print("Billable seconds:", job.get("BillableTimeInSeconds"))
        print("Model:", job.get("ModelArtifacts", {}).get("S3ModelArtifacts"))
        return

    consumption = load_hourly_consumption(args.gold)
    name = f"greentrack-rcf-{time.strftime('%Y%m%d-%H%M%S')}"
    with temporary_endpoint(sagemaker, name, args.image_uri, args.model_data, args.role_arn):
        summary, rcf = compare(consumption, endpoint_scorer(boto3.client("sagemaker-runtime"), name))

    args.output.mkdir(parents=True, exist_ok=True)
    rcf.to_csv(args.output / "rcf_validation_scores.csv", index_label="timestamp")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
