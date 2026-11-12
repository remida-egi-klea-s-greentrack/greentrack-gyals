-- DATA-07: Iceberg upsert and time travel in Athena (same idea as data/jobs/iceberg_upsert_demo.py).
-- Run each statement separately in the Athena query editor, workgroup g2-greentrack-analytics.
-- Replace <account> with the AWS account id before running step 1.

-- 1. Copy of the silver table to experiment on (the real silver table is not changed)
CREATE TABLE g2_greentrack_silver.household_power_upsert_demo
WITH (
  table_type   = 'ICEBERG',
  is_external  = false,
  location     = 's3://g2-greentrack-silver-<account>/warehouse/household_power_upsert_demo/',
  partitioning = ARRAY['year', 'month']
)
AS SELECT
  CAST("timestamp" AS timestamp(6)) AS "timestamp",
  global_active_power, global_reactive_power, voltage, global_intensity,
  sub_metering_1, sub_metering_2, sub_metering_3,
  year, month, source_file,
  CAST(load_timestamp AS timestamp(6)) AS load_timestamp
FROM g2_greentrack_silver.household_power;

-- 2. Row count before the merge (expected 2,075,259)
SELECT COUNT(*) AS rows_before FROM g2_greentrack_silver.household_power_upsert_demo;

-- 3. Version history: copy the snapshot_id shown here (the version before the merge)
SELECT snapshot_id, committed_at, operation
FROM "g2_greentrack_silver"."household_power_upsert_demo$snapshots"
ORDER BY committed_at;

-- 4. The 3 minutes that will be corrected (currently null)
SELECT "timestamp", global_active_power, source_file
FROM g2_greentrack_silver.household_power_upsert_demo
WHERE global_active_power IS NULL
ORDER BY "timestamp"
LIMIT 3;

-- 5. UPSERT: 3 corrected minutes (update) + 3 new minutes after the data ends (insert)
MERGE INTO g2_greentrack_silver.household_power_upsert_demo AS target
USING (
  SELECT "timestamp",
         CAST(1.5 AS double) AS global_active_power, CAST(0.1 AS double) AS global_reactive_power,
         CAST(240.0 AS double) AS voltage, CAST(6.2 AS double) AS global_intensity,
         CAST(0.0 AS double) AS sub_metering_1, CAST(1.0 AS double) AS sub_metering_2,
         CAST(17.0 AS double) AS sub_metering_3,
         year, month
  FROM (
    SELECT * FROM g2_greentrack_silver.household_power_upsert_demo
    WHERE global_active_power IS NULL
    ORDER BY "timestamp"
    LIMIT 3
  )
  UNION ALL
  SELECT "timestamp" + INTERVAL '3' MINUTE,
         global_active_power, global_reactive_power, voltage, global_intensity,
         sub_metering_1, sub_metering_2, sub_metering_3,
         CAST(year("timestamp" + INTERVAL '3' MINUTE) AS integer),
         CAST(month("timestamp" + INTERVAL '3' MINUTE) AS integer)
  FROM (
    SELECT * FROM g2_greentrack_silver.household_power_upsert_demo
    ORDER BY "timestamp" DESC
    LIMIT 3
  )
) AS source
ON target."timestamp" = source."timestamp"
WHEN MATCHED THEN UPDATE SET
  global_active_power   = source.global_active_power,
  global_reactive_power = source.global_reactive_power,
  voltage               = source.voltage,
  global_intensity      = source.global_intensity,
  sub_metering_1        = source.sub_metering_1,
  sub_metering_2        = source.sub_metering_2,
  sub_metering_3        = source.sub_metering_3,
  source_file           = 'demo_correction_batch.txt',
  load_timestamp        = CAST(current_timestamp AS timestamp(6))
WHEN NOT MATCHED THEN INSERT (
  "timestamp", global_active_power, global_reactive_power, voltage, global_intensity,
  sub_metering_1, sub_metering_2, sub_metering_3, year, month, source_file, load_timestamp
) VALUES (
  source."timestamp", source.global_active_power, source.global_reactive_power, source.voltage,
  source.global_intensity, source.sub_metering_1, source.sub_metering_2, source.sub_metering_3,
  source.year, source.month, 'demo_correction_batch.txt', CAST(current_timestamp AS timestamp(6))
);

-- 6. Row count after the merge (expected 2,075,262: 3 updated, 3 inserted)
SELECT COUNT(*) AS rows_after FROM g2_greentrack_silver.household_power_upsert_demo;

-- 7. The changed rows now
SELECT "timestamp", global_active_power, source_file, load_timestamp
FROM g2_greentrack_silver.household_power_upsert_demo
WHERE source_file = 'demo_correction_batch.txt'
ORDER BY "timestamp";

-- 8. History now has a second version (the merge)
SELECT snapshot_id, committed_at, operation
FROM "g2_greentrack_silver"."household_power_upsert_demo$snapshots"
ORDER BY committed_at;

-- 9. TIME TRAVEL: the table as it was before the merge
--    Replace <snapshot_before> with the snapshot_id from step 3 (expected 2,075,259)
SELECT COUNT(*) AS rows_in_old_version
FROM g2_greentrack_silver.household_power_upsert_demo FOR VERSION AS OF <snapshot_before>;

-- 10. The same 3 corrected minutes in the old version (still null)
SELECT "timestamp", global_active_power, source_file
FROM g2_greentrack_silver.household_power_upsert_demo FOR VERSION AS OF <snapshot_before>
WHERE global_active_power IS NULL
ORDER BY "timestamp"
LIMIT 3;

