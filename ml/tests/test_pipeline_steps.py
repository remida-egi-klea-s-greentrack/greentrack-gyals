"""Tests for the SageMaker pipeline steps without AWS.

Variables: hours_rows - Athena-style string rows for a synthetic series (daily pattern, one incomplete hour);
the training and validation windows are shortened with monkeypatch so the tests stay fast.
"""

import io
import json
import tarfile

import numpy as np
import pandas as pd
import pytest
import xgboost

from ml.forecasting.features import FEATURE_COLUMNS
from ml.pipeline import steps


def hours_rows(start="2009-11-01", days=60, incomplete=("2009-11-20 05:00:00",)):
    index = pd.date_range(start, periods=days * 24, freq="h")
    rows = []
    for t in index:
        kwh = 0.5 + 0.4 * np.sin(2 * np.pi * t.hour / 24) ** 2 + 0.1 * (t.day_of_week >= 5)
        complete = str(t) not in incomplete
        rows.append([f"{t:%Y-%m-%d %H:%M:%S}.000 UTC", f"{kwh:.4f}", "true" if complete else "false"])
    return rows


@pytest.fixture
def short_windows(monkeypatch):
    monkeypatch.setattr(steps, "TRAIN_START", "2009-11-10")
    monkeypatch.setattr(steps, "TRAIN_END", "2009-12-10")
    monkeypatch.setattr(steps, "VALIDATION_START", "2009-12-15")
    monkeypatch.setattr(steps, "VALIDATION_END", "2009-12-25")


def test_hourly_frame_parses_athena_strings_and_blanks_incomplete_hours():
    frame = steps.hourly_frame(hours_rows(days=2, incomplete=("2009-11-01 03:00:00",)))
    assert frame["complete"].dtype == bool and frame["timestamp"].iloc[0] == pd.Timestamp("2009-11-01")
    assert frame["timestamp"].dt.tz is None
    assert frame["global_active_power_kwh"].isna().sum() == 1 and not frame.loc[3, "complete"]


def test_prepare_writes_training_csv_and_hours(tmp_path, short_windows):
    count = steps.prepare(hours_rows(), tmp_path)
    train = pd.read_csv(tmp_path / "train" / "train.csv", header=None)
    assert count == len(train) == 31 * 24 - 1  # the incomplete hour is not a training target
    assert train.shape[1] == 1 + len(FEATURE_COLUMNS)
    hours = steps.read_hours(tmp_path / "hours" / steps.HOURS_FILE)
    assert len(hours) == 60 * 24 and hours.isna().sum() == 1


def test_load_model_reads_the_built_in_archive(tmp_path):
    x = np.random.default_rng(0).random((50, len(FEATURE_COLUMNS)))
    booster = xgboost.train({"objective": "reg:squarederror"}, xgboost.DMatrix(x, label=x[:, 0]), 5)
    raw = booster.save_raw("json")
    with tarfile.open(tmp_path / "model.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("xgboost-model")
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(bytes(raw)))
    model = steps.load_model(tmp_path)
    features = pd.DataFrame(x[:3], columns=FEATURE_COLUMNS)
    assert np.allclose(model.predict(features), booster.predict(xgboost.DMatrix(x[:3])))


class LagModel:
    """Predicts the value of 24 hours earlier, so it equals the daily baseline."""

    def predict(self, features):
        return features["lag_24h_kwh"].to_numpy(dtype=float)


def test_evaluate_compares_with_the_best_baseline(tmp_path, short_windows):
    steps.prepare(hours_rows(), tmp_path)
    result = steps.evaluate(LagModel(), steps.read_hours(tmp_path / "hours" / steps.HOURS_FILE))
    assert set(result["rmse_kwh"]) == {"daily", "weekly", "xgboost"}
    assert result["baseline_rmse"] == min(result["rmse_kwh"]["daily"], result["rmse_kwh"]["weekly"])
    assert result["xgboost_rmse"] == pytest.approx(result["rmse_kwh"]["daily"])
    assert result["regression_metrics"]["rmse"]["value"] == result["xgboost_rmse"]
    assert result["validation"]["days"] == 11
    json.dumps(result)
