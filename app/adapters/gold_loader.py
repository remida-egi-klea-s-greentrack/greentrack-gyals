"""Loader for gold layer data exported by Developer A."""
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np
import boto3


# S3 bucket dhe paths për gold data (Developer A)
S3_BUCKET = os.environ.get("DATA_BUCKET", "g2-greentrack-data-886565871385")
S3_GOLD_PREFIX = "lakehouse/exports/"


def get_gold_exports_dir() -> Path:
    """Returns the path to gold exports directory (for local development)."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "lakehouse" / "exports"


def load_parquet_from_s3(table_name: str) -> pd.DataFrame:
    """
    Load Parquet data from S3.
    Works both in Lambda (S3) and locally (fallback to local files).
    """
    # Try S3 first (for Lambda/AWS environment)
    try:
        s3_path = f"s3://{S3_BUCKET}/{S3_GOLD_PREFIX}{table_name}/"
        df = pd.read_parquet(s3_path)
        print(f"✅ Loaded {len(df)} rows from S3: {s3_path}")
        return df
    except Exception as e:
        print(f"⚠️  S3 load failed: {e}")
        
        # Fallback to local files (for development)
        local_path = get_gold_exports_dir() / table_name
        if local_path.exists():
            df = pd.read_parquet(local_path)
            print(f"✅ Loaded {len(df)} rows from local: {local_path}")
            return df
        else:
            raise FileNotFoundError(
                f"Gold data not found in S3 ({s3_path}) or locally ({local_path}). "
                "Ensure Developer A's pipeline has run."
            )


def load_hourly_consumption(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load hourly consumption data from gold layer (S3 or local).
    
    Returns data in the same format as contracts/consumption.json
    """
    # Load from S3 (or local fallback)
    df = load_parquet_from_s3("gold_hourly_consumption")
    
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
    """Load daily consumption aggregates from gold layer (S3 or local)."""
    # Load from S3 (or local fallback)
    df = load_parquet_from_s3("gold_daily_consumption")
    
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
    try:
        df = load_parquet_from_s3("gold_hourly_consumption")
        df = df[df["complete"] == True].copy()
    except Exception as e:
        print(f"⚠️  Could not load gold data for anomalies: {e}")
        return []
    
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
