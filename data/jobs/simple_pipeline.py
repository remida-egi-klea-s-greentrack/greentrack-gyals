"""Simple data pipeline without Spark - creates gold tables from raw CSV."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
EXPORTS_DIR = REPO / "data" / "lakehouse" / "exports"


def load_and_clean_data(raw_file: Path) -> pd.DataFrame:
    """Load raw UCI data and clean it."""
    print("Loading raw data...")
    df = pd.read_csv(
        raw_file,
        sep=";",
        na_values=["?", ""],
        parse_dates={"timestamp": ["Date", "Time"]},
        dayfirst=True,
        infer_datetime_format=True,
    )
    
    print(f"Loaded {len(df):,} rows")
    
    # Rename columns to snake_case
    df = df.rename(columns={
        "Global_active_power": "global_active_power",
        "Global_reactive_power": "global_reactive_power",
        "Voltage": "voltage",
        "Global_intensity": "global_intensity",
        "Sub_metering_1": "sub_metering_1",
        "Sub_metering_2": "sub_metering_2",
        "Sub_metering_3": "sub_metering_3",
    })
    
    # Remove rows with null timestamp
    df = df[df["timestamp"].notna()].copy()
    
    # Remove duplicates (keep last)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    
    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    print(f"After cleaning: {len(df):,} rows")
    
    return df


def create_hourly_consumption(df: pd.DataFrame) -> pd.DataFrame:
    """Create gold_hourly_consumption table."""
    print("\nCreating hourly consumption...")
    
    # Add hour column
    df = df.copy()
    df["hour"] = df["timestamp"].dt.floor("h")
    
    # Check which minutes are valid (all meters have values)
    df["valid"] = (
        df["global_active_power"].notna()
        & df["sub_metering_1"].notna()
        & df["sub_metering_2"].notna()
        & df["sub_metering_3"].notna()
    )
    
    # Aggregate by hour
    hourly = df.groupby("hour").agg({
        "valid": "sum",  # Count of valid minutes
        "global_active_power": lambda x: x[df.loc[x.index, "valid"]].sum() / 60 if x[df.loc[x.index, "valid"]].sum() > 0 else np.nan,
        "sub_metering_1": lambda x: x[df.loc[x.index, "valid"]].sum() / 1000 if x[df.loc[x.index, "valid"]].sum() > 0 else np.nan,
        "sub_metering_2": lambda x: x[df.loc[x.index, "valid"]].sum() / 1000 if x[df.loc[x.index, "valid"]].sum() > 0 else np.nan,
        "sub_metering_3": lambda x: x[df.loc[x.index, "valid"]].sum() / 1000 if x[df.loc[x.index, "valid"]].sum() > 0 else np.nan,
    }).rename(columns={
        "valid": "minutes_recorded",
        "global_active_power": "global_active_power_kwh",
        "sub_metering_1": "sub_metering_1_kwh",
        "sub_metering_2": "sub_metering_2_kwh",
        "sub_metering_3": "sub_metering_3_kwh",
    })
    
    # Create complete timeline (every hour between first and last)
    first_hour = hourly.index.min()
    last_hour = hourly.index.max()
    all_hours = pd.date_range(first_hour, last_hour, freq="h")
    
    # Reindex to include all hours
    hourly = hourly.reindex(all_hours, fill_value=0)
    hourly.index.name = "timestamp"
    
    # Mark complete hours (60 minutes recorded)
    hourly["complete"] = hourly["minutes_recorded"] == 60
    
    # Set null for incomplete hours
    for col in ["global_active_power_kwh", "sub_metering_1_kwh", "sub_metering_2_kwh", "sub_metering_3_kwh"]:
        hourly.loc[~hourly["complete"], col] = np.nan
    
    hourly = hourly.reset_index()
    
    print(f"Created {len(hourly):,} hourly records")
    print(f"Complete hours: {hourly['complete'].sum():,}")
    print(f"Incomplete hours: {(~hourly['complete']).sum():,}")
    
    return hourly


def create_daily_consumption(hourly: pd.DataFrame) -> pd.DataFrame:
    """Create gold_daily_consumption table."""
    print("\nCreating daily consumption...")
    
    # Add date column
    df = hourly.copy()
    df["date"] = df["timestamp"].dt.date
    
    # Aggregate by day
    daily = df.groupby("date").agg({
        "complete": "sum",
        "global_active_power_kwh": "sum",
        "sub_metering_1_kwh": "sum",
        "sub_metering_2_kwh": "sum",
        "sub_metering_3_kwh": "sum",
    }).rename(columns={"complete": "complete_hours"})
    
    # Find peak hour for each day
    complete_df = df[df["complete"]].copy()
    peak_hours = complete_df.loc[complete_df.groupby(complete_df["timestamp"].dt.date)["global_active_power_kwh"].idxmax()]
    peak_hours = peak_hours.set_index(peak_hours["timestamp"].dt.date)[["timestamp", "global_active_power_kwh"]]
    peak_hours.columns = ["peak_hour", "peak_hour_kwh"]
    
    daily = daily.join(peak_hours)
    
    # Mark complete days (24 complete hours)
    daily["complete"] = daily["complete_hours"] == 24
    
    # Set null for incomplete days
    for col in ["global_active_power_kwh", "sub_metering_1_kwh", "sub_metering_2_kwh", "sub_metering_3_kwh", "peak_hour", "peak_hour_kwh"]:
        daily.loc[~daily["complete"], col] = np.nan
    
    daily = daily.reset_index()
    
    print(f"Created {len(daily):,} daily records")
    
    return daily


def main():
    """Run the simple pipeline."""
    raw_file = REPO / "household_power_consumption.txt"
    
    if not raw_file.exists():
        print(f"Error: {raw_file} not found!")
        return
    
    # Load and clean
    df = load_and_clean_data(raw_file)
    
    # Create gold tables
    hourly = create_hourly_consumption(df)
    daily = create_daily_consumption(hourly)
    
    # Export to Parquet
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("\nExporting to Parquet...")
    hourly_dir = EXPORTS_DIR / "gold_hourly_consumption"
    hourly_dir.mkdir(exist_ok=True)
    hourly.to_parquet(hourly_dir / "data.parquet", index=False)
    print(f"✅ Exported to {hourly_dir}")
    
    daily_dir = EXPORTS_DIR / "gold_daily_consumption"
    daily_dir.mkdir(exist_ok=True)
    daily.to_parquet(daily_dir / "data.parquet", index=False)
    print(f"✅ Exported to {daily_dir}")
    
    print("\n===== PIPELINE COMPLETE =====")
    print(f"Gold tables ready in: {EXPORTS_DIR}")
    print("\nNow restart the backend:")
    print("  python -m app.backend.server")


if __name__ == "__main__":
    main()
