"""Loader for gold layer data exported by Developer A.

Gold exports each table as CSV in S3 (s3://<GOLD_BUCKET>/exports/<table>_csv/*.csv).
We read it with the stdlib csv module + boto3, so the Lambda needs no pandas,
pyarrow or layer.
"""
import csv
import io
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# S3 bucket dhe prefix për gold exports (Developer A)
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "g2-greentrack-gold-886565871385")
GOLD_PREFIX = os.environ.get("GOLD_PREFIX", "exports/")


def get_gold_exports_dir() -> Path:
    """Returns the path to gold exports directory (for local development)."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "lakehouse" / "exports"


def _read_csv_text_from_s3(table_name: str) -> str:
    import boto3

    s3 = boto3.client("s3")
    prefix = f"{GOLD_PREFIX}{table_name}_csv/"
    objects = s3.list_objects_v2(Bucket=GOLD_BUCKET, Prefix=prefix).get("Contents", [])
    key = next((o["Key"] for o in objects if o["Key"].endswith(".csv")), None)
    if key is None:
        raise FileNotFoundError(f"No CSV under s3://{GOLD_BUCKET}/{prefix}")
    return s3.get_object(Bucket=GOLD_BUCKET, Key=key)["Body"].read().decode("utf-8")


def _read_csv_text_local(table_name: str) -> str:
    folder = get_gold_exports_dir() / f"{table_name}_csv"
    files = sorted(folder.glob("*.csv")) if folder.exists() else []
    if not files:
        raise FileNotFoundError(f"No CSV under {folder}")
    return files[0].read_text(encoding="utf-8")


# Cache per Lambda container: thirrjet e ngrohta nuk e rilexojnë CSV-në nga S3.
CACHE_TTL_SECONDS = int(os.environ.get("GOLD_CACHE_TTL_SECONDS", "600"))
_cache: Dict[str, Tuple[float, List[Dict[str, str]]]] = {}


def load_csv_rows(table_name: str) -> List[Dict[str, str]]:
    """Read a gold CSV export as a list of string dicts (cached; S3 first, local fallback)."""
    cached = _cache.get(table_name)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        text = _read_csv_text_from_s3(table_name)
        source = "S3"
    except Exception as s3_err:
        print(f"WARN S3 load failed for {table_name}: {s3_err}")
        text = _read_csv_text_local(table_name)
        source = "local"
    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"Loaded {len(rows)} rows of {table_name} from {source}")
    _cache[table_name] = (time.monotonic(), rows)
    return rows


def _num(value: Optional[str]) -> Optional[float]:
    """Incomplete hours are empty (null) in the CSV."""
    return float(value) if value not in (None, "") else None


def _bool(value: Optional[str]) -> bool:
    return str(value).strip().lower() == "true"


def _hourly_record(r: Dict[str, str]) -> Dict[str, Any]:
    return {
        "timestamp": r["timestamp"],
        "global_active_power_kwh": _num(r.get("global_active_power_kwh")),
        "sub_metering_1_kwh": _num(r.get("sub_metering_1_kwh")),
        "sub_metering_2_kwh": _num(r.get("sub_metering_2_kwh")),
        "sub_metering_3_kwh": _num(r.get("sub_metering_3_kwh")),
        "minutes_recorded": int(float(r.get("minutes_recorded") or 0)),
        "complete": _bool(r.get("complete")),
    }


def load_hourly_consumption(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Most recent `limit` complete hours, oldest first.

    Returns records in the same format as contracts/consumption.json.
    """
    records = [_hourly_record(r) for r in load_csv_rows("gold_hourly_consumption")]
    complete = [r for r in records if r["complete"]]
    complete.sort(key=lambda r: r["timestamp"])
    return complete[-limit:] if limit else complete


def load_daily_consumption(days: int = 30) -> List[Dict[str, Any]]:
    """Most recent `days` complete days from gold daily aggregates, oldest first."""
    records = []
    for r in load_csv_rows("gold_daily_consumption"):
        if not _bool(r.get("complete")):
            continue
        records.append({
            "date": r["date"],
            "global_active_power_kwh": _num(r.get("global_active_power_kwh")),
            "peak_hour": r.get("peak_hour") or None,
            "peak_hour_kwh": _num(r.get("peak_hour_kwh")),
            "complete": True,
        })
    records.sort(key=lambda r: r["date"])
    return records[-days:]


def detect_anomalies_simple(threshold_kwh: float = 5.0) -> List[Dict[str, Any]]:
    """
    Simple anomaly detection: complete hours with consumption above threshold.

    In production, this would use Developer B's ML model.
    """
    try:
        records = [_hourly_record(r) for r in load_csv_rows("gold_hourly_consumption")]
    except Exception as e:
        print(f"WARN could not load gold data for anomalies: {e}")
        return []

    high = [
        r for r in records
        if r["complete"] and r["global_active_power_kwh"] is not None
        and r["global_active_power_kwh"] > threshold_kwh
    ]
    high.sort(key=lambda r: r["global_active_power_kwh"], reverse=True)

    anomalies = []
    for r in high[:20]:
        kwh = r["global_active_power_kwh"]
        severity = "high" if kwh > 6.0 else "medium" if kwh > 5.5 else "low"
        anomalies.append({
            "timestamp": r["timestamp"],
            "global_active_power_kwh": kwh,
            "anomaly_score": round(min(kwh / threshold_kwh, 1.0), 3),
            "severity": severity,
            "reason": f"Consumption {kwh:.2f} kWh above {threshold_kwh} kWh threshold",
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
