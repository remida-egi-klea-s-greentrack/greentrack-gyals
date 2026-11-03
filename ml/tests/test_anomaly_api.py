"""Tests for the Developer B -> C anomaly API response."""

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from ml.anomaly.api import to_anomaly_response


GENERATED_AT = datetime(
    2026, 11, 1, 15, 0, tzinfo=timezone.utc
)


def test_response_contains_only_flagged_anomalies():
    scores = pd.DataFrame({
        "timestamp": pd.date_range(
            "2010-01-01", periods=3, freq="h"
        ),
        "consumption_kwh": [1.0, 4.8, np.nan],
        "anomaly_score": [0.5, 0.996, np.nan],
        "severity": [None, "medium", None],
    })

    response = to_anomaly_response(
        scores, generated_at=GENERATED_AT
    )

    assert response == {
        "generated_at": "2026-11-01T15:00:00+00:00",
        "anomalies": [{
            "timestamp": "2010-01-01T01:00:00",
            "consumption_kwh": 4.8,
            "anomaly_score": 0.996,
            "severity": "medium",
        }],
    }

    # Must serialize without custom JSON encoders.
    json.dumps(response)


def test_empty_response():
    scores = pd.DataFrame(columns=[
        "timestamp", "consumption_kwh",
        "anomaly_score", "severity",
    ])

    response = to_anomaly_response(
        scores, generated_at=GENERATED_AT
    )

    assert response["anomalies"] == []


def test_invalid_severity_rejected():
    scores = pd.DataFrame({
        "timestamp": [pd.Timestamp("2010-01-01")],
        "consumption_kwh": [3.0],
        "anomaly_score": [0.999],
        "severity": ["critical"],
    })

    with pytest.raises(ValueError, match="Invalid severity"):
        to_anomaly_response(
            scores, generated_at=GENERATED_AT
        )
