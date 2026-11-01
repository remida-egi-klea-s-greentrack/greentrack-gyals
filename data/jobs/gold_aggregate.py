"""DATA-03: Build the gold tables from the silver Iceberg table."""
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

REPO = Path(__file__).resolve().parents[2]
WAREHOUSE = f"file://{REPO}/data/lakehouse/warehouse"
EXPORT_DIR = f"file://{REPO}/data/lakehouse/exports"
SILVER_TABLE = "local.silver.household_power"

SUB_METERS = {
    "sub_metering_1": "sub_metering_1_kwh",  # kitchen
    "sub_metering_2": "sub_metering_2_kwh",  # laundry
    "sub_metering_3": "sub_metering_3_kwh",  # water heater and AC
}
KWH_COLUMNS = ["global_active_power_kwh", *SUB_METERS.values()]


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("greentrack-gold")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", WAREHOUSE)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def hourly(silver):
    """One row per hour, every hour present, matching contracts/consumption.json."""
    # A minute is valid only if the main meter and all three sub-meters have values.
    valid = (
        F.col("global_active_power").isNotNull()
        & F.col("sub_metering_1").isNotNull()
        & F.col("sub_metering_2").isNotNull()
        & F.col("sub_metering_3").isNotNull()
    )
    minutes = silver.withColumn("hour", F.date_trunc("hour", "timestamp")).withColumn("valid", valid)

    def when_valid(column):
        return F.when(F.col("valid"), F.col(column))

    aggregated = minutes.groupBy("hour").agg(
        F.sum(F.col("valid").cast("int")).alias("minutes_recorded"),
        # kW averaged over one minute -> kWh: sum / 60
        (F.sum(when_valid("global_active_power")) / 60).alias("global_active_power_kwh"),
        # Wh per minute -> kWh: sum / 1000
        *[(F.sum(when_valid(raw)) / 1000).alias(out) for raw, out in SUB_METERS.items()],
    )

    # Full timeline: every hour between the first and the last one, even with no data.
    bounds = aggregated.agg(F.min("hour").alias("first"), F.max("hour").alias("last"))
    spine = bounds.select(
        F.explode(F.sequence("first", "last", F.expr("INTERVAL 1 HOUR"))).alias("hour")
    )

    result = (
        spine.join(aggregated, "hour", "left")
        .withColumn("minutes_recorded", F.coalesce("minutes_recorded", F.lit(0)))
        .withColumn("complete", F.col("minutes_recorded") == 60)
    )
    # Incomplete hours get null values instead of a misleadingly low total.
    for column in KWH_COLUMNS:
        result = result.withColumn(column, F.when(F.col("complete"), F.col(column)))

    return result.select(
        F.col("hour").alias("timestamp"), *KWH_COLUMNS, "minutes_recorded", "complete"
    )


def daily(hourly_df):
    """One row per day, totals and the day's peak hour (complete days only have values)."""
    by_day = hourly_df.withColumn("date", F.to_date("timestamp"))
    peak = F.max_by(F.struct("global_active_power_kwh", "timestamp"), "global_active_power_kwh")
    result = by_day.groupBy("date").agg(
        F.sum(F.col("complete").cast("int")).alias("complete_hours"),
        F.sum("global_active_power_kwh").alias("global_active_power_kwh"),
        *[F.sum(c).alias(c) for c in SUB_METERS.values()],
        peak.alias("peak"),
    )
    result = result.withColumn("complete", F.col("complete_hours") == 24)
    for column in KWH_COLUMNS:
        result = result.withColumn(column, F.when(F.col("complete"), F.col(column)))
    return result.select(
        "date",
        *KWH_COLUMNS,
        F.when(F.col("complete"), F.col("peak.timestamp")).alias("peak_hour"),
        F.when(F.col("complete"), F.col("peak.global_active_power_kwh")).alias("peak_hour_kwh"),
        "complete_hours",
        "complete",
    ).orderBy("date")


def peak_hour_stats(hourly_df):
    """Average and max consumption per hour of day, weekdays vs weekends."""
    complete = hourly_df.filter("complete")
    return (
        complete.withColumn("hour_of_day", F.hour("timestamp"))
        .withColumn(
            "day_type",
            F.when(F.dayofweek("timestamp").isin(1, 7), "weekend").otherwise("weekday"),
        )
        .groupBy("day_type", "hour_of_day")
        .agg(
            F.round(F.avg("global_active_power_kwh"), 4).alias("avg_kwh"),
            F.round(F.max("global_active_power_kwh"), 4).alias("max_kwh"),
            F.count("*").alias("hours_counted"),
        )
        .orderBy("day_type", "hour_of_day")
    )


