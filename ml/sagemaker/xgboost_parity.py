"""Train XGBoost on SageMaker and check it reproduces the locally validated model (parity).

Two commands:
    train     start a SageMaker training job on xgboost/train/ in the ML bucket and wait for it
    evaluate  score the frozen validation window with the downloaded model and compare RMSE

Variables:
    VALIDATION_RMSE_LOCAL - frozen local XGBoost validation RMSE (kWh)
    PARITY_TOLERANCE_KWH  - accepted |RMSE difference|, fixed before running (different XGBoost versions)
    MODEL_COLUMNS         - prediction columns compared by forecast_error_metrics

Usage:
    python -m ml.sagemaker.xgboost_parity train --bucket B --role-arn R --image-uri I
    python -m ml.sagemaker.xgboost_parity evaluate --gold gold.parquet --model xgboost-model.json
"""

import argparse
import time

import numpy as np
import xgboost as xgb

from ml.forecasting.evaluation import rolling_baseline_predictions
from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.input_data import load_hourly_consumption
from ml.forecasting.metrics import forecast_error_metrics
from ml.forecasting.run_xgboost_validation import VALIDATION_END, VALIDATION_START
from ml.forecasting.xgboost_evaluation import add_xgboost_predictions
from ml.sagemaker.prepare_xgboost_data import HYPERPARAMETERS

VALIDATION_RMSE_LOCAL = 0.6232
PARITY_TOLERANCE_KWH = 0.01
MODEL_COLUMNS = {"daily": "daily_pred_kwh", "weekly": "weekly_pred_kwh", "xgboost": "xgboost_pred_kwh"}


def training_job_request(job_name, bucket, role_arn, image_uri, instance_type="ml.m5.large"):
    """CreateTrainingJob parameters for the built-in XGBoost container (CSV, target first)."""
    return {
        "TrainingJobName": job_name,
        "AlgorithmSpecification": {"TrainingImage": image_uri, "TrainingInputMode": "File"},
        "RoleArn": role_arn,
        "InputDataConfig": [{
            "ChannelName": "train",
            "ContentType": "text/csv",
            "DataSource": {"S3DataSource": {
                "S3DataType": "S3Prefix",
                "S3Uri": f"s3://{bucket}/xgboost/train/",
                "S3DataDistributionType": "FullyReplicated",
            }},
        }],
        "OutputDataConfig": {"S3OutputPath": f"s3://{bucket}/xgboost/models/"},
        "ResourceConfig": {"InstanceType": instance_type, "InstanceCount": 1, "VolumeSizeInGB": 5},
        # Hard stop so a stuck job cannot keep billing.
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "HyperParameters": HYPERPARAMETERS,
    }


def train(sagemaker_client, bucket, role_arn, image_uri):
    """Start the training job, wait until it ends, and return its description."""
    job_name = f"greentrack-xgboost-{time.strftime('%Y%m%d-%H%M%S')}"
    sagemaker_client.create_training_job(**training_job_request(job_name, bucket, role_arn, image_uri))
    print(f"Started {job_name}; waiting (usually 3-5 minutes)...")
    sagemaker_client.get_waiter("training_job_completed_or_stopped").wait(TrainingJobName=job_name)
    return sagemaker_client.describe_training_job(TrainingJobName=job_name)


class BoosterModel:
    """Gives a raw xgboost.Booster the .predict(DataFrame) interface used by add_xgboost_predictions.

    The built-in container was trained on unnamed CSV columns, so features are passed
    positionally in FEATURE_COLUMNS order; NaN stays a missing value.
    """

    def __init__(self, booster):
        self.booster = booster

    def predict(self, features):
        values = features[FEATURE_COLUMNS].to_numpy(dtype=float)
        return self.booster.predict(xgb.DMatrix(values, missing=np.nan))


def evaluate(gold_path, model_path):
    """Score the frozen validation window and return (overall metrics, predictions)."""
    booster = xgb.Booster()
    booster.load_model(model_path)

    consumption = load_hourly_consumption(gold_path)
    baseline, _ = rolling_baseline_predictions(consumption, VALIDATION_START, VALIDATION_END)
    predictions = add_xgboost_predictions(BoosterModel(booster), consumption, baseline)
    _, overall = forecast_error_metrics(predictions, MODEL_COLUMNS)
    return overall, predictions


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    train_cmd = commands.add_parser("train")
    train_cmd.add_argument("--bucket", required=True)
    train_cmd.add_argument("--role-arn", required=True)
    train_cmd.add_argument("--image-uri", required=True)

    eval_cmd = commands.add_parser("evaluate")
    eval_cmd.add_argument("--gold", required=True)
    eval_cmd.add_argument("--model", required=True)

    args = parser.parse_args()

    if args.command == "train":
        import boto3

        job = train(boto3.client("sagemaker"), args.bucket, args.role_arn, args.image_uri)
        print("Status:", job["TrainingJobStatus"], job.get("FailureReason", ""))
        print("Billable seconds:", job.get("BillableTimeInSeconds"))
        print("Model:", job.get("ModelArtifacts", {}).get("S3ModelArtifacts"))
        return

    overall, predictions = evaluate(args.gold, args.model)
    print(f"Validation hours: {len(predictions)}")
    print(overall.round(4).to_string(index=False))

    rmse = overall.set_index("model").loc["xgboost", "rmse_kwh"]
    diff = rmse - VALIDATION_RMSE_LOCAL
    verdict = "PASS" if abs(diff) <= PARITY_TOLERANCE_KWH else "FAIL"
    print(f"\nSageMaker RMSE {rmse:.4f} vs local {VALIDATION_RMSE_LOCAL:.4f} "
          f"(diff {diff:+.4f}, tolerance {PARITY_TOLERANCE_KWH}): {verdict}")


if __name__ == "__main__":
    main()
