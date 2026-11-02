"""Input-data contract for hourly electricity consumption."""

from pathlib import Path

import numpy as np
import pandas as pd


def load_hourly_consumption(path: Path) -> pd.Series:
    """Load and validate complete/incomplete hourly consumption records."""
    df = pd.read_parquet(path)

    required = {"timestamp", "global_active_power_kwh", "complete"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing input columns: {sorted(missing)}")

    timestamps = pd.DatetimeIndex(pd.to_datetime(df["timestamp"]))

    if timestamps.hasnans or timestamps.has_duplicates:
        raise ValueError("Null or duplicate timestamps")
    if timestamps.tz is not None:
        raise ValueError("Expected timezone-naive hourly timestamps")
    if not (timestamps == timestamps.floor("h")).all():
        raise ValueError("Timestamps must be aligned to whole hours")

    expected = pd.date_range(
        timestamps.min(), timestamps.max(), freq="h"
    )
    if not timestamps.sort_values().equals(expected):
        raise ValueError("Missing hours in input timeline")

    if not pd.api.types.is_bool_dtype(df["complete"]):
        raise ValueError("Complete column must be boolean")
    if df["complete"].isna().any():
        raise ValueError("Complete column contains null values")

    complete = df["complete"].to_numpy(dtype=bool)
    power = pd.to_numeric(
        df["global_active_power_kwh"], errors="raise"
    ).to_numpy(dtype=float)

    if not np.isfinite(power[complete]).all():
        raise ValueError("Complete hours must have finite consumption")
    if (power[complete] <= 0).any():
        raise ValueError("Complete hours must have positive consumption")
    if not np.isnan(power[~complete]).all():
        raise ValueError("Incomplete hours must have null consumption")

    return pd.Series(
        power,
        index=timestamps,
        name="global_active_power_kwh",
    ).sort_index()
