"""XGBoost model for hourly electricity consumption forecasting."""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.forecasting.features import FEATURE_COLUMNS


def train_xgboost(train: pd.DataFrame) -> XGBRegressor:
    """Fit a fixed-configuration XGBoost forecasting model."""
    required = set(FEATURE_COLUMNS) | {"target_kwh"}

    if not required.issubset(train.columns):
        raise ValueError("Missing required training columns")
    if train.empty:
        raise ValueError("Training data is empty")
    targets = train["target_kwh"].to_numpy(dtype=float)
    if not np.isfinite(targets).all():
        raise ValueError("Training targets must be finite")

    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        tree_method="hist",
        random_state=42,
        n_jobs=2,
    )

    model.fit(
        train[FEATURE_COLUMNS],
        train["target_kwh"],
    )

    return model
