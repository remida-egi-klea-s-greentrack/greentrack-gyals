"""DATA-02: Clean bronze data and write the silver Iceberg table."""
import argparse
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

_HERE = Path(__file__).resolve()
# On Glue the script runs from a temporary folder, so fall back to the current one.
REPO = _HERE.parents[2] if len(_HERE.parents) > 2 else Path.cwd()
BRONZE_PATH = f"file://{REPO}/data/lakehouse/bronze/household_power"
WAREHOUSE = f"file://{REPO}/data/lakehouse/warehouse"

# Original column name -> clean snake_case name
NUMERIC_COLUMNS = {
    "Global_active_power": "global_active_power",
    "Global_reactive_power": "global_reactive_power",
    "Voltage": "voltage",
    "Global_intensity": "global_intensity",
    "Sub_metering_1": "sub_metering_1",
    "Sub_metering_2": "sub_metering_2",
    "Sub_metering_3": "sub_metering_3",
}


# Glue Data Quality rules for the silver table (DQDL), run by the Glue job after the write.
# Null rate: the raw file has about 1.25 % missing readings, so completeness must stay above 98 %.
# Ranges (UCI dataset description): active power up to ~11 kW, voltage ~223-254 V, sub-meters 0-88 Wh.
# Duplicates: exactly one row per timestamp.
# Ranges count non-null values outside the range (nulls are covered by Completeness): ColumnValues with a
# threshold returned NULL on these columns in the first AWS run (13 Nov 2026), so CustomSql is used instead.
DQ_RULESET = """Rules = [
    RowCount > 1000000,
    IsComplete "timestamp",
    IsUnique "timestamp",
    Completeness "global_active_power" > 0.98,
    Completeness "voltage" > 0.98,
    CustomSql "select count(*) from primary where global_active_power < 0 or global_active_power > 15" = 0,
    CustomSql "select count(*) from primary where voltage < 200 or voltage > 260" = 0,
    CustomSql "select count(*) from primary where sub_metering_1 < 0 or sub_metering_1 > 100" = 0,
    CustomSql "select count(*) from primary where sub_metering_2 < 0 or sub_metering_2 > 100" = 0,
    CustomSql "select count(*) from primary where sub_metering_3 < 0 or sub_metering_3 > 100" = 0
]"""
DQ_CONTEXT = "silver_household_power"  # name of the evaluation in the Glue Data Quality results


