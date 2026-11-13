"""Tests for the DynamoDB loader's pure parts (no AWS).

Variables: RESPONSE - a minimal inference Lambda response with one forecast hour, one missing hour
and one alert per detector at the same timestamp.
"""

from datetime import date
from decimal import Decimal

from ml.inference.load_dynamodb import items, windows

RESPONSE = {
    "forecast": {"predictions": [
        {"timestamp": "2010-01-24T17:00:00", "forecast_origin": "2010-01-24T00:00:00", "predicted_kwh": 1.25},
        {"timestamp": "2010-01-24T18:00:00", "forecast_origin": "2010-01-24T00:00:00", "predicted_kwh": 0.0},
    ]},
    "anomalies": {"anomalies": [
        {"timestamp": "2010-01-24T17:00:00", "consumption_kwh": 4.2, "anomaly_score": 0.991547935,
         "severity": "low", "detector": "rcf_raw_24"},
        {"timestamp": "2010-01-24T17:00:00", "consumption_kwh": 4.2, "anomaly_score": 0.9995,
         "severity": "high", "detector": "log_mad"},
    ]},
    "scores": [{"timestamp": "2010-01-24T17:00:00", "consumption_kwh": 4.2},
               {"timestamp": "2010-01-24T18:00:00", "consumption_kwh": None}],
}


def test_windows_cover_the_period_in_week_chunks():
    w = windows(date(2010, 10, 1), date(2010, 10, 16))
    assert [x["start"][:10] for x in w] == ["2010-10-01", "2010-10-08", "2010-10-15"]
    assert w[-1]["end"] == "2010-10-16T00:00:00"
    assert windows(date(2010, 10, 1), date(2010, 10, 1)) == []


def test_forecast_items_use_decimals_and_skip_missing_actuals():
    forecasts, _ = items(RESPONSE, "household-1")
    first, second = forecasts
    assert first == {"household_id": "household-1", "timestamp": "2010-01-24T17:00:00",
                     "predicted_kwh": Decimal("1.25"), "actual_kwh": Decimal("4.2"),
                     "forecast_origin": "2010-01-24T00:00:00", "model": "xgboost"}
    assert "actual_kwh" not in second and second["predicted_kwh"] == Decimal("0.0")


def test_both_detectors_get_their_own_item_at_the_same_hour():
    _, anomalies = items(RESPONSE, "household-1")
    assert [a["timestamp_detector"] for a in anomalies] == ["2010-01-24T17:00:00#rcf_raw_24",
                                                            "2010-01-24T17:00:00#log_mad"]
    assert anomalies[0]["anomaly_score"] == Decimal("0.991548") and anomalies[1]["severity"] == "high"
    assert all(isinstance(v, (str, Decimal)) for a in anomalies for v in a.values())
