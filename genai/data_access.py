"""Read validated hourly consumption records from local Parquet."""

from pathlib import Path

import numpy as np
import pandas as pd


def load_complete_hours(
    path: str | Path,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Return valid hourly observations in [start, end)."""

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    if start_ts.tzinfo is not None or end_ts.tzinfo is not None:
        raise ValueError("Timestamps must be timezone-naive")

    if start_ts >= end_ts:
        raise ValueError("start must be before end")

    frame = pd.read_parquet(
        path,
        columns=[
            "timestamp",
            "global_active_power_kwh",
            "complete",
        ],
    )

    frame["global_active_power_kwh"] = pd.to_numeric(
        frame["global_active_power_kwh"], errors="coerce"
    )
    consumption = frame["global_active_power_kwh"]

    valid = (
        (frame["timestamp"] >= start_ts)
        & (frame["timestamp"] < end_ts)
        & frame["complete"].eq(True)
        & np.isfinite(consumption)
        & (consumption > 0)
    )

    return (
        frame.loc[
            valid,
            ["timestamp", "global_active_power_kwh"],
        ]
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
