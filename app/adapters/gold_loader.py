"""Loader for gold layer data exported by Developer A."""
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np


def get_gold_exports_dir() -> Path:
    """Returns the path to gold exports directory."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "lakehouse" / "exports"


def load_hourly_consumption(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load hourly consumption data from gold layer.
    
    Returns data in the same format as contracts/consumption.json
    """
    exports_dir = get_gold_exports_dir()
    parquet_path = exports_dir / "gold_hourly_consumption"
    
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Gold data not found at {parquet_path}. "
            "Run 'python data/jobs/gold_aggregate.py' first."
        )
    
    # Read Parquet file
    df = pd.read_parquet(parquet_path)
    
    # Filter only complete hours
    df = df[df["complete"] == True].copy()
    
    # Take most recent records
    df = df.sort_values("timestamp", ascending=False).head(limit)
    
    # Replace NaN with None for JSON serialization
    df = df.replace({np.nan: None})
    
    # Convert to list of dicts matching contract format
    records = []
    for _, row in df.iterrows():
        records.append({
            "timestamp": row["timestamp"].isoformat(),
            "global_active_power_kwh": float(row["global_active_power_kwh"]) if pd.notna(row["global_active_power_kwh"]) else None,
            "sub_metering_1_kwh": float(row["sub_metering_1_kwh"]) if pd.notna(row["sub_metering_1_kwh"]) else None,
            "sub_metering_2_kwh": float(row["sub_metering_2_kwh"]) if pd.notna(row["sub_metering_2_kwh"]) else None,
            "sub_metering_3_kwh": float(row["sub_metering_3_kwh"]) if pd.notna(row["sub_metering_3_kwh"]) else None,
            "minutes_recorded": int(row["minutes_recorded"]),
            "complete": bool(row["complete"]),
        })
    
    return records


def load_daily_consumption() -> List[Dict[str, Any]]:
    """Load daily consumption aggregates from gold layer."""
    exports_dir = get_gold_exports_dir()
    parquet_path = exports_dir / "gold_daily_consumption"
    
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Gold data not found at {parquet_path}. "
            "Run 'python data/jobs/gold_aggregate.py' first."
        )
    
    df = pd.read_parquet(parquet_path)
    df = df[df["complete"] == True].copy()
    df = df.sort_values("date", ascending=False).head(30)  # Last 30 days
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": row["date"].isoformat(),
            "global_active_power_kwh": float(row["global_active_power_kwh"]),
            "peak_hour": row["peak_hour"].isoformat() if pd.notna(row["peak_hour"]) else None,
            "peak_hour_kwh": float(row["peak_hour_kwh"]) if pd.notna(row["peak_hour_kwh"]) else None,
            "complete": bool(row["complete"]),
        })
    
    return records


def detect_anomalies_simple(threshold_kwh: float = 5.0) -> List[Dict[str, Any]]:
    """
    Simple anomaly detection: hours with consumption above threshold.
    
    In production, this would use Developer B's ML model.
    """
    exports_dir = get_gold_exports_dir()
    parquet_path = exports_dir / "gold_hourly_consumption"
    
    if not parquet_path.exists():
        return []
    
    df = pd.read_parquet(parquet_path)
    df = df[df["complete"] == True].copy()
    
    # Simple rule: consumption > threshold
    anomalies_df = df[df["global_active_power_kwh"] > threshold_kwh].copy()
    anomalies_df = anomalies_df.sort_values("global_active_power_kwh", ascending=False).head(20)
    
    anomalies = []
    for _, row in anomalies_df.iterrows():
        # Simple score: how much over the threshold
        score = min((row["global_active_power_kwh"] / threshold_kwh), 1.0)
        
        # Determine severity based on consumption level
        consumption = row["global_active_power_kwh"]
        if consumption > 6.0:
            severity = "high"
        elif consumption > 5.5:
            severity = "medium"
        else:
            severity = "low"
        
        anomalies.append({
            "timestamp": row["timestamp"].isoformat(),
            "consumption_kwh": float(row["global_active_power_kwh"]),
            "anomaly_score": round(score, 3),
            "severity": severity,
        })
    
    return anomalies


def to_dynamodb_format(data: Any) -> Any:
    """Convert Python types to DynamoDB-compatible format."""
    if isinstance(data, dict):
        return {k: to_dynamodb_format(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [to_dynamodb_format(item) for item in data]
    elif isinstance(data, float):
        return Decimal(str(data))
    return data
