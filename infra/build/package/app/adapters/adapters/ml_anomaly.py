"""Anomaly detection integration using Developer B's ML outputs."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def get_ml_artifacts_dir() -> Path:
    """Returns the path to ML artifacts directory."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "ml_artifacts"


def detect_anomalies() -> Dict[str, Any]:
    """
    Load anomaly detection results from Developer B's ML pipeline.
    
    Returns data matching contracts/anomaly.json format.
    """
    artifacts_dir = get_ml_artifacts_dir()
    anomalies_csv = artifacts_dir / "anomaly" / "anomalies.csv"
    
    if not anomalies_csv.exists():
        raise FileNotFoundError(
            f"Anomaly data not found at {anomalies_csv}. "
            "Developer B must provide ML artifacts."
        )
    
    # Read CSV from Developer B
    df = pd.read_csv(anomalies_csv)
    
    # Convert to API format matching contract
    anomalies = []
    for _, row in df.iterrows():
        anomalies.append({
            "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
            "consumption_kwh": float(row["consumption_kwh"]),
            "anomaly_score": float(row["anomaly_score"]),
            "severity": str(row["severity"]),
        })
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "anomalies": anomalies,
    }


def get_anomaly_statistics() -> Dict[str, Any]:
    """Get statistics about detected anomalies."""
    artifacts_dir = get_ml_artifacts_dir()
    anomalies_csv = artifacts_dir / "anomaly" / "anomalies.csv"
    
    if not anomalies_csv.exists():
        return {"error": "No anomaly data available"}
    
    df = pd.read_csv(anomalies_csv)
    
    return {
        "total_anomalies": len(df),
        "by_severity": {
            "low": len(df[df["severity"] == "low"]),
            "medium": len(df[df["severity"] == "medium"]),
            "high": len(df[df["severity"] == "high"]),
        },
        "date_range": {
            "start": pd.Timestamp(df["timestamp"].min()).isoformat(),
            "end": pd.Timestamp(df["timestamp"].max()).isoformat(),
        },
    }
