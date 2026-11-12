"""Tests for the inference Lambda, without AWS.

Variables: synthetic hourly series with gaps (dict for the Lambda, pandas Series for the ML-03
reference code), botocore Stubber for Athena, fake SageMaker runtime / S3 clients, and params
built from a fitted GlobalLogMADDetector.
"""

import io
import json
from datetime import datetime, timedelta, timezone

import boto3
import numpy as np
import pandas as pd
import pytest
from botocore.stub import Stubber

from ml.anomaly.global_log_mad import GlobalLogMADDetector
from ml.forecasting.features import FEATURE_COLUMNS, build_forecast_features
from ml.inference import aws, core, handler

FIRST = datetime(2010, 1, 1)


def series(days=30, missing=()):
    """Positive hourly kWh with a daily pattern; `missing` hours are NaN (incomplete)."""
    index = pd.date_range(FIRST, periods=days * 24, freq="h")
    rng = np.random.default_rng(3)
    values = (0.5 + 1.5 * (index.hour >= 18)) * np.exp(rng.normal(0, 0.3, len(index)))
    s = pd.Series(values, index=index)
    s.loc[list(missing)] = np.nan
    return s


def as_hours(s):
    return {t.to_pydatetime(): (None if np.isnan(v) else float(v)) for t, v in s.items()}


# ---------- window ----------

@pytest.mark.parametrize("event, message", [
    ({}, "Expected"),
    ({"start": "2010-01-10T00:00:00+00:00", "end": "2010-01-11T00:00:00"}, "timezone-naive"),
    ({"start": "2010-01-10T05:00:00", "end": "2010-01-11T00:00:00"}, "midnights"),
    ({"start": "2010-01-10T00:00:00", "end": "2010-01-18T00:00:00"}, "at most 7 days"),
    ({"start": "2010-01-05T00:00:00", "end": "2010-01-06T00:00:00"}, "7 days of history"),
    ({"start": "2010-01-29T00:00:00", "end": "2010-02-01T00:00:00"}, "after the last"),
])
def test_window_rejections(event, message):
    with pytest.raises(ValueError, match=message):
        core.parse_window(event, FIRST, datetime(2010, 1, 30, 23))


def test_window_accepts_first_day_with_full_history():
    window = core.parse_window({"start": "2010-01-08T00:00:00", "end": "2010-01-15T00:00:00"}, FIRST, datetime(2010, 1, 30, 23))
    assert window == (datetime(2010, 1, 8), datetime(2010, 1, 15))


# ---------- forecast features: parity with ML-03 ----------

@pytest.mark.parametrize("missing", [(), ("2010-01-14 05:00", "2010-01-08 20:00", "2010-01-16 23:00")])
def test_forecast_rows_match_ml03_features(missing):
    s = series(missing=missing)
    hours = as_hours(s)
    for day in pd.date_range("2010-01-15", "2010-01-18"):
        expected = build_forecast_features(s, day)[FEATURE_COLUMNS].to_numpy(dtype=float)
        rows = core.forecast_rows(hours, day.to_pydatetime())
        got = np.array([[np.nan if v is None else v for v in row] for row in rows], dtype=float)
        np.testing.assert_allclose(got, expected, equal_nan=True)


def test_forecast_rows_ignore_hours_after_origin():
    s = series()
    day = datetime(2010, 1, 15)
    changed = as_hours(s)
    for t in core.hour_range(day, day + timedelta(days=3)):
        changed[t] = 99.0
    assert core.forecast_rows(changed, day) == core.forecast_rows(as_hours(s), day)


# ---------- RCF shingles and log-MAD: parity ----------

def test_shingles_need_a_fully_observed_window():
    s = series(missing=("2010-01-15 10:00",))
    hours = as_hours(s)
    targets = core.hour_range(datetime(2010, 1, 15), datetime(2010, 1, 17))
    windows = core.shingles(hours, targets)
    gap = datetime(2010, 1, 15, 10)
    blocked = {gap + timedelta(hours=h) for h in range(core.SHINGLE_HOURS)}
    assert set(windows) == set(targets) - blocked
    first = datetime(2010, 1, 16, 12)
    assert windows[first] == [hours[first - timedelta(hours=h)] for h in range(23, -1, -1)]


def detector_params(detector):
    return {
        "log_mad": {
            "medians": [float(detector.medians_.loc[slot]) for slot in range(168)],
            "mads": [float(detector.mads_.loc[slot]) for slot in range(168)],
            "reference": detector.training_deviations_.tolist(),
        },
        "rcf": {"reference": [0.5, 1.0, 1.5, 2.0]},
    }


