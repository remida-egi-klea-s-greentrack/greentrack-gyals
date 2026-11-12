"""Deterministic electricity consumption queries."""

from pathlib import Path

from genai.data_access import load_complete_hours


def find_peak_consumption(
    path: str | Path,
    start: str,
    end: str,
) -> dict | None:
    """Find the earliest peak hourly consumption in [start, end)."""

    frame = load_complete_hours(path, start, end)

    if frame.empty:
        return None

    # Data loader sorts chronologically, so idxmax selects
    # the earliest timestamp when peak values are tied.
    peak = frame.loc[
        frame["global_active_power_kwh"].idxmax()
    ]

    return {
        "timestamp": peak["timestamp"].isoformat(),
        "consumption_kwh": float(
            peak["global_active_power_kwh"]
        ),
    }
