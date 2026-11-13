"""Read results from DynamoDB: forecasts and anomalies (ML loader) and hourly consumption
(app/data/load_consumption_table.py)."""
import os
from decimal import Decimal
from typing import Any, Dict, List

HOUSEHOLD_ID = os.environ.get("HOUSEHOLD_ID", "household-1")


def _plain(value: Any) -> Any:
    """DynamoDB returns numbers as Decimal; convert for JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _query_latest(table_env: str, limit: int) -> List[Dict[str, Any]]:
    """Newest `limit` items for the household, returned oldest first."""
    import boto3
    from boto3.dynamodb.conditions import Key

    table_name = os.environ.get(table_env)
    if not table_name:
        raise RuntimeError(f"{table_env} is not set")

    table = boto3.resource("dynamodb").Table(table_name)
    resp = table.query(
        KeyConditionExpression=Key("household_id").eq(HOUSEHOLD_ID),
        ScanIndexForward=False,  # sort key starts with the timestamp -> newest first
        Limit=limit,
    )
    items = [_plain(i) for i in resp.get("Items", [])]
    items.reverse()
    return items


def load_forecast(horizon_hours: int = 24) -> Dict[str, Any]:
    items = _query_latest("DYNAMODB_TABLE_FORECASTS", horizon_hours)
    predictions = [
        {
            "timestamp": i["timestamp"],
            "predicted_kwh": i.get("predicted_kwh"),
            "actual_kwh": i.get("actual_kwh"),
        }
        for i in items
    ]
    return {"unit": "kWh", "household_id": HOUSEHOLD_ID, "predictions": predictions}


def load_anomalies(limit: int = 20) -> Dict[str, Any]:
    items = _query_latest("DYNAMODB_TABLE_ANOMALIES", limit)
    items.reverse()  # list newest first
    anomalies = [
        {
            "timestamp": i.get("timestamp") or i["timestamp_detector"].split("#")[0],
            "detector": i.get("detector"),
            "consumption_kwh": i.get("consumption_kwh"),
            "anomaly_score": i.get("anomaly_score"),
            "severity": i.get("severity", "low"),
        }
        for i in items
    ]
    return {"household_id": HOUSEHOLD_ID, "anomalies": anomalies}


def load_consumption(limit: int = 100) -> Dict[str, Any]:
    """Newest `limit` complete hours from the consumption table, oldest first (contract: consumption.json)."""
    items = _query_latest("DYNAMODB_TABLE_CONSUMPTION", limit)
    records = [{k: v for k, v in i.items() if k != "household_id"} for i in items]
    return {"unit": "kWh", "household_id": HOUSEHOLD_ID, "records": records}
