import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
cgrs_path = "untitled1_v2/backend/data/CGRS.csv"

con.execute(f"CREATE TABLE clean_yield AS SELECT * FROM read_parquet('{parquet_path}')")
con.execute(f"""
    CREATE OR REPLACE TABLE cgrs_records AS 
    SELECT 
        *,
        COALESCE(
            TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
            TRY_CAST(SPLIT_PART(TechOffsetLocalDate, ' ', 1) AS DATE)
        ) AS match_date,
        COALESCE(
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y-%m-%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
        ) AS event_timestamp
    FROM read_csv_auto('{cgrs_path}', all_varchar=True)
""")

print("=== 1. Check CGRS event_timestamp parsing ===")
res_cgrs = con.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(event_timestamp) as valid_ts,
        MIN(event_timestamp) as min_ts,
        MAX(event_timestamp) as max_ts
    FROM cgrs_records
""").df()
print(res_cgrs)

print("\n=== 2. Check clean_yield timestamp parsing ===")
res_cy = con.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as valid_gt_ts,
        MIN(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as min_gt_ts,
        MAX(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as max_gt_ts,
        COUNT(TRY_CAST(ct_loc_timestamp AS TIMESTAMP)) as valid_ct_ts
    FROM clean_yield
""").df()
print(res_cy)

print("\n=== 3. Sample comparison for TB224 on 2026-08-10 ===")
time_expr = "COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))"
sample_comp = con.execute(f"""
    SELECT 
        gt_workcenter,
        article10,
        gt_loc_timestamp,
        {time_expr} as parsed_time,
        rfppwc_first
    FROM clean_yield
    WHERE gt_workcenter = 'TB224'
      AND article10 = '0312053000'
      AND {time_expr} >= TIMESTAMP '2026-08-10 09:20:00'
      AND {time_expr} <= TIMESTAMP '2026-08-10 09:30:00'
    ORDER BY {time_expr} ASC
""").df()
print(sample_comp)
