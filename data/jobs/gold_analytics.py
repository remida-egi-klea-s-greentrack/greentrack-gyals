"""DATA-04: Run analytical SQL queries against the local gold Iceberg tables."""
from pathlib import Path

from pyspark.sql import SparkSession

REPO = Path(__file__).resolve().parents[2]
WAREHOUSE = f"file://{REPO}/data/lakehouse/warehouse"

QUERIES = {
    "Top 10 highest-consumption days": """
        SELECT date, ROUND(global_active_power_kwh, 2) AS total_kwh,
               peak_hour, ROUND(peak_hour_kwh, 2) AS peak_hour_kwh
        FROM local.gold.gold_daily_consumption
        WHERE complete
        ORDER BY global_active_power_kwh DESC
        LIMIT 10
    """,
    "Average hourly use: weekday vs weekend": """
        SELECT day_type,
               ROUND(SUM(avg_kwh * hours_counted) / SUM(hours_counted), 3) AS avg_kwh_per_hour
        FROM local.gold.gold_peak_hour_stats
        GROUP BY day_type
    """,
    "Busiest hour of the day (weekday vs weekend)": """
        SELECT day_type, hour_of_day, avg_kwh
        FROM (
            SELECT day_type, hour_of_day, avg_kwh,
                   ROW_NUMBER() OVER (PARTITION BY day_type ORDER BY avg_kwh DESC) AS rank
            FROM local.gold.gold_peak_hour_stats
        ) ranked
        WHERE rank = 1
    """,
    "Consumption per year (complete hours only)": """
        SELECT year, ROUND(SUM(total_kwh), 1) AS total_kwh, SUM(complete_hours) AS complete_hours
        FROM local.gold.gold_submetering_monthly
        GROUP BY year
        ORDER BY year
    """,
    "Highest and lowest month": """
        (SELECT 'highest' AS which, year, month, ROUND(total_kwh, 1) AS total_kwh
         FROM local.gold.gold_submetering_monthly ORDER BY total_kwh DESC LIMIT 1)
        UNION ALL
        (SELECT 'lowest' AS which, year, month, ROUND(total_kwh, 1) AS total_kwh
         FROM local.gold.gold_submetering_monthly ORDER BY total_kwh ASC LIMIT 1)
    """,
    "Where the electricity goes (whole dataset)": """
        SELECT ROUND(SUM(kitchen_kwh) / SUM(total_kwh) * 100, 1) AS kitchen_pct,
               ROUND(SUM(laundry_kwh) / SUM(total_kwh) * 100, 1) AS laundry_pct,
               ROUND(SUM(water_heater_ac_kwh) / SUM(total_kwh) * 100, 1) AS water_heater_ac_pct,
               ROUND(SUM(other_kwh) / SUM(total_kwh) * 100, 1) AS other_pct
        FROM local.gold.gold_submetering_monthly
    """,
    "Data completeness": """
        SELECT COUNT(*) AS hours,
               SUM(CASE WHEN complete THEN 1 ELSE 0 END) AS complete_hours,
               ROUND(AVG(CASE WHEN complete THEN 1.0 ELSE 0.0 END) * 100, 2) AS complete_pct
        FROM local.gold.gold_hourly_consumption
    """,
}


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("greentrack-gold-analytics")
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", WAREHOUSE)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    for title, sql in QUERIES.items():
        print(f"\n===== {title} =====")
        spark.sql(sql).show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()