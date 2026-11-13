"""Tests for the Random Cut Forest input export.

Variables: a synthetic gap-free hourly series (with one incomplete stretch) and a synthetic Gold file.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from ml.sagemaker.prepare_rcf_data import (  # noqa: E402
    CALIBRATION_END,
    CALIBRATION_START,
    FIT_END,
    SHINGLE_HOURS,
    VALIDATION_END,
    VALIDATION_START,
    build_shingles,
    split_shingles,
    write_rcf_inputs,
)


def series(start="2009-12-25 00:00", end="2010-01-05 23:00"):
    hours = pd.date_range(start, end, freq="h")
    values = 1.0 + np.arange(len(hours)) / 100
    return pd.Series(values, index=hours)


def test_shingle_holds_kwh_of_previous_24_hours_ending_at_t():
    consumption = series()
    shingles = build_shingles(consumption)

    t = shingles.index[0]
    expected = consumption.loc[t - pd.Timedelta(hours=SHINGLE_HOURS - 1):t].to_numpy()
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


def test_injected_hour_changes_exactly_the_windows_containing_it():
    consumption = series()
    t = pd.Timestamp("2009-12-30 12:00")
    modified = consumption.copy()
    modified.loc[t] *= 5

    changed = (build_shingles(modified) != build_shingles(consumption)).any(axis=1)
    expected = pd.date_range(t, t + pd.Timedelta(hours=SHINGLE_HOURS - 1), freq="h")
    assert changed[changed].index.equals(expected)


def test_split_periods_and_files(tmp_path):
    consumption = series("2008-12-20 00:00", "2010-06-10 23:00")
    gold = tmp_path / "gold.parquet"
    pd.DataFrame({
        "timestamp": consumption.index,
        "global_active_power_kwh": consumption.to_numpy(),
        "complete": np.ones(len(consumption), dtype=bool),
    }).to_parquet(gold)

    counts = write_rcf_inputs(gold, tmp_path / "out")

    out = tmp_path / "out"
    for name in ["train", "calibration", "validation"]:
        frame = pd.read_csv(out / f"{name}.csv", header=None)
        assert len(frame) == counts[name] and frame.shape[1] == SHINGLE_HOURS
    assert not (out / "train_index.csv").exists()

    calibration = pd.read_csv(out / "calibration_index.csv", parse_dates=["timestamp"])["timestamp"]
    validation = pd.read_csv(out / "validation_index.csv", parse_dates=["timestamp"])["timestamp"]
    assert calibration.min() == pd.Timestamp(CALIBRATION_START) and calibration.max() == pd.Timestamp(CALIBRATION_END)
    assert validation.min() == pd.Timestamp(VALIDATION_START) and validation.max() == pd.Timestamp(VALIDATION_END)
    assert counts["train"] == len(split_shingles(consumption)["train"].loc[:FIT_END])


def test_split_never_reads_hours_after_validation():
    consumption = series("2008-12-20 00:00", "2010-06-10 23:00")
    changed = consumption.copy()
    changed.loc["2010-06-01":] = 99.0

    for name, frame in split_shingles(consumption).items():
        pd.testing.assert_frame_equal(frame, split_shingles(changed)[name])
