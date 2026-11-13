"""Train SageMaker Random Cut Forest and run the confirmation test against log-MAD.

Two commands:
    train    start an RCF training job on rcf/train/ (FIT period, data through 2008) and wait for it
    compare  deploy a temporary endpoint, score calibration (2009) + validation (Jan-May 2010) shingles
             and the injected test windows, delete the endpoint, then evaluate the confirmation rule

Both detectors use the same scheme: fitted on FIT, thresholds from their own 2009 scores (out of
sample), evaluated on validation. log-MAD here is fitted on FIT only for a like-for-like comparison;
the production log-MAD detector is not changed. One SageMaker model is scored, so the 10 seeds vary
the injection positions only.

Confirmation rule (written before the SageMaker run, 11 Nov 2026), all must hold:
    1. RCF validation alerts > 0 and <= 2 x log-MAD validation alerts
    2. on busy-slot x3 spikes, RCF recall beats log-MAD in >= 7 of 10 seeds
    3. RCF or log-MAD together catch more busy-slot x3 spikes than log-MAD alone

Variables:
    HYPERPARAMETERS - RCF settings (feature_dim = shingle length; trees/samples at RCF defaults)
    SEVERITY_LEVELS - calibration-percentile cut-offs, identical for both detectors (0.99 / 0.995 / 0.999)
    BATCH_SIZE      - records per InvokeEndpoint call (well under the 6 MB payload limit)
    INJECTIONS      - injection type -> (hours, multiplier, load stratum of the first hour)
    CONTEXT_HOURS   - fully observed, alert-free hours required before an injection (covers a 24 h window)
    AFTER_HOURS     - alert-free hours required after an injection
    N_SEEDS, N_PER_TYPE - injection draws: 10 seeds x 20 per type

Usage:
    python -m ml.sagemaker.rcf_compare train --bucket B --role-arn R --image-uri I
    python -m ml.sagemaker.rcf_compare compare --gold gold.parquet --model-data s3://.../model.tar.gz \
        --role-arn R --image-uri I --output out_dir
"""

import argparse
import json
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly.global_log_mad import GlobalLogMADDetector
from ml.forecasting.input_data import load_hourly_consumption
from ml.sagemaker.aws_names import TAGS, resource_name
from ml.sagemaker.prepare_rcf_data import (
    CALIBRATION_END,
    CALIBRATION_START,
    FIT_END,
    SHINGLE_HOURS,
    VALIDATION_END,
    VALIDATION_START,
    build_shingles,
    split_shingles,
)

HYPERPARAMETERS = {"feature_dim": str(SHINGLE_HOURS), "num_trees": "100", "num_samples_per_tree": "256"}
SEVERITY_LEVELS = [(0.99, "low"), (0.995, "medium"), (0.999, "high")]
BATCH_SIZE = 500
INJECTIONS = {
    "spike_low_x5": (1, 5.0, "low"),
    "spike_high_x3": (1, 3.0, "high"),
    "dip_high_x0.2": (1, 0.2, "high"),
    "sustained_6h_x2": (6, 2.0, "any"),
    "dropout_6h_x0.25": (6, 0.25, "high"),
}
CONTEXT_HOURS = 30
AFTER_HOURS = 11
N_SEEDS = 10
N_PER_TYPE = 20


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
        "Tags": TAGS,
    }


def train(sagemaker_client, bucket, role_arn, image_uri):
    """Start the RCF training job, wait until it ends, and return its description."""
    job_name = resource_name("rcf")
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
            Tags=TAGS,
        )
        sagemaker_client.create_endpoint_config(
            EndpointConfigName=name,
            ProductionVariants=[{
                "VariantName": "AllTraffic",
                "ModelName": name,
                "InstanceType": instance_type,
                "InitialInstanceCount": 1,
            }],
            Tags=TAGS,
        )
        sagemaker_client.create_endpoint(EndpointName=name, EndpointConfigName=name, Tags=TAGS)
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


