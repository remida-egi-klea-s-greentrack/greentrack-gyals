"""ML forecasting integration using Developer B's models."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# Add project root to path for ml module import
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from ml.forecasting.baseline import seasonal_naive_forecast


def get_consumption_series() -> pd.Series:
    """Load consumption data as pandas Series for ML model."""
    from app.adapters.gold_loader import get_gold_exports_dir
    
    exports_dir = get_gold_exports_dir()
    parquet_path = exports_dir / "gold_hourly_consumption"
    
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Gold data not found. Run 'python data/jobs/gold_aggregate.py' first."
        )
    
    df = pd.read_parquet(parquet_path)
    
    # Use only complete hours for forecasting
    df = df[df["complete"] == True].copy()
    df = df.sort_values("timestamp")
    
    # Create Series with timestamp index
    series = pd.Series(
        df["global_active_power_kwh"].values,
        index=pd.DatetimeIndex(df["timestamp"]),
        name="global_active_power_kwh"
    )
    
    return series


def generate_forecast(horizon_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Generate consumption forecast using Developer B's ML model.
    
    Args:
        horizon_hours: Number of hours to forecast
    
    Returns:
        List of predictions matching contracts/forecast.json format
    """
    try:
        # Load consumption data
        consumption = get_consumption_series()
        
        # Use the most recent timestamp as forecast origin
        origin = consumption.index[-1]
        
        # Generate forecast using seasonal naive model
        forecast = seasonal_naive_forecast(
            consumption=consumption,
            origin=origin,
            horizon=horizon_hours,
            season_hours=168,  # Weekly seasonality
        )
        
        # Convert to API format
        predictions = []
        for timestamp, predicted_kwh in forecast.items():
            predictions.append({
                "timestamp": timestamp.isoformat(),
                "predicted_kwh": round(float(predicted_kwh), 4),
            })
        
        return predictions
        
    except Exception as e:
        # If ML model fails, return empty predictions with error info
        print(f"⚠️  Forecast generation failed: {e}")
        return []


def get_forecast_metadata() -> Dict[str, Any]:
    """Get metadata about the forecast model."""
    try:
        consumption = get_consumption_series()
        return {
            "model": "seasonal_naive",
            "model_version": "1.0",
            "training_data_start": consumption.index[0].isoformat(),
            "training_data_end": consumption.index[-1].isoformat(),
            "training_samples": len(consumption),
        }
    except Exception:
        return {
            "model": "seasonal_naive",
            "model_version": "1.0",
            "training_data_start": None,
            "training_data_end": None,
            "training_samples": 0,
        }