def test_log_mad_scores_match_detector():
    s = series(days=8 * 7 * 6, missing=("2010-03-03 03:00",))  # >= 30 observations per hour-of-week slot
    detector = GlobalLogMADDetector().fit(s.loc[:"2010-08-31"])
    scored = s.loc["2010-09-01":"2010-09-07 23:00"]
    expected = detector.score(scored).set_index("timestamp")["anomaly_score"].dropna()

    got = core.log_mad_scores(as_hours(s), [t.to_pydatetime() for t in scored.index], detector_params(detector))
    assert {pd.Timestamp(t) for t in got} == set(expected.index)
    np.testing.assert_allclose([got[t.to_pydatetime()] for t in expected.index], expected.to_numpy())


def test_severity_cutoffs_match_contract():
    assert [core.severity(x) for x in (0.5, 0.99, 0.995, 0.999)] == [None, "low", "medium", "high"]


# ---------- AWS calls ----------

def athena_row(*values):
    return {"Data": [{} if v is None else {"VarCharValue": v} for v in values]}


def test_query_hours_reads_pages_and_marks_incomplete_hours():
    athena = boto3.client("athena", region_name="eu-central-1")
    stub = Stubber(athena)
    stub.add_response("start_query_execution", {"QueryExecutionId": "q1"})
    stub.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "RUNNING"}}})
    stub.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}})
    stub.add_response("get_query_results", {"ResultSet": {"Rows": [
        athena_row("timestamp", "global_active_power_kwh", "complete"),
        athena_row("2010-01-08 00:00:00.000", "1.25", "true"),
    ]}, "NextToken": "t2"})
    stub.add_response("get_query_results", {"ResultSet": {"Rows": [
        athena_row("2010-01-08 01:00:00.000", None, "false"),
    ]}}, {"QueryExecutionId": "q1", "NextToken": "t2"})
    with stub:
        hours = aws.query_hours(athena, "g2_greentrack_gold", "wg", datetime(2010, 1, 8), datetime(2010, 1, 9), sleep=lambda s: None)
    stub.assert_no_pending_responses()
    assert hours == {datetime(2010, 1, 8, 0): 1.25, datetime(2010, 1, 8, 1): None}


def test_query_hours_failure_and_timeout():
    athena = boto3.client("athena", region_name="eu-central-1")
    stub = Stubber(athena)
    stub.add_response("start_query_execution", {"QueryExecutionId": "q1"})
    stub.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "FAILED", "StateChangeReason": "no table"}}})
    with stub, pytest.raises(RuntimeError, match="no table"):
        aws.query_hours(athena, "db", "wg", datetime(2010, 1, 8), datetime(2010, 1, 9), sleep=lambda s: None)

    stub = Stubber(athena)
    stub.add_response("start_query_execution", {"QueryExecutionId": "q2"})
    stub.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "RUNNING"}}})
    stub.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "RUNNING"}}})
    stub.add_response("stop_query_execution", {}, {"QueryExecutionId": "q2"})
    with stub, pytest.raises(TimeoutError, match="cancelled"):
        aws.query_hours(athena, "db", "wg", datetime(2010, 1, 8), datetime(2010, 1, 9), timeout_seconds=0.5, sleep=lambda s: None)
    stub.assert_no_pending_responses()


def test_query_is_read_only_and_bounded():
    sql = aws.QUERY.format(database="g2_greentrack_gold", start=datetime(2010, 1, 1), end=datetime(2010, 1, 8))
    assert sql.startswith("SELECT ") and ";" not in sql
    assert "TIMESTAMP '2010-01-01 00:00:00'" in sql and "TIMESTAMP '2010-01-08 00:00:00'" in sql


class FakeRuntime:
    """SageMaker runtime stand-in: XGBoost returns 1.0 per row (or -1.0 to test clipping), RCF returns the last value."""

    def __init__(self, xgb_value=1.0):
        self.xgb_value, self.calls = xgb_value, []

    def invoke_endpoint(self, EndpointName, ContentType, Accept, Body):
        self.calls.append((EndpointName, Body))
        rows = Body.split("\n")
        if EndpointName == "xgb":
            return {"Body": io.BytesIO("\n".join(str(self.xgb_value) for _ in rows).encode())}
        scores = [{"score": float(row.split(",")[-1])} for row in rows]
        return {"Body": io.BytesIO(json.dumps({"scores": scores}).encode())}


def test_xgboost_body_keeps_missing_values_empty():
    runtime = FakeRuntime()
    assert aws.predict_xgboost(runtime, "xgb", [[1, 2, 3, None, 0.5, None]]) == [1.0]
    assert runtime.calls[0][1] == "1.0,2.0,3.0,,0.5,"


# ---------- whole request ----------

class FakeS3:
    def __init__(self, params):
        self.params = params

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(json.dumps(self.params).encode())}


