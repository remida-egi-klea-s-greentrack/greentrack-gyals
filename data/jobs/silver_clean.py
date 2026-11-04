"""DATA-02: Clean bronze data and write the silver Iceberg table."""
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

REPO = Path(__file__).resolve().parents[2]
BRONZE_PATH = f"file://{REPO}/data/lakehouse/bronze/household_power"
WAREHOUSE = f"file://{REPO}/data/lakehouse/warehouse"
SILVER_TABLE = "local.silver.household_power"

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


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("greentrack-silver")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", WAREHOUSE)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


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


def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    bronze = spark.read.parquet(BRONZE_PATH)
    bronze_rows = bronze.count()

    silver = clean(bronze).cache()
    silver_rows = silver.count()

    # 5. Write the Iceberg table, partitioned by year and month
    spark.sql("CREATE NAMESPACE IF NOT EXISTS local.silver")
    silver.writeTo(SILVER_TABLE).partitionedBy(F.col("year"), F.col("month")).createOrReplace()

    # Short quality report
    print("\n===== SILVER REPORT =====")
    print(f"Bronze rows:              {bronze_rows:,}")
    print(f"Silver rows:              {silver_rows:,}")
    print(f"Dropped (bad time/dupes): {bronze_rows - silver_rows:,}")
    for name in NUMERIC_COLUMNS.values():
        nulls = silver.filter(F.col(name).isNull()).count()
        print(f"Nulls in {name:<22} {nulls:,}")
    print(f"Iceberg table rows:       {spark.table(SILVER_TABLE).count():,}")
    spark.table(SILVER_TABLE).orderBy("timestamp").show(5, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()