"""Tests for the SageMaker XGBoost training-data export.

Variables: a synthetic Gold file covering the frozen training window (tmp_path fixture).
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from ml.forecasting.features import FEATURE_COLUMNS  # noqa: E402
from ml.sagemaker.prepare_xgboost_data import HYPERPARAMETERS, write_training_csv  # noqa: E402


@pytest.fixture
def gold_file(tmp_path):
    hours = pd.date_range("2006-12-16 17:00", "2010-01-02 23:00", freq="h")
    power = np.full(len(hours), 1.0) + (np.arange(len(hours)) % 24) / 10
    complete = np.ones(len(hours), dtype=bool)
    complete[100:110] = False  # a gap: incomplete hours have null consumption
    power[~complete] = np.nan
    path = tmp_path / "gold.parquet"
    pd.DataFrame({"timestamp": hours, "global_active_power_kwh": power, "complete": complete}).to_parquet(path)
    return path


def test_csv_has_target_first_and_no_header(gold_file, tmp_path):
    rows = write_training_csv(gold_file, tmp_path / "out")
    csv = pd.read_csv(tmp_path / "out" / "train.csv", header=None)

    assert len(csv) == rows
    assert csv.shape[1] == 1 + len(FEATURE_COLUMNS)
    # First column is the target: always present and positive.
    assert csv[0].notna().all() and (csv[0] > 0).all()
    # Hour column (first feature) holds hours, not a header string.
    assert set(csv[1].unique()) <= set(range(24))


def test_missing_features_are_kept_as_empty_values(gold_file, tmp_path):
    write_training_csv(gold_file, tmp_path / "out")
    csv = pd.read_csv(tmp_path / "out" / "train.csv", header=None)

    # The gap makes some lag features unavailable; those rows are kept with missing values.
    assert csv.iloc[:, 1:].isna().any().any()


def test_hyperparameters_match_frozen_model():
    assert HYPERPARAMETERS["num_round"] == "200"
    assert HYPERPARAMETERS["eta"] == "0.05"
    assert HYPERPARAMETERS["max_depth"] == "4"
    assert HYPERPARAMETERS["seed"] == "42"
