"""Convert scored observations to the shared anomaly API contract."""

from datetime import datetime, timezone
import math

import pandas as pd


SEVERITIES = {"low", "medium", "high"}
REQUIRED = {
    "timestamp",
    "consumption_kwh",
    "anomaly_score",
    "severity",
}


def to_anomaly_response(
    scores: pd.DataFrame,
    *,
    generated_at: datetime | None = None,
) -> dict:
    """Return only flagged observations in the Developer B -> C contract."""

    missing = REQUIRED - set(scores.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    anomalies = []

    flagged = scores.loc[scores["severity"].notna()]

    for timestamp, consumption, score, severity in flagged[
        ["timestamp", "consumption_kwh", "anomaly_score", "severity"]
    ].itertuples(index=False, name=None):

        if severity not in SEVERITIES:
            raise ValueError(f"Invalid severity: {severity}")

        consumption = float(consumption)
        score = float(score)

        if not math.isfinite(consumption) or consumption <= 0:
            raise ValueError("Invalid consumption in flagged observation")

        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Anomaly score must be between 0 and 1")

        timestamp = pd.Timestamp(timestamp)
        if pd.isna(timestamp):
            raise ValueError("Invalid anomaly timestamp")

        anomalies.append({
            "timestamp": timestamp.isoformat(),
            "consumption_kwh": consumption,
            "anomaly_score": score,
            "severity": severity,
        })

    return {
        "generated_at": generated_at.isoformat(),
        "anomalies": anomalies,
    }
