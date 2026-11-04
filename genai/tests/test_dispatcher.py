"""Tests for the local query dispatcher."""

import pandas as pd
import pytest

from genai.dispatcher import dispatch_local_query


def test_dispatches_peak_query(tmp_path):
    frame = pd.DataFrame({
        "timestamp": pd.date_range(
            "2010-01-01", periods=3, freq="h"
        ),
        "global_active_power_kwh": [1.0, 3.5, 2.0],
        "complete": [True, True, True],
    })

    path = tmp_path / "hourly.parquet"
    frame.to_parquet(path, index=False)

    result = dispatch_local_query(
        "peak_hourly_consumption",
        path,
        start="2010-01-01",
        end="2010-01-02",
    )

    assert "3.500 kWh" in result["answer"]
    assert "2010-01-01T01:00:00" in result["answer"]
    assert result["tools_used"] == ["find_peak_consumption"]


def test_rejects_unsupported_query_without_data_access(tmp_path):
    result = dispatch_local_query(
        "total_consumption",
        tmp_path / "nonexistent.parquet",
    )

    assert result["citations"] == []
    assert result["tools_used"] == []


def test_requires_explicit_date_range(tmp_path):
    with pytest.raises(ValueError, match="requires start and end"):
        dispatch_local_query(
            "peak_hourly_consumption",
            tmp_path / "nonexistent.parquet",
        )
