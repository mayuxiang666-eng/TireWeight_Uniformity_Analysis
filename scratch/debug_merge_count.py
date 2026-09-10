import duckdb, os, sys

con = duckdb.connect()
cgrs_p = 'd:/Ava/untitled1/untitled1_v2/backend/data/cgrs_data/*.parquet'
yield_p = 'd:/Ava/untitled1/untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet'

# Query raw events
ev_df = con.execute(f"""
    SELECT 
        COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) as event_time,
        ParameterLocalName,
        TechOffsetHistoryValueFrom,
        TechOffsetHistoryValueTo
    FROM read_parquet('{cgrs_p}', union_by_name=True)
    WHERE Workcenter IN ('TB252', 'TB152') AND (CAST(TechOffsetHistoryLocalDate AS VARCHAR) LIKE '2026-08-17%' OR CAST(TechOffsetLocalDate AS VARCHAR) LIKE '2026-08-17%')
    ORDER BY event_time ASC
""").df()

print("CGRS raw events for TB252 on 2026-08-17:")
print(ev_df.to_string())

# Query production timestamps of clean_yield around 08:00 to 13:00 for TB252
yield_df = con.execute(f"""
    SELECT 
        gt_loc_timestamp,
        barcode,
        tu_first_loc_timestamp
    FROM read_parquet('{yield_p}')
    WHERE gt_workcenter IN ('TB152', 'TB252')
      AND TRY_CAST(tu_first_loc_timestamp AS DATE) = '2026-08-17'::DATE
    ORDER BY TRY_CAST(gt_loc_timestamp AS TIMESTAMP) ASC
""").df()

print("\nYield samples count on 2026-08-17:", len(yield_df))
print(yield_df.head(10).to_string())

# Check sample count between 08:26:59 and 08:46:03
t1 = '2026-08-17 08:26:59.280'
t2 = '2026-08-17 08:46:03.300'
t3 = '2026-08-17 12:20:22.877'

cnt_1_2 = con.execute(f"""
    SELECT COUNT(*) 
    FROM read_parquet('{yield_p}')
    WHERE gt_workcenter IN ('TB152', 'TB252')
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) >= '{t1}'::TIMESTAMP
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) < '{t2}'::TIMESTAMP
""").fetchone()[0]

cnt_2_3 = con.execute(f"""
    SELECT COUNT(*) 
    FROM read_parquet('{yield_p}')
    WHERE gt_workcenter IN ('TB152', 'TB252')
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) >= '{t2}'::TIMESTAMP
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) < '{t3}'::TIMESTAMP
""").fetchone()[0]

print(f"\nSamples between Event 1 (08:26) and Event 2 (08:46): {cnt_1_2}")
print(f"Samples between Event 2 (08:46) and Event 3 (12:20): {cnt_2_3}")

# Also check timestamps of GT vs TU!
gt_1_2 = con.execute(f"""
    SELECT barcode, gt_loc_timestamp, tu_first_loc_timestamp
    FROM read_parquet('{yield_p}')
    WHERE gt_workcenter IN ('TB152', 'TB252')
      AND TRY_CAST(tu_first_loc_timestamp AS DATE) = '2026-08-17'::DATE
    ORDER BY TRY_CAST(gt_loc_timestamp AS TIMESTAMP) ASC
""").df()
print("\nAll GT timestamps vs CGRS event timestamps:")
print(gt_1_2.to_string())
