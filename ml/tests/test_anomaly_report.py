"""Integration test for the local anomaly validation report."""

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from ml.anomaly.run_validation import main


def test_validation_report_outputs(tmp_path, monkeypatch):
    index = pd.date_range(
        "2009-05-01",
        "2010-01-03 23:00",
        freq="h",
    )

    t = np.arange(len(index))

    consumption = (
        1.0
        + 0.15 * np.sin(2 * np.pi * index.hour / 24)
        + 0.08 * np.sin(t / 37)
        + 0.03 * np.sin(t / 11)
    )

    frame = pd.DataFrame({
        "timestamp": index,
        "global_active_power_kwh": consumption,
        "complete": True,
    })

    # Include one incomplete validation hour.
    missing = frame["timestamp"] == pd.Timestamp(
        "2010-01-02 02:00"
    )
    frame.loc[missing, "complete"] = False
    frame.loc[missing, "global_active_power_kwh"] = np.nan

    input_path = tmp_path / "hourly.parquet"
    output_dir = tmp_path / "report"
    frame.to_parquet(input_path, index=False)

    monkeypatch.setattr(sys, "argv", [
        "run_validation",
        "--input", str(input_path),
        "--output", str(output_dir),
    ])

    main()

    expected = {
        "scores.csv",
        "anomalies.csv",
        "monthly_summary.csv",
        "episodes.csv",
        "manifest.json",
    }

    assert {p.name for p in output_dir.iterdir()} == expected

    scores = pd.read_csv(output_dir / "scores.csv")
    anomalies = pd.read_csv(output_dir / "anomalies.csv")
    episodes = pd.read_csv(output_dir / "episodes.csv")
    manifest = json.loads(
        (output_dir / "manifest.json").read_text()
    )

    assert len(scores) == 72
    assert scores["anomaly_score"].notna().sum() == 71

    assert len(anomalies) == manifest["alert_hours"]
    assert len(episodes) == manifest["episodes"]

    assert episodes["flagged_hours"].sum() == len(anomalies)

    assert manifest["validation_scored_hours"] == 71
    assert manifest["test_period_evaluated"] is False

    assert manifest["input_sha256"] == hashlib.sha256(
        input_path.read_bytes()
    ).hexdigest()

    assert set(anomalies["severity"]).issubset({
        "low", "medium", "high"
    })
