"""Tests for the Random Cut Forest input export.

Variables: a synthetic gap-free hourly series (with one incomplete stretch) and a synthetic Gold file.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from ml.sagemaker.prepare_rcf_data import (  # noqa: E402
    SHINGLE_HOURS,
    VALIDATION_START,
    build_shingles,
    write_rcf_inputs,
)


def series(start="2009-12-25 00:00", end="2010-01-05 23:00"):
    hours = pd.date_range(start, end, freq="h")
    values = 1.0 + np.arange(len(hours)) / 100
    return pd.Series(values, index=hours)


def test_shingle_holds_log_of_previous_24_hours_ending_at_t():
    consumption = series()
    shingles = build_shingles(consumption)

    t = shingles.index[0]
    expected = np.log(consumption.loc[t - pd.Timedelta(hours=SHINGLE_HOURS - 1):t].to_numpy())
    np.testing.assert_allclose(shingles.loc[t].to_numpy(), expected)
    assert list(shingles.columns) == [f"lag_{k}" for k in range(SHINGLE_HOURS - 1, -1, -1)]


def test_windows_touching_a_missing_hour_are_dropped():
    consumption = series()
    gap = pd.Timestamp("2009-12-30 12:00")
    consumption.loc[gap] = np.nan

    shingles = build_shingles(consumption)

    touching = (shingles.index >= gap) & (shingles.index < gap + pd.Timedelta(hours=SHINGLE_HOURS))
    assert not touching.any()
    assert np.isfinite(shingles.to_numpy()).all()


def test_split_and_files(tmp_path):
    consumption = series()
    gold = tmp_path / "gold.parquet"
    pd.DataFrame({
        "timestamp": consumption.index,
        "global_active_power_kwh": consumption.to_numpy(),
        "complete": np.ones(len(consumption), dtype=bool),
    }).to_parquet(gold)

    counts = write_rcf_inputs(gold, tmp_path / "out")

    train = pd.read_csv(tmp_path / "out" / "train.csv", header=None)
    validation = pd.read_csv(tmp_path / "out" / "validation.csv", header=None)
    index = pd.read_csv(tmp_path / "out" / "validation_index.csv", parse_dates=["timestamp"])

    assert len(train) == counts["train"] and len(validation) == counts["validation"]
    assert train.shape[1] == SHINGLE_HOURS and validation.shape[1] == SHINGLE_HOURS
    assert len(index) == len(validation)
    assert index["timestamp"].min() == pd.Timestamp(VALIDATION_START)
