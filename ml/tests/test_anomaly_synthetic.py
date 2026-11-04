"""Integration test for reproducible synthetic anomaly evaluation."""

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from ml.anomaly.run_synthetic import main


def test_synthetic_evaluation_report(tmp_path, monkeypatch):
    # Enough training history for all 168 hour-of-week groups.
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

    input_path = tmp_path / "hourly.parquet"
    output_dir = tmp_path / "synthetic_report"

    frame.to_parquet(input_path, index=False)

    monkeypatch.setattr(sys, "argv", [
        "run_synthetic",
        "--input", str(input_path),
        "--output", str(output_dir),
    ])

    main()

    assert {p.name for p in output_dir.iterdir()} == {
        "injections.csv",
        "manifest.json",
    }

    manifest = json.loads(
        (output_dir / "manifest.json").read_text()
    )
    injections = pd.read_csv(output_dir / "injections.csv")

    assert manifest["seed"] == 42
    assert manifest["test_period_evaluated"] is False
    assert manifest["unmodified_scores_unchanged"] is True

    assert manifest["input_sha256"] == hashlib.sha256(
        input_path.read_bytes()
    ).hexdigest()

    assert len(injections) == 40
    assert injections["timestamp"].is_unique

    for name, factor in [
        ("high_x5", 5.0),
        ("low_x0_2", 0.2),
    ]:
        rows = injections[injections["injection"] == name]
        result = manifest["results"][name]

        assert len(rows) == 20
        assert result["injected"] == 20
        assert result["correct_direction"] == 20

        assert np.allclose(
            rows["modified_kwh"],
            rows["original_kwh"] * factor,
        )

        assert result["detected"] == rows["severity"].notna().sum()
        assert result["detection_rate"] == result["detected"] / 20
        assert sum(result["severity_counts"].values()) == result["detected"]

        # Selected observations were originally not flagged.
        assert (rows["original_score"] < 0.99).all()