def run_window(monkeypatch, s, event, runtime, params):
    monkeypatch.setattr(handler, "_params", None)
    hours = as_hours(s)
    monkeypatch.setattr(aws, "query_hours", lambda athena, db, wg, start, end: {t: v for t, v in hours.items() if start <= t < end})
    env = {"XGBOOST_ENDPOINT": "xgb", "RCF_ENDPOINT": "rcf", "ATHENA_DATABASE": "db", "ATHENA_WORKGROUP": "wg",
           "PARAMS_BUCKET": "b", "PARAMS_KEY": "k", "FIRST_HOUR": "2010-01-01T00:00:00", "LAST_HOUR": "2010-01-30T23:00:00"}
    now = datetime(2026, 11, 12, 13, tzinfo=timezone.utc)
    return handler.run(event, None, runtime, FakeS3(params), env, now)


def test_handler_returns_contract_shapes_for_both_detectors(monkeypatch):
    s = series(missing=("2010-01-16 12:00",))
    s.loc["2010-01-16 03:00"] = 50.0  # a large night spike
    detector = GlobalLogMADDetector().fit(series(days=8 * 7 * 6).loc[:"2010-08-31"])
    params = detector_params(detector)
    params["rcf"]["reference"] = [0.5, 1.0, 2.0, 3.0]  # fake RCF score = last value, so 50 kWh is above all

    out = run_window(monkeypatch, s, {"start": "2010-01-15T00:00:00", "end": "2010-01-17T00:00:00"}, FakeRuntime(), params)

    forecast = out["forecast"]
    assert forecast["unit"] == "kWh" and forecast["generated_at"] == "2026-11-12T13:00:00+00:00"
    assert len(forecast["predictions"]) == 48
    assert set(forecast["predictions"][0]) == {"timestamp", "forecast_origin", "predicted_kwh", "lower_bound", "upper_bound"}
    assert forecast["predictions"][30]["forecast_origin"] == "2010-01-16T00:00:00"

    flagged = {(a["timestamp"], a["detector"]) for a in out["anomalies"]["anomalies"]}
    assert ("2010-01-16T03:00:00", "log_mad") in flagged and ("2010-01-16T03:00:00", "rcf_raw_24") in flagged
    for a in out["anomalies"]["anomalies"]:
        assert set(a) == {"timestamp", "consumption_kwh", "anomaly_score", "severity", "detector"}
        assert a["severity"] in {"low", "medium", "high"}

    assert len(out["scores"]) == 48
    gap = next(r for r in out["scores"] if r["timestamp"] == "2010-01-16T12:00:00")
    assert gap["consumption_kwh"] is None and gap["log_mad"] is None and gap["rcf_raw_24"] is None


def test_handler_clips_negative_forecasts_and_reports_bad_windows(monkeypatch):
    params = {"log_mad": {"medians": [0.0] * 168, "mads": [1.0] * 168, "reference": [1.0]}, "rcf": {"reference": [1.0]}}
    out = run_window(monkeypatch, series(), {"start": "2010-01-15T00:00:00", "end": "2010-01-16T00:00:00"}, FakeRuntime(-0.3), params)
    assert {p["predicted_kwh"] for p in out["forecast"]["predictions"]} == {0.0}

    out = run_window(monkeypatch, series(), {"start": "2010-01-02T00:00:00", "end": "2010-01-03T00:00:00"}, FakeRuntime(), params)
    assert "history" in out["error"]


# ---------- calibrate ----------

def test_calibrate_matches_the_confirmation_scheme():
    from ml.inference.calibrate import build_params

    index = pd.date_range("2008-01-01", "2010-03-31 23:00", freq="h")
    rng = np.random.default_rng(5)
    s = pd.Series((0.5 + 1.5 * (index.hour >= 18)) * np.exp(rng.normal(0, 0.3, len(index))), index=index)
    s.loc["2009-06-01 05:00"] = np.nan
    s.loc["2010-01-15":] = 999.0  # after 2009: must not influence anything

    seen = []

    def score(records):
        seen.extend(records)
        return [r[-1] for r in records]

    params = build_params(s, score, {"rcf_endpoint": "x"})

    detector = GlobalLogMADDetector().fit(s.loc[:"2008-12-31 23:00"])
    expected = np.sort(detector.score(s.loc["2009"])["robust_z"].abs().dropna().to_numpy())
    np.testing.assert_allclose(params["log_mad"]["reference"], expected)
    assert params["log_mad"]["medians"][0] == pytest.approx(detector.medians_.loc[0])

    # 2009 windows only, none touching the missing hour; references are sorted.
    assert len(seen) == len(s.loc["2009"]) - 24
    assert max(max(r) for r in seen) < 999.0
    assert params["rcf"]["reference"] == sorted(params["rcf"]["reference"])
    json.dumps(params)
