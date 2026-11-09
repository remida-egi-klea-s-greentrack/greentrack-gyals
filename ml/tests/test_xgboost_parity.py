"""Tests for the SageMaker XGBoost parity helpers, without AWS.

Variables: stubbed SageMaker client (botocore Stubber) and a tiny locally trained booster.
"""

import boto3
import numpy as np
import pandas as pd
import xgboost as xgb
from botocore.stub import ANY, Stubber

from ml.forecasting.features import FEATURE_COLUMNS
from ml.sagemaker.prepare_xgboost_data import HYPERPARAMETERS
from ml.sagemaker.xgboost_parity import BoosterModel, train, training_job_request

ROLE = "arn:aws:iam::123456789012:role/test-sagemaker-exec"
IMAGE = "662702820516.dkr.ecr.eu-north-1.amazonaws.com/sagemaker-xgboost:1.7-1"


def test_request_uses_csv_channel_and_frozen_hyperparameters():
    request = training_job_request("job", "my-bucket", "arn:role", "image:1.7-1")

    channel = request["InputDataConfig"][0]
    assert channel["ContentType"] == "text/csv"
    assert channel["DataSource"]["S3DataSource"]["S3Uri"] == "s3://my-bucket/xgboost/train/"
    assert request["OutputDataConfig"]["S3OutputPath"] == "s3://my-bucket/xgboost/models/"
    assert request["HyperParameters"] == HYPERPARAMETERS
    assert request["StoppingCondition"]["MaxRuntimeInSeconds"] <= 3600


def test_train_sends_request_and_returns_job_description():
    client = boto3.client("sagemaker", region_name="eu-north-1",
                          aws_access_key_id="x", aws_secret_access_key="x")
    stubber = Stubber(client)
    stubber.add_response("create_training_job", {"TrainingJobArn": "arn:aws:sagemaker:eu-north-1:123456789012:training-job/j"},
                         {**training_job_request(ANY, "b", ROLE, IMAGE), "TrainingJobName": ANY})
    description = {
        "TrainingJobName": "j", "TrainingJobArn": "arn:aws:sagemaker:eu-north-1:123456789012:training-job/j", "TrainingJobStatus": "Completed",
        "SecondaryStatus": "Completed", "AlgorithmSpecification": {"TrainingInputMode": "File"},
        "ModelArtifacts": {"S3ModelArtifacts": "s3://b/xgboost/models/j/output/model.tar.gz"},
        "ResourceConfig": {"InstanceType": "ml.m5.large", "InstanceCount": 1, "VolumeSizeInGB": 5},
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "CreationTime": "2026-01-01T00:00:00Z",
    }
    # The waiter polls describe_training_job once (already Completed), then train() describes again.
    stubber.add_response("describe_training_job", description, {"TrainingJobName": ANY})
    stubber.add_response("describe_training_job", description, {"TrainingJobName": ANY})

    with stubber:
        job = train(client, "b", ROLE, IMAGE)

    assert job["TrainingJobStatus"] == "Completed"
    stubber.assert_no_pending_responses()


def test_booster_model_uses_feature_order_and_keeps_missing_values():
    rng = np.random.default_rng(0)
    X = rng.random((200, len(FEATURE_COLUMNS)))
    booster = xgb.train({"objective": "reg:squarederror"}, xgb.DMatrix(X, label=X[:, 3]), 20)

    features = pd.DataFrame(X[:5], columns=FEATURE_COLUMNS)
    features.loc[0, "lag_24h_kwh"] = np.nan
    shuffled = features[list(reversed(FEATURE_COLUMNS))]  # column order must not matter

    predictions = BoosterModel(booster).predict(shuffled)

    assert predictions.shape == (5,)
    assert np.isfinite(predictions).all()
    expected = booster.predict(xgb.DMatrix(features[FEATURE_COLUMNS].to_numpy(dtype=float)))
    np.testing.assert_allclose(predictions, expected)
