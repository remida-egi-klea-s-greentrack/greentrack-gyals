"""DATA-06: Bronze ingestion as a Glue (Spark) job on AWS.

Same rules as bronze_ingest.py (which uses pandas locally): every value is kept
exactly as received (as text, "?" stays "?"), and two metadata columns are added.
Bronze is append-only: each run adds the received file, and silver removes
duplicate timestamps, keeping the most recently loaded row.
"""
import argparse
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_path", required=True, help="s3://.../incoming/<file>.txt")
    parser.add_argument("--bronze_path", required=True, help="s3://.../household_power/")
    args, _unknown = parser.parse_known_args()  # Glue also passes its own arguments
    return args


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("greentrack-bronze").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.read.option("header", True)
        .option("sep", ";")
        .option("inferSchema", False)   # every column stays text
        .option("nullValue", "\u0000")  # never turn "" into null...
        .option("emptyValue", "")       # ...keep empty values as empty text
        .csv(args.raw_path)
    )

    source_file = args.raw_path.rstrip("/").split("/")[-1]
    load_timestamp = datetime.now(timezone.utc).isoformat()

    bronze = (
        raw.withColumn("source_file", F.lit(source_file))
        .withColumn("load_timestamp", F.lit(load_timestamp))
    )
    bronze.write.mode("append").parquet(args.bronze_path)

    print("\n===== BRONZE REPORT =====")
    print(f"Source:       {args.raw_path}")
    print(f"Rows written: {bronze.count():,}")
    print(f"Columns:      {bronze.columns}")
    print(f"Output:       {args.bronze_path}")

    spark.stop()


if __name__ == "__main__":
    main()