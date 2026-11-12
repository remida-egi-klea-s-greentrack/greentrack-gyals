"""Fill the app's DynamoDB tables with forecasts and anomalies from the inference Lambda.

The dashboard reads precomputed results from DynamoDB (Challenge 1) instead of waiting on SageMaker
behind the API Gateway timeout. This command calls g2-greentrack-ml-inference one week at a time
(its 7-day limit) and writes every hour's forecast and every alert of both detectors.
Writes are idempotent: the same hour (and detector) overwrites the same item.

Usage (AWS credentials in the terminal, from the repo root):
    PYTHONPATH=. python -m ml.inference.load_dynamodb --start 2010-10-01 --end 2010-11-26 [--dry-run]

Variables:
    DEFAULT_*          - table names from infra/main.tf (name prefix includes the environment) and the household
    forecast item      - household_id, timestamp (hour start), predicted_kwh, actual_kwh, forecast_origin, model
    anomaly item       - household_id, timestamp_detector ("2010-01-24T17:00:00#rcf_raw_24"), timestamp, detector,
                         consumption_kwh, anomaly_score (percentile vs 2009), severity
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

from ml.inference.core import MAX_DAYS

DEFAULT_FUNCTION = "g2-greentrack-ml-inference"
DEFAULT_FORECASTS_TABLE = "g2-greentrack-dev-forecasts"
DEFAULT_ANOMALIES_TABLE = "g2-greentrack-dev-anomalies"
DEFAULT_HOUSEHOLD = "household-1"


def windows(start, end):
    """[start, end) split into consecutive windows of at most MAX_DAYS days (ISO midnights)."""
    out, current = [], start
    while current < end:
        stop = min(current + timedelta(days=MAX_DAYS), end)
        out.append({"start": f"{current}T00:00:00", "end": f"{stop}T00:00:00"})
        current = stop
    return out


def _decimal(value):
    """DynamoDB numbers must be Decimal; round to keep items small and readable."""
    return None if value is None else Decimal(str(round(value, 6)))


def _item(fields):
    """Drop empty attributes (DynamoDB has no use for None)."""
    return {k: v for k, v in fields.items() if v is not None}


def items(response, household_id):
    """(forecast items, anomaly items) from one inference Lambda response."""
    actual = {row["timestamp"]: row["consumption_kwh"] for row in response["scores"]}
    forecasts = [_item({
        "household_id": household_id,
        "timestamp": p["timestamp"],
        "predicted_kwh": _decimal(p["predicted_kwh"]),
        "actual_kwh": _decimal(actual.get(p["timestamp"])),
        "forecast_origin": p["forecast_origin"],
        "model": "xgboost",
    }) for p in response["forecast"]["predictions"]]
    anomalies = [_item({
        "household_id": household_id,
        "timestamp_detector": f"{a['timestamp']}#{a['detector']}",
        "timestamp": a["timestamp"],
        "detector": a["detector"],
        "consumption_kwh": _decimal(a["consumption_kwh"]),
        "anomaly_score": _decimal(a["anomaly_score"]),
        "severity": a["severity"],
    }) for a in response["anomalies"]["anomalies"]]
    return forecasts, anomalies


def invoke(lambda_client, function, window):
    response = lambda_client.invoke(FunctionName=function, Payload=json.dumps(window).encode())
    result = json.loads(response["Payload"].read())
    if "error" in result or "errorMessage" in result:
        raise RuntimeError(f"{window}: {result.get('error') or result.get('errorMessage')}")
    return result


def write(table, rows, key):
    with table.batch_writer(overwrite_by_pkeys=["household_id", key]) as batch:
        for row in rows:
            batch.put_item(Item=row)


def main():
    import boto3
    from botocore.config import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2010, 10, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2010, 11, 26), help="exclusive")
    parser.add_argument("--function", default=DEFAULT_FUNCTION)
    parser.add_argument("--forecasts-table", default=DEFAULT_FORECASTS_TABLE)
    parser.add_argument("--anomalies-table", default=DEFAULT_ANOMALIES_TABLE)
    parser.add_argument("--household-id", default=DEFAULT_HOUSEHOLD)
    parser.add_argument("--dry-run", action="store_true", help="call the Lambda, print counts, write nothing")
    args = parser.parse_args()

    # Serverless endpoints may cold-start; no retries, so a slow window is not computed twice.
    lambda_client = boto3.client("lambda", config=Config(read_timeout=200, retries={"total_max_attempts": 1}))
    dynamodb = boto3.resource("dynamodb")
    totals = [0, 0]
    for window in windows(args.start, args.end):
        forecasts, anomalies = items(invoke(lambda_client, args.function, window), args.household_id)
        if not args.dry_run:
            write(dynamodb.Table(args.forecasts_table), forecasts, "timestamp")
            write(dynamodb.Table(args.anomalies_table), anomalies, "timestamp_detector")
        totals[0] += len(forecasts)
        totals[1] += len(anomalies)
        print(f"{window['start'][:10]} .. {window['end'][:10]}: {len(forecasts)} forecasts, {len(anomalies)} anomalies"
              f"{' (dry run)' if args.dry_run else ''}", flush=True)
    print(f"total: {totals[0]} forecasts, {totals[1]} anomalies, generated {datetime.now():%Y-%m-%d %H:%M}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
