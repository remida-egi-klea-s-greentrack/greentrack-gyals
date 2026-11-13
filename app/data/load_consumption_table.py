"""Load Gold hourly consumption into the DynamoDB consumption table read by GET /consumption.

Reads the Gold CSV export (s3://<GOLD_BUCKET>/exports/gold_hourly_consumption_csv/, local fallback)
and writes every complete hour as one item: household_id + timestamp, plus the contract fields.

    python -m app.data.load_consumption_table --table g2-greentrack-production-consumption

Variables: args.table - target table; args.household_id - partition key value;
args.dry_run - count items without writing.
"""
import argparse
from decimal import Decimal

from app.adapters.gold_loader import _hourly_record, load_csv_rows


def to_item(record, household_id):
    """Contract record -> DynamoDB item (floats as Decimal, nulls dropped)."""
    item = {"household_id": household_id}
    for key, value in record.items():
        if value is None:
            continue
        item[key] = Decimal(str(value)) if isinstance(value, float) else value
    return item


def complete_items(rows, household_id):
    """Items for the complete hours only (the API serves complete hours)."""
    records = (_hourly_record(r) for r in rows)
    return [to_item(r, household_id) for r in records if r["complete"]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--household-id", dest="household_id", default="household-1")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    args = parser.parse_args()

    items = complete_items(load_csv_rows("gold_hourly_consumption"), args.household_id)
    print(f"{len(items):,} complete hours, {items[0]['timestamp']} to {items[-1]['timestamp']}" if items else "no items")
    if args.dry_run or not items:
        return

    import boto3
    table = boto3.resource("dynamodb").Table(args.table)
    with table.batch_writer(overwrite_by_pkeys=["household_id", "timestamp"]) as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"Wrote {len(items):,} items to {args.table}")


if __name__ == "__main__":
    main()
