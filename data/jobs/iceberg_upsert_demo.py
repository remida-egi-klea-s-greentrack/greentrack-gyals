"""DATA-04: Demonstrate an Iceberg upsert, time travel and rollback on a silver table."""
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

REPO = Path(__file__).resolve().parents[2]
WAREHOUSE = f"file://{REPO}/data/lakehouse/warehouse"
SILVER_TABLE = "local.silver.household_power"
DEMO_TABLE = "local.silver.household_power_upsert_demo"

NUMERIC_COLUMNS = [
    "global_active_power",
    "global_reactive_power",
    "voltage",
    "global_intensity",
    "sub_metering_1",
    "sub_metering_2",
    "sub_metering_3",
]


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("greentrack-iceberg-demo")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", WAREHOUSE)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def latest_snapshot_id(spark, table):
    """The id of the newest version of an Iceberg table."""
    return spark.sql(
        f"SELECT snapshot_id FROM {table}.snapshots ORDER BY committed_at DESC LIMIT 1"
    ).first()["snapshot_id"]


def build_update_batch(demo):
    """A small 'new file': 3 corrected minutes (were null) + 3 brand-new minutes."""
    corrections = demo.filter(F.col("global_active_power").isNull()).orderBy("timestamp").limit(3)
    demo_values = {
        "global_active_power": 1.5,
        "global_reactive_power": 0.1,
        "voltage": 240.0,
        "global_intensity": 6.2,
        "sub_metering_1": 0.0,
        "sub_metering_2": 1.0,
        "sub_metering_3": 17.0,
    }
    for column, value in demo_values.items():
        corrections = corrections.withColumn(column, F.lit(value))

    # New rows: copy the last 3 minutes and move them 3 minutes later (after the data ends).
    new_rows = (
        demo.orderBy(F.col("timestamp").desc())
        .limit(3)
        .withColumn("timestamp", F.col("timestamp") + F.expr("INTERVAL 3 MINUTES"))
        .withColumn("year", F.year("timestamp"))
        .withColumn("month", F.month("timestamp"))
    )

    batch = corrections.unionByName(new_rows)
    return (
        batch.withColumn("source_file", F.lit("demo_correction_batch.txt"))
        .withColumn("load_timestamp", F.current_timestamp())
    )


def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    # 1. Fresh copy of silver to experiment on.
    spark.sql(f"""
        CREATE OR REPLACE TABLE {DEMO_TABLE}
        USING iceberg
        PARTITIONED BY (year, month)
        AS SELECT * FROM {SILVER_TABLE}
    """)
    rows_before = spark.table(DEMO_TABLE).count()
    snapshot_before = latest_snapshot_id(spark, DEMO_TABLE)

    # 2. Build the small update batch.
    batch = build_update_batch(spark.table(DEMO_TABLE)).cache()
    corrected_times = [row["timestamp"] for row in batch.orderBy("timestamp").limit(3).collect()]
    batch.createOrReplaceTempView("updates")
    print("\n===== UPDATE BATCH (3 corrections + 3 new minutes) =====")
    batch.select("timestamp", "global_active_power", "voltage").orderBy("timestamp").show(truncate=False)

    # 3. UPSERT: update rows whose timestamp exists, insert the others.
    spark.sql(f"""
        MERGE INTO {DEMO_TABLE} AS target
        USING updates AS source
        ON target.timestamp = source.timestamp
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    rows_after = spark.table(DEMO_TABLE).count()
    snapshot_after = latest_snapshot_id(spark, DEMO_TABLE)

    # 4. TIME TRAVEL: read the table as it was before the merge.
    old_version = spark.sql(f"SELECT * FROM {DEMO_TABLE} VERSION AS OF {snapshot_before}")
    rows_old_version = old_version.count()

    print("\n===== CORRECTED MINUTES: BEFORE (time travel) vs AFTER =====")
    old_version.filter(F.col("timestamp").isin(corrected_times)) \
        .select("timestamp", "global_active_power", "source_file").orderBy("timestamp").show(truncate=False)
    spark.table(DEMO_TABLE).filter(F.col("timestamp").isin(corrected_times)) \
        .select("timestamp", "global_active_power", "source_file").orderBy("timestamp").show(truncate=False)

    print("===== TABLE HISTORY (one row per version) =====")
    spark.sql(f"SELECT snapshot_id, committed_at, operation FROM {DEMO_TABLE}.snapshots "
              "ORDER BY committed_at").show(truncate=False)

    # 5. ROLLBACK: undo the merge by going back to the earlier snapshot.
    spark.sql(f"CALL local.system.rollback_to_snapshot('silver.household_power_upsert_demo', "
              f"{snapshot_before})")
    rows_after_rollback = spark.table(DEMO_TABLE).count()

    # 6. Checks: stop with an error if anything behaved unexpectedly.
    still_null = spark.sql(
        f"SELECT * FROM {DEMO_TABLE} VERSION AS OF {snapshot_after}"
    ).filter(F.col("timestamp").isin(corrected_times) & F.col("global_active_power").isNull()).count()

    problems = []
    if rows_after != rows_before + 3:
        problems.append(f"expected {rows_before + 3} rows after merge, got {rows_after}")
    if still_null:
        problems.append("corrected minutes are still null after the merge")
    if rows_old_version != rows_before:
        problems.append("time travel did not return the original row count")
    if rows_after_rollback != rows_before:
        problems.append("rollback did not restore the original row count")
    if problems:
        raise ValueError("Iceberg demo failed: " + "; ".join(problems))

    print("\n===== DATA-04 ICEBERG REPORT =====")
    print(f"Rows before merge:           {rows_before:,}")
    print(f"Rows after merge:            {rows_after:,}  (3 updated, 3 inserted)")
    print(f"Rows via time travel:        {rows_old_version:,}  (snapshot {snapshot_before})")
    print(f"Rows after rollback:         {rows_after_rollback:,}")
    print("All checks passed. The real silver table was not modified.")

    spark.stop()


if __name__ == "__main__":
    main()