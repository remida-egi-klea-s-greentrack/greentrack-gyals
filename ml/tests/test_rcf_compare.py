"""Tests for the RCF confirmation test, without AWS.

Variables: stubbed SageMaker client (botocore Stubber), a fake runtime client, a fake RCF score
function (distance of the newest hour from its window mean), and synthetic hourly series where
2008 is noisier than 2009-2010 (the calibration shift seen in the real data).
"""

import io
import json

import boto3
import numpy as np
import pandas as pd
import pytest
from botocore.stub import ANY, Stubber

from ml.sagemaker.aws_names import TAGS
from ml.sagemaker.rcf_compare import (
    INJECTIONS,
    N_PER_TYPE,
    N_SEEDS,
    candidate_starts,
    compare,
    endpoint_scorer,
    summarise,
    temporary_endpoint,
    to_severity,
)

ARN = "arn:aws:sagemaker:eu-north-1:123456789012:{}/x"
ROLE = "arn:aws:iam::123456789012:role/test-sagemaker-exec"
IMAGE = "669576153137.dkr.ecr.eu-north-1.amazonaws.com/randomcutforest:1"


def test_severity_uses_reference_percentiles_like_log_mad():
    reference = np.arange(1000, dtype=float)
    percentile, severity = to_severity(np.array([989.0, 994.0, 999.0, 5.0]), reference)

    np.testing.assert_allclose(percentile, [0.99, 0.995, 1.0, 0.006])
    assert list(severity) == ["low", "medium", "high", None]


def test_endpoint_is_deleted_even_when_scoring_fails():
    client = boto3.client("sagemaker", region_name="eu-north-1",
                          aws_access_key_id="x", aws_secret_access_key="x")
    stubber = Stubber(client)
    # Every resource created in the shared account must carry the group tags.
    stubber.add_response("create_model", {"ModelArn": ARN.format("model")},
                         {"ModelName": "x", "PrimaryContainer": ANY, "ExecutionRoleArn": ROLE, "Tags": TAGS})
    stubber.add_response("create_endpoint_config", {"EndpointConfigArn": ARN.format("endpoint-config")},
                         {"EndpointConfigName": "x", "ProductionVariants": ANY, "Tags": TAGS})
    stubber.add_response("create_endpoint", {"EndpointArn": ARN.format("endpoint")},
                         {"EndpointName": "x", "EndpointConfigName": "x", "Tags": TAGS})
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


def noisy_then_calm(end="2010-05-31 23:00", seed=1):
    """Hourly kWh with a daily pattern; log noise sd 0.8 through 2008, 0.3 afterwards."""
    hours = pd.date_range("2008-03-01", end, freq="h")
    rng = np.random.default_rng(seed)
    sd = np.where(hours <= pd.Timestamp("2008-12-31 23:00"), 0.8, 0.3)
    daily = 1.0 + 0.8 * (hours.hour >= 18)
    return pd.Series(daily * np.exp(rng.normal(0.0, sd)), index=hours)


def fake_score(records):
    """Fake RCF: how far the newest hour is from its window's mean (spikes score high)."""
    return np.abs(records[:, -1] - records.mean(axis=1))


@pytest.fixture(scope="module")
def result():
    return compare(noisy_then_calm(), fake_score)


def test_thresholds_come_from_2009_so_calm_validation_still_alerts(result):
    # With thresholds from the noisy FIT period both detectors would stay almost silent here.
    summary, rcf, _ = result
    assert summary["validation_alerts"]["rcf"] > 0
    assert summary["validation_alerts"]["log_mad"] > 0
    assert rcf.index.min() >= pd.Timestamp("2010-01-01") and rcf.index.max() <= pd.Timestamp("2010-05-31 23:00")


def test_injections_and_summary_shape(result):
    summary, _, injections = result
    assert len(injections) == len(INJECTIONS) * N_SEEDS * N_PER_TYPE
    assert injections["start"].min() >= pd.Timestamp("2010-01-01")
    assert summary["test_period_evaluated"] is False
    assert set(summary["recall_percent"]) == set(INJECTIONS)
    assert set(summary["confirmation_rule"]) == {"1_alert_burden", "2_busy_spikes_seeds", "3_union_adds", "passed"}
    assert summary["recall_percent"]["spike_low_x5"]["log_mad"] > 0


def test_hours_after_validation_are_never_read(result):
    longer = noisy_then_calm(end="2010-11-26 21:00")
    longer.loc["2010-06-01":] *= 50.0
    summary, _, injections = compare(longer, fake_score)
    assert summary == result[0]
    pd.testing.assert_frame_equal(injections, result[2])


def test_candidates_need_clean_observed_context_event_and_after():
    hours = pd.date_range("2009-12-30 00:00", "2010-01-04 23:00", freq="h")
    consumption = pd.Series(1.0, index=hours)
    alert = pd.Series(False, index=hours)
    all_slots = range(168)

    clean = candidate_starts(consumption, alert, 1, all_slots)
    assert clean.min() == pd.Timestamp("2010-01-01 00:00")   # validation starts only
    assert clean.max() == hours[-1] - pd.Timedelta(hours=11)  # room for the after hours

    alert.loc["2010-01-02 10:00"] = True                      # inside the 30 h context of 2010-01-03 12:00
    consumption.loc["2010-01-01 05:00"] = np.nan              # missing hour
    starts = candidate_starts(consumption, alert, 1, all_slots)
    assert pd.Timestamp("2010-01-03 16:00") not in starts     # context starts exactly at the alert hour
    assert pd.Timestamp("2010-01-03 17:00") in starts         # first start whose context is after it
    assert pd.Timestamp("2010-01-01 05:00") not in starts
    assert not set(candidate_starts(consumption, alert, 1, [0])).difference(
        starts[starts.day_of_week * 24 + starts.hour == 0])


def test_confirmation_rule():
    rows = []
    for seed in range(N_SEEDS):
        for kind in INJECTIONS:
            # busy-slot spikes: RCF catches one more case than log-MAD in 7 seeds
            rcf_extra = kind == "spike_high_x3" and seed < 7
            rows += [{"seed": seed, "type": kind, "log_mad": False, "rcf": rcf_extra and i == 0}
                     for i in range(N_PER_TYPE)]
    injections = pd.DataFrame(rows)
    injections["either"] = injections["log_mad"] | injections["rcf"]
    hours = pd.date_range("2010-01-01", periods=100, freq="h")
    mad_alert = pd.Series(np.arange(100) < 10, index=hours)

    rcf_alert = pd.Series(np.arange(100) < 5, index=hours)
    assert summarise(injections, rcf_alert, mad_alert)["confirmation_rule"]["passed"] is True

    silent = pd.Series(False, index=hours)
    rule = summarise(injections, silent, mad_alert)["confirmation_rule"]
    assert rule["1_alert_burden"] is False and rule["passed"] is False

    noisy = pd.Series(True, index=hours)
    assert summarise(injections, noisy, mad_alert)["confirmation_rule"]["1_alert_burden"] is False
