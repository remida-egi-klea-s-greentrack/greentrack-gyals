"""Tests for deterministic consumption queries."""

import pandas as pd

from genai.queries import find_peak_consumption


def test_peak_selects_earliest_valid_maximum(tmp_path):
    timestamps = pd.date_range(
        "2010-01-01", periods=5, freq="h"
    )

    frame = pd.DataFrame({
        "timestamp": timestamps,
        "global_active_power_kwh": [
            2.0, 5.0, 5.0, 9.0, 99.0
        ],
        "complete": [
            True, True, True, False, True
        ],
    })

    path = tmp_path / "hourly.parquet"
    frame.to_parquet(path, index=False)

    result = find_peak_consumption(
        path,
        start="2010-01-01 00:00:00",
        end="2010-01-01 04:00:00",
    )

    assert result == {
        "timestamp": "2010-01-01T01:00:00",
        "consumption_kwh": 5.0,
    }


def test_peak_returns_none_without_valid_hours(tmp_path):
    frame = pd.DataFrame({
        "timestamp": [pd.Timestamp("2010-01-01")],
        "global_active_power_kwh": [None],
        "complete": [False],
    })

    path = tmp_path / "empty.parquet"
    frame.to_parquet(path, index=False)

    result = find_peak_consumption(
        path,
        start="2010-01-01",
        end="2010-01-02",
    )

    assert result is None