def submetering_monthly(hourly_df):
    """Monthly breakdown: kitchen, laundry, water heater/AC and the unmetered rest."""
    complete = hourly_df.filter("complete")
    result = (
        complete.groupBy(F.year("timestamp").alias("year"), F.month("timestamp").alias("month"))
        .agg(
            F.sum("global_active_power_kwh").alias("total_kwh"),
            F.sum("sub_metering_1_kwh").alias("kitchen_kwh"),
            F.sum("sub_metering_2_kwh").alias("laundry_kwh"),
            F.sum("sub_metering_3_kwh").alias("water_heater_ac_kwh"),
            F.count("*").alias("complete_hours"),
        )
        .withColumn(
            "other_kwh",
            F.col("total_kwh") - F.col("kitchen_kwh") - F.col("laundry_kwh")
            - F.col("water_heater_ac_kwh"),
        )
    )
    for part in ["kitchen", "laundry", "water_heater_ac", "other"]:
        result = result.withColumn(
            f"{part}_pct", F.round(F.col(f"{part}_kwh") / F.col("total_kwh") * 100, 2)
        )
    return result.orderBy("year", "month")


def check_hourly(hourly_df):
    """Quality assertions: stop the pipeline if the hourly table breaks the contract."""
    total = hourly_df.count()
    distinct = hourly_df.select("timestamp").distinct().count()
    bounds = hourly_df.agg(F.min("timestamp"), F.max("timestamp")).first()
    expected = int((bounds[1] - bounds[0]).total_seconds() // 3600) + 1

    problems = []
    if distinct != total:
        problems.append("duplicate hours")
    if total != expected:
        problems.append(f"missing hours in timeline ({total} rows, expected {expected})")
    if hourly_df.filter(F.col("complete") & F.col("global_active_power_kwh").isNull()).count():
        problems.append("complete hour with null consumption")
    if hourly_df.filter(~F.col("complete") & F.col("global_active_power_kwh").isNotNull()).count():
        problems.append("incomplete hour with a value")
    if hourly_df.filter(F.col("complete") & (F.col("global_active_power_kwh") <= 0)).count():
        problems.append("complete hour with zero or negative consumption")

    if problems:
        raise ValueError("Gold hourly quality check failed: " + "; ".join(problems))
    print(f"Quality checks passed: {total:,} hours, no gaps, no duplicates.")


def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    silver = spark.table(SILVER_TABLE)
    hourly_df = hourly(silver).cache()
    check_hourly(hourly_df)

    tables = {
        "gold_hourly_consumption": hourly_df,
        "gold_daily_consumption": daily(hourly_df),
        "gold_peak_hour_stats": peak_hour_stats(hourly_df),
        "gold_submetering_monthly": submetering_monthly(hourly_df),
    }

    spark.sql("CREATE NAMESPACE IF NOT EXISTS local.gold")
    for name, df in tables.items():
        df.writeTo(f"local.gold.{name}").createOrReplace()
        print(f"Wrote local.gold.{name}: {spark.table(f'local.gold.{name}').count():,} rows")

    # Plain copies of every gold table (Parquet + CSV) for teammates who don't use Spark.
    # timestamp_ntz = timestamp without timezone, as ML's input_data.py expects.
    for name, df in tables.items():
        if "timestamp" in df.columns:
            df = df.withColumn("timestamp", F.col("timestamp").cast("timestamp_ntz")).orderBy("timestamp")
        out = df.coalesce(1)
        out.write.mode("overwrite").parquet(f"{EXPORT_DIR}/{name}")
        out.write.mode("overwrite").option("header", True).csv(f"{EXPORT_DIR}/{name}_csv")
    print("Exported all gold tables to data/lakehouse/exports/")

    summary = hourly_df.agg(
        F.sum(F.col("complete").cast("int")).alias("complete"),
        F.sum((~F.col("complete")).cast("int")).alias("incomplete"),
    ).first()
    print("\n===== GOLD REPORT =====")
    print(f"Complete hours:   {summary['complete']:,}")
    print(f"Incomplete hours: {summary['incomplete']:,}")
    spark.table("local.gold.gold_submetering_monthly").show(3)
    spark.table("local.gold.gold_peak_hour_stats").filter("day_type = 'weekday'").show(24)

    spark.stop()


if __name__ == "__main__":
    main()