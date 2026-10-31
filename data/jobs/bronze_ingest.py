"""DATA-01: Ingest the raw UCI CSV into the bronze layer as Parquet."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BRONZE_DIR = Path("data/lakehouse/bronze/household_power")


def ingest(raw_file: Path) -> Path:
    # Read everything as text, exactly as received: no cleaning in bronze.
    df = pd.read_csv(raw_file, sep=";", dtype=str, keep_default_na=False)

    # Ingestion metadata so every row is traceable.
    df["source_file"] = raw_file.name
    df["load_timestamp"] = datetime.now(timezone.utc).isoformat()

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = BRONZE_DIR / f"{raw_file.stem}.parquet"
    df.to_parquet(out_file, index=False)

    print(f"Rows written: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"Output: {out_file}")
    return out_file


if __name__ == "__main__":
    ingest(Path(sys.argv[1]))