"""Tests for XGBoost training and model persistence."""

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBRegressor

from ml.forecasting.features import FEATURE_COLUMNS
from ml.forecasting.xgboost_model import train_xgboost


@pytest.fixture
def training_rows():
    hours = pd.date_range(
        "2010-01-01", periods=72, freq="h"
    )

    frame = pd.DataFrame({
        "hour": hours.hour,
        "day_of_week": hours.day_of_week,
        "month": hours.month,
        "lag_24h_kwh": np.linspace(0.5, 2.0, 72),
        "lag_168h_kwh": np.linspace(0.6, 1.8, 72),
        "mean_last_24h_kwh": np.full(72, 1.2),
        "target_kwh": 1.0 + 0.05 * hours.hour,
    })

    # Historical features may be missing.
    frame.loc[:5, "lag_24h_kwh"] = np.nan
    frame.loc[:10, "lag_168h_kwh"] = np.nan

    return frame


def test_model_training_and_persistence(training_rows, tmp_path):
    model = train_xgboost(training_rows)

    assert isinstance(model, XGBRegressor)
    assert model.n_estimators == 200

    features = training_rows[FEATURE_COLUMNS]
    original = model.predict(features)

    assert original.shape == (72,)
    assert np.isfinite(original).all()

    path = tmp_path / "model.ubj"
    model.save_model(path)

    assert path.exists()

    restored = XGBRegressor()
    restored.load_model(path)
    reloaded = restored.predict(features)

    np.testing.assert_allclose(
        original, reloaded, rtol=1e-6, atol=1e-6
    )


def test_missing_columns_rejected(training_rows):
    invalid = training_rows.drop(columns=["month"])

    with pytest.raises(ValueError, match="Missing required"):
        train_xgboost(invalid)


def test_empty_training_data_rejected(training_rows):
    with pytest.raises(ValueError, match="empty"):
        train_xgboost(training_rows.iloc[:0])


@pytest.mark.parametrize("invalid_target", [np.nan, np.inf])
def test_nonfinite_training_targets_rejected(
    training_rows, invalid_target
):
    invalid = training_rows.copy()
    invalid.loc[0, "target_kwh"] = invalid_target

    with pytest.raises(ValueError, match="must be finite"):
        train_xgboost(invalid)