def parse_args():
    """Settings. With no arguments it runs locally; the Glue job passes S3 paths and catalog names."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", choices=["local", "glue"], default="local")
    parser.add_argument("--bronze_path", default=BRONZE_PATH)
    parser.add_argument("--warehouse", default=WAREHOUSE)
    parser.add_argument("--silver_db", default="silver")
    args, _unknown = parser.parse_known_args()  # Glue also passes its own arguments
    return args


def build_spark(args) -> SparkSession:
    """Spark with Iceberg. The catalog alias is "local" in both environments:
    locally its tables are folders in the warehouse; on AWS they are registered
    in the Glue Data Catalog and stored in S3."""
    builder = (
        SparkSession.builder.appName("greentrack-silver")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.warehouse", args.warehouse)
        .config("spark.sql.session.timeZone", "UTC")
    )
    if args.catalog == "glue":
        builder = (
            builder.config("spark.sql.catalog.local.catalog-impl",
                           "org.apache.iceberg.aws.glue.GlueCatalog")
            .config("spark.sql.catalog.local.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        )
    else:
        builder = builder.config("spark.sql.catalog.local.type", "hadoop")
    return builder.getOrCreate()


def clean(bronze):
    df = bronze

    # 1. Date + Time -> one timestamp
    df = df.withColumn(
        "timestamp",
        F.to_timestamp(F.concat_ws(" ", "Date", "Time"), "d/M/yyyy HH:mm:ss"),
    )

    # 2 + 3. "?" or empty -> null, then text -> number
    for raw, clean_name in NUMERIC_COLUMNS.items():
        df = df.withColumn(
            clean_name,
            F.when(F.col(raw).isin("?", ""), None).otherwise(F.col(raw)).cast("double"),
        )

    # Rows whose date/time could not be read are unusable
    df = df.filter(F.col("timestamp").isNotNull())

    # 4. Remove duplicate timestamps: keep the most recently loaded row
    latest_first = Window.partitionBy("timestamp").orderBy(F.col("load_timestamp").desc())
    df = (
        df.withColumn("row_num", F.row_number().over(latest_first))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )

    # Partition columns + lineage
    df = (
        df.withColumn("year", F.year("timestamp"))
        .withColumn("month", F.month("timestamp"))
        .withColumn("load_timestamp", F.to_timestamp("load_timestamp"))
    )

    return df.select(
        "timestamp",
        *NUMERIC_COLUMNS.values(),
        "year",
        "month",
        "source_file",
        "load_timestamp",
    )


def failed_rules(outcomes):
    """Rules that did not pass. outcomes: rows with "Rule", "Outcome" and "FailureReason" (Glue DQ output)."""
    return [(r["Rule"], r["FailureReason"]) for r in outcomes if r["Outcome"] != "Passed"]


def run_data_quality(spark, silver):
    """Evaluate DQ_RULESET on the silver rows with Glue Data Quality (Glue only).

    Results are published to the Glue Data Quality results and CloudWatch metrics, and printed;
    a failed rule is reported, it does not stop the pipeline (gold has its own blocking checks).
    """
    from awsglue.context import GlueContext
    from awsglue.dynamicframe import DynamicFrame
    from awsgluedq.transforms import EvaluateDataQuality

    glue = GlueContext(spark.sparkContext)
    outcomes = EvaluateDataQuality.apply(
        frame=DynamicFrame.fromDF(silver, glue, "silver"),
        ruleset=DQ_RULESET,
        publishing_options={
            "dataQualityEvaluationContext": DQ_CONTEXT,
            "enableDataQualityCloudWatchMetrics": True,
            "enableDataQualityResultsPublishing": True,
        },
    ).toDF().collect()

    print("\n===== SILVER DATA QUALITY =====")
    for r in outcomes:
        print(f"{r['Outcome']:<7} {r['Rule']}")
    failed = failed_rules(outcomes)
    print(f"{len(outcomes) - len(failed)}/{len(outcomes)} rules passed")
    for rule, reason in failed:
        print(f"FAILED {rule}: {reason}")
    return failed


def main():
    args = parse_args()
    spark = build_spark(args)
    silver_table = f"local.{args.silver_db}.household_power"
    spark.sparkContext.setLogLevel("WARN")

    bronze = spark.read.parquet(args.bronze_path)
    bronze_rows = bronze.count()

    silver = clean(bronze).cache()
    silver_rows = silver.count()

    # 5. Write the Iceberg table, partitioned by year and month
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS local.{args.silver_db}")
    silver.writeTo(silver_table).partitionedBy(F.col("year"), F.col("month")).createOrReplace()

    # Short quality report
    print("\n===== SILVER REPORT =====")
    print(f"Bronze rows:              {bronze_rows:,}")
    print(f"Silver rows:              {silver_rows:,}")
    print(f"Dropped (bad time/dupes): {bronze_rows - silver_rows:,}")
    for name in NUMERIC_COLUMNS.values():
        nulls = silver.filter(F.col(name).isNull()).count()
        print(f"Nulls in {name:<22} {nulls:,}")
    print(f"Iceberg table rows:       {spark.table(silver_table).count():,}")
    spark.table(silver_table).orderBy("timestamp").show(5, truncate=False)

    if args.catalog == "glue":  # Glue Data Quality exists only in the Glue runtime
        run_data_quality(spark, silver)

    spark.stop()


if __name__ == "__main__":
    main()