def to_severity(scores, reference_scores):
    """Percentile of each score within the reference (calibration) scores, and its severity."""
    reference = np.sort(reference_scores)
    percentile = np.searchsorted(reference, scores, side="right") / len(reference)
    severity = np.full(len(scores), None, dtype=object)
    for cutoff, level in SEVERITY_LEVELS:
        severity[percentile >= cutoff] = level
    return percentile, severity


def is_alert(scores, reference_scores):
    """True where a score reaches the lowest severity cut-off of the reference distribution."""
    percentile, _ = to_severity(scores, reference_scores)
    return percentile >= SEVERITY_LEVELS[0][0]


def abs_robust_z(detector, consumption):
    """|robust z| per observed hour from a fitted log-MAD detector (missing hours dropped)."""
    return detector.score(consumption).set_index("timestamp")["robust_z"].abs().dropna()


def candidate_starts(consumption, alert, hours, slots):
    """Validation starts whose context + event + after hours are fully observed and alert-free.

    consumption and alert share one gap-free hourly index; slots = allowed hour-of-week of the start.
    """
    bad = (consumption.isna() | alert).to_numpy()
    cumulative = np.concatenate([[0], np.cumsum(bad)])
    index = consumption.index
    position = np.arange(len(index))
    low = position - CONTEXT_HOURS
    high = position + hours - 1 + AFTER_HOURS
    inside = (low >= 0) & (high < len(index)) & (index >= pd.Timestamp(VALIDATION_START))
    clean = np.zeros(len(index), dtype=bool)
    clean[inside] = cumulative[high[inside] + 1] - cumulative[low[inside]] == 0
    in_slots = np.isin(index.day_of_week * 24 + index.hour, list(slots))
    return index[clean & in_slots]


def compare(consumption, score):
    """Run the confirmation test; return (summary dict, validation RCF scores, one row per injection).

    `score` maps an (n, feature_dim) array of shingles to n RCF scores (endpoint or fake in tests).
    """
    consumption = consumption.loc[:VALIDATION_END]
    parts = split_shingles(consumption)

    # RCF: thresholds from 2009 scores
    rcf_reference = score(parts["calibration"].to_numpy())
    validation_scores = score(parts["validation"].to_numpy())
    percentile, severity = to_severity(validation_scores, rcf_reference)
    rcf = pd.DataFrame(
        {"score": validation_scores, "percentile": percentile, "severity": severity},
        index=parts["validation"].index,
    )

    # log-MAD under the same scheme: fitted on FIT, thresholds from 2009 |z|
    detector = GlobalLogMADDetector().fit(consumption.loc[:FIT_END])
    mad_reference = abs_robust_z(detector, consumption.loc[CALIBRATION_START:CALIBRATION_END]).to_numpy()
    scored = consumption.loc[CALIBRATION_START:VALIDATION_END]
    mad_z = abs_robust_z(detector, scored)

    # Baseline alerts over 2009 + validation (the context of early-January injections lies in 2009)
    rcf_scores = np.concatenate([rcf_reference, validation_scores])
    rcf_index = parts["calibration"].index.append(parts["validation"].index)
    rcf_alert = pd.Series(is_alert(rcf_scores, rcf_reference), index=rcf_index).reindex(scored.index, fill_value=False)
    mad_alert = pd.Series(is_alert(mad_z.to_numpy(), mad_reference), index=mad_z.index).reindex(scored.index, fill_value=False)
    validation_hours = slice(VALIDATION_START, VALIDATION_END)

    # Load strata: hour-of-week slots by typical kWh over FIT
    typical = np.exp(detector.medians_)
    strata = {
        "low": typical.index[typical <= typical.quantile(1 / 3)],
        "high": typical.index[typical >= typical.quantile(2 / 3)],
        "any": typical.index,
    }

    pools = {}
    for kind, (hours, _, stratum) in INJECTIONS.items():
        pools[kind] = candidate_starts(scored, rcf_alert | mad_alert, hours, strata[stratum])
        if len(pools[kind]) < N_PER_TYPE:
            raise ValueError(f"Only {len(pools[kind])} clean starts for {kind}")

    # Draw injections; collect every RCF window that ends during an injection for one batched scoring pass
    cases, windows, owners = [], [], []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        for kind, (hours, multiplier, _) in INJECTIONS.items():
            for start in pd.DatetimeIndex(np.sort(rng.choice(pools[kind].to_numpy(), size=N_PER_TYPE, replace=False))):
                end = start + pd.Timedelta(hours=hours - 1)
                local = consumption.loc[start - pd.Timedelta(hours=CONTEXT_HOURS):end].copy()
                local.loc[start:end] *= multiplier
                event_windows = build_shingles(local).loc[start:end].to_numpy()
                windows.append(event_windows)
                owners.extend([len(cases)] * len(event_windows))
                mad_hit = is_alert(abs_robust_z(detector, local.loc[start:end]).to_numpy(), mad_reference).any()
                cases.append({"seed": seed, "type": kind, "start": start, "log_mad": bool(mad_hit)})

    injected_alert = is_alert(score(np.concatenate(windows)), rcf_reference)
    rcf_hit = pd.Series(injected_alert).groupby(np.asarray(owners)).any()
    injections = pd.DataFrame(cases)
    injections["rcf"] = rcf_hit.reindex(injections.index, fill_value=False).to_numpy()
    injections["either"] = injections["log_mad"] | injections["rcf"]

    summary = summarise(injections, rcf_alert.loc[validation_hours], mad_alert.loc[validation_hours])
    summary["validation_hours_scored"] = {"rcf": len(rcf), "log_mad": int(mad_z.loc[validation_hours].size)}
    return summary, rcf, injections


