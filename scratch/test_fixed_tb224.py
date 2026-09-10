import duckdb
import numpy as np

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
            TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
        ) AS event_timestamp
    FROM read_csv_auto('{cgrs_path}', all_varchar=True)
""")

# Test with COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))
gt_candidates = ['TB224', 'TB124', 'TB24']
gt_placeholders = ",".join(["?"] * len(gt_candidates))
ts = "2026-08-10 09:21:00"
article10 = "0312053000"

time_expr = "COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))"

# Pre-change 50
rows_before = con.execute(f"""
    SELECT 
        TRY_CAST(rfppwc_first AS DOUBLE) as val,
        {time_expr} as t
    FROM clean_yield
    WHERE gt_workcenter IN ({gt_placeholders})
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
      AND {time_expr} < ?::TIMESTAMP
    ORDER BY {time_expr} DESC
    LIMIT 50
""", gt_candidates + [article10, ts]).fetchall()

# Post-change 50
rows_after = con.execute(f"""
    SELECT 
        TRY_CAST(rfppwc_first AS DOUBLE) as val,
        {time_expr} as t
    FROM clean_yield
    WHERE gt_workcenter IN ({gt_placeholders})
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
      AND {time_expr} >= ?::TIMESTAMP
    ORDER BY {time_expr} ASC
    LIMIT 50
""", gt_candidates + [article10, ts]).fetchall()

print(f"Rows before 09:21: count = {len(rows_before)}")
if rows_before:
    vals_b = [r[0] for r in rows_before]
    print(f"  Mean before = {np.mean(vals_b):.3f}, Std before = {np.std(vals_b, ddof=1):.3f}, Time range = {rows_before[-1][1]} to {rows_before[0][1]}")

print(f"Rows after 09:21: count = {len(rows_after)}")
if rows_after:
    vals_a = [r[0] for r in rows_after]
    print(f"  Mean after = {np.mean(vals_a):.3f}, Std after = {np.std(vals_a, ddof=1):.3f}, Time range = {rows_after[0][1]} to {rows_after[-1][1]}")
