"""Tests for local consumption data access."""

import pandas as pd

from genai.data_access import load_complete_hours


def test_filters_invalid_and_out_of_range_hours(tmp_path):
    timestamps = pd.date_range(
        "2010-01-01",
        periods=7,
        freq="h",
    )

    frame = pd.DataFrame({
        "timestamp": timestamps,
        "global_active_power_kwh": [
            20.0, 2.0, 9.0, float("nan"),
            float("inf"), 1.0, 8.0,
        ],
        "complete": [
            True, True, False, True,
            True, True, True,
        ],
    })

    path = tmp_path / "hourly.parquet"
    frame.to_parquet(path, index=False)

    result = load_complete_hours(
        path,
        start="2010-01-01 01:00:00",
        end="2010-01-01 06:00:00",
    )

    assert result["timestamp"].tolist() == [
        timestamps[1],
        timestamps[5],
    ]

    assert result["global_active_power_kwh"].tolist() == [
        2.0,
        1.0,
    ]


def test_rejects_reversed_date_range(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="start must be before end"):
        load_complete_hours(
            tmp_path / "unused.parquet",
            start="2010-01-02",
            end="2010-01-01",
        )


def test_rejects_equal_date_boundaries(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="start must be before end"):
        load_complete_hours(
            tmp_path / "unused.parquet",
            start="2010-01-01",
            end="2010-01-01",
        )


def test_rejects_timezone_aware_dates(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="timezone-naive"):
        load_complete_hours(
            tmp_path / "unused.parquet",
            start="2010-01-01T00:00:00+01:00",
            end="2010-01-02T00:00:00+01:00",
        )