def summarise(injections, rcf_alert, mad_alert):
    """Alert counts, recall per type (mean and per seed), paired differences and the confirmation rule."""
    per_seed = injections.groupby(["type", "seed"])[["log_mad", "rcf", "either"]].mean() * 100
    recall = {}
    for kind in INJECTIONS:
        rows = per_seed.loc[kind]
        difference = rows["rcf"] - rows["log_mad"]
        recall[kind] = {
            **{name: round(float(rows[name].mean()), 1) for name in ["log_mad", "rcf", "either"]},
            "rcf_minus_log_mad_per_seed": [round(float(value), 1) for value in difference],
            "rcf_better_seeds": int((difference > 0).sum()),
            "rcf_worse_seeds": int((difference < 0).sum()),
        }

    alerts = {"rcf": int(rcf_alert.sum()), "log_mad": int(mad_alert.sum()), "either": int((rcf_alert | mad_alert).sum())}
    busy = recall["spike_high_x3"]
    rule = {
        "1_alert_burden": 0 < alerts["rcf"] <= 2 * alerts["log_mad"],
        "2_busy_spikes_seeds": busy["rcf_better_seeds"] >= 7,
        "3_union_adds": busy["either"] > busy["log_mad"],
    }
    rule["passed"] = all(rule.values())
    return {
        "periods": {"fit_end": FIT_END, "calibration": [CALIBRATION_START, CALIBRATION_END],
                    "validation": [VALIDATION_START, VALIDATION_END]},
        "test_period_evaluated": False,
        "validation_alerts": alerts,
        "injections_per_type": N_SEEDS * N_PER_TYPE,
        "recall_percent": recall,
        "confirmation_rule": rule,
    }


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
    name = resource_name("rcf")
    with temporary_endpoint(sagemaker, name, args.image_uri, args.model_data, args.role_arn):
        summary, rcf, injections = compare(consumption, endpoint_scorer(boto3.client("sagemaker-runtime"), name))

    args.output.mkdir(parents=True, exist_ok=True)
    rcf.to_csv(args.output / "rcf_validation_scores.csv", index_label="timestamp")
    injections.to_csv(args.output / "injections.csv", index=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
