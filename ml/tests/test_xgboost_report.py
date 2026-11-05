"""Integration test for XGBoost validation artifacts and strict JSON metadata."""

import hashlib
import json
import sys

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.forecasting import run_xgboost_validation as report
from ml.forecasting.features import build_forecast_features, FEATURE_COLUMNS


def test_validation_report_outputs(tmp_path, monkeypatch):
    hours = pd.date_range("2009-12-01", "2010-01-02 23:00", freq="h")
    frame = pd.DataFrame({
        "timestamp": hours,
        "global_active_power_kwh": 1.0 + 0.1 * np.sin(np.arange(len(hours)) / 7),
        "complete": True,
    })
    input_path = tmp_path / "hourly.parquet"
    output_dir = tmp_path / "report"
    frame.to_parquet(input_path, index=False)

    monkeypatch.setattr(report, "TRAIN_START", "2009-12-08")
    monkeypatch.setattr(report, "TRAIN_END", "2009-12-31")
    monkeypatch.setattr(report, "VALIDATION_END", "2010-01-02")
    monkeypatch.setattr(sys, "argv", [
        "run_xgboost_validation",
        "--input", str(input_path),
        "--output", str(output_dir),
    ])

    report.main()

    assert {path.name for path in output_dir.iterdir()} == {
        "predictions.csv", "per_day_metrics.csv", "overall_metrics.csv",
        "exclusions.csv", "model.ubj", "manifest.json",
    }

    def reject_nonfinite(value):
        raise ValueError(f"Invalid JSON constant: {value}")

    manifest = json.loads(
        (output_dir / "manifest.json").read_text(),
        parse_constant=reject_nonfinite,
    )
    assert manifest["model_parameters"]["missing"] is None
    assert manifest["eligible_days"] == 2
    assert manifest["prediction_hours"] == 48
    assert manifest["input_sha256"] == hashlib.sha256(
        input_path.read_bytes()
    ).hexdigest()

    restored = XGBRegressor()
    restored.load_model(output_dir / "model.ubj")
    assert np.isnan(restored.missing)
    consumption = frame.set_index("timestamp")["global_active_power_kwh"]
    features = build_forecast_features(consumption, pd.Timestamp("2010-01-01"))
    predictions = pd.read_csv(output_dir / "predictions.csv")
    np.testing.assert_allclose(
        restored.predict(features[FEATURE_COLUMNS]),
        predictions["xgboost_pred_kwh"].iloc[:24],
    )
