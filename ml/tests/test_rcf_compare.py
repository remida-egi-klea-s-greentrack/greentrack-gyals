"""Tests for the RCF comparison helpers, without AWS.

Variables: stubbed SageMaker client (botocore Stubber), a fake runtime client, a fake RCF score
function, and a synthetic noisy hourly series long enough to fit log-MAD.
"""

import io
import json

import boto3
import numpy as np
import pandas as pd
import pytest
from botocore.stub import Stubber

from ml.sagemaker.rcf_compare import compare, endpoint_scorer, temporary_endpoint, to_severity

ARN = "arn:aws:sagemaker:eu-north-1:123456789012:{}/x"
ROLE = "arn:aws:iam::123456789012:role/test-sagemaker-exec"
IMAGE = "669576153137.dkr.ecr.eu-north-1.amazonaws.com/randomcutforest:1"


def test_severity_uses_training_percentiles_like_log_mad():
    training = np.arange(1000, dtype=float)
    percentile, severity = to_severity(np.array([989.0, 994.0, 999.0, 5.0]), training)

    np.testing.assert_allclose(percentile, [0.99, 0.995, 1.0, 0.006])
    assert list(severity) == ["low", "medium", "high", None]


def test_endpoint_is_deleted_even_when_scoring_fails():
    client = boto3.client("sagemaker", region_name="eu-north-1",
                          aws_access_key_id="x", aws_secret_access_key="x")
    stubber = Stubber(client)
    stubber.add_response("create_model", {"ModelArn": ARN.format("model")})
    stubber.add_response("create_endpoint_config", {"EndpointConfigArn": ARN.format("endpoint-config")})
    stubber.add_response("create_endpoint", {"EndpointArn": ARN.format("endpoint")})
    stubber.add_response("describe_endpoint", {
        "EndpointName": "x", "EndpointArn": ARN.format("endpoint"), "EndpointConfigName": "x",
        "EndpointStatus": "InService", "CreationTime": "2026-01-01T00:00:00Z",
        "LastModifiedTime": "2026-01-01T00:00:00Z",
    })
    stubber.add_response("delete_endpoint", {}, {"EndpointName": "x"})
    stubber.add_response("delete_endpoint_config", {}, {"EndpointConfigName": "x"})
    stubber.add_response("delete_model", {}, {"ModelName": "x"})

    with stubber, pytest.raises(RuntimeError):
        with temporary_endpoint(client, "x", IMAGE, "s3://b/rcf/models/model.tar.gz", ROLE):
            raise RuntimeError("scoring failed")

    stubber.assert_no_pending_responses()


class FakeRuntime:
    """Answers InvokeEndpoint like RCF: one score per CSV line (here: the line's last value)."""

    def __init__(self):
        self.calls = 0

    def invoke_endpoint(self, EndpointName, ContentType, Accept, Body):
        self.calls += 1
        assert ContentType == "text/csv" and Accept == "application/json"
        scores = [{"score": float(line.split(",")[-1])} for line in Body.split("\n")]
        return {"Body": io.BytesIO(json.dumps({"scores": scores}).encode())}


def test_scorer_batches_and_keeps_order():
    runtime = FakeRuntime()
    records = np.arange(1200 * 3, dtype=float).reshape(1200, 3)

    scores = endpoint_scorer(runtime, "x", batch_size=500)(records)

    assert runtime.calls == 3
    np.testing.assert_allclose(scores, records[:, -1], atol=1e-6)


def test_compare_reports_both_methods_on_common_hours():
    hours = pd.date_range("2009-01-01", "2010-05-31 23:00", freq="h")
    rng = np.random.default_rng(1)
    consumption = pd.Series(np.exp(rng.normal(0.0, 0.3, len(hours))), index=hours)

    # Fake RCF: how far the newest hour is from the window's mean (spikes score high).
    def fake_score(records):
        return np.abs(records[:, -1] - records.mean(axis=1))

    summary, rcf = compare(consumption, fake_score)

    assert summary["test_period_evaluated"] is False
    assert summary["hours_compared"] == len(rcf)
    assert summary["synthetic"]["high_x5"]["injected"] == 20
    assert summary["synthetic"]["high_x5"]["rcf_detected"] > 0
    assert rcf.index.min() >= pd.Timestamp("2010-01-01")
