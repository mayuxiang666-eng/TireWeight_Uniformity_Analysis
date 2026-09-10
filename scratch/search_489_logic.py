import duckdb
import pandas as pd
import json

p_clean = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100_cleaned.parquet"
p_raw = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100.parquet"

con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{p_clean}')")

print("=" * 80)
print("CHECKING ALL SQL PATTERNS FOR 2026-08-17")
print("=" * 80)

# 1. Total records on 2026-08-17 by different date columns
date_cols = ['tu_first_shift_date', 'gt_loc_timestamp', 'ct_loc_timestamp', 'bead_loc_timestamp', 'tread_loc_timestamp', 'inner_liner_loc_timestamp', 'sidewall_loc_timestamp', 'first_breaker_loc_timestamp', 'second_breaker_loc_timestamp', 'first_ply_loc_timestamp', 'second_ply_loc_timestamp', 'wound_cap_ply1_loc_timestamp', 'wound_cap_ply2_loc_timestamp']

for dc in date_cols:
    cnt = con.execute(f"""
        SELECT COUNT(*) FROM clean_yield
        WHERE TRY_CAST(TRY_CAST({dc} AS TIMESTAMP) AS DATE) = DATE '2026-08-17'
    """).fetchone()[0]
    print(f"Date col [{dc:30s}]: {cnt} records")

# 2. Let's check CPK trend / daily trend on 2026-08-17
print("\n--- Daily trend SQL on clean_yield ---")
trend_sql = """
    SELECT 
        tu_first_shift_date::DATE as dt,
        COUNT(*) as total,
        SUM(CASE WHEN rfppwc_first IS NOT NULL THEN 1 ELSE 0 END) as rfpp_count,
        SUM(CASE WHEN rfh1wc_first IS NOT NULL THEN 1 ELSE 0 END) as rfh1_count,
        SUM(CASE WHEN cony_first IS NOT NULL THEN 1 ELSE 0 END) as cony_count,
        SUM(CASE WHEN tire_weight_actual_first IS NOT NULL AND tire_weight_target_first IS NOT NULL THEN 1 ELSE 0 END) as weight_count
    FROM clean_yield
    WHERE tu_first_shift_date::DATE >= DATE '2026-08-10'
    GROUP BY 1
    ORDER BY 1 DESC
"""
print(con.execute(trend_sql).df())

# 3. Let's check Sankey / Best Process / Combination Tree / Machines / etc.
print("\n--- Sankey / Machine queries on 2026-08-17 ---")
for dt_field in ['tu_first_shift_date', 'ct_loc_timestamp']:
    # Machines with tb, gt, ct, tu
    sankey_cnt = con.execute(f"""
        SELECT COUNT(*) 
        FROM clean_yield
        WHERE {dt_field}::DATE = DATE '2026-08-17'
          AND tb_first_workcenter IS NOT NULL
          AND gt_workcenter IS NOT NULL
          AND ct_workcenter IS NOT NULL
          AND tu_first_workcenter IS NOT NULL
    """).fetchone()[0]
    print(f"Full 4-process chain (tb, gt, ct, tu) using {dt_field}: {sankey_cnt}")

# 4. Search for any query result or count that equals 489
print("\n--- SEARCH FOR ANY FILTER / COMBINATION EQUALING 489 ---")
# Let's test combinations of workcenters, shops, articles, machines, shifts, hours, etc.
# Check hourly breakdown on 2026-08-17
print("\nHourly breakdown of 2026-08-17:")
print(con.execute("""
    SELECT 
        EXTRACT(hour FROM TRY_CAST(tu_first_shift_date AS TIMESTAMP)) as hr,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY 1
""").df())

print("\nGT timestamp hourly breakdown of 2026-08-17:")
print(con.execute("""
    SELECT 
        EXTRACT(hour FROM TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as hr,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE TRY_CAST(gt_loc_timestamp AS DATE) = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY 1
""").df())

print("\nCT timestamp hourly breakdown of 2026-08-17:")
print(con.execute("""
    SELECT 
        EXTRACT(hour FROM TRY_CAST(ct_loc_timestamp AS TIMESTAMP)) as hr,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE TRY_CAST(ct_loc_timestamp AS DATE) = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY 1
""").df())

# Check workcenters on 2026-08-17
print("\ntu_first_workcenter distribution on 2026-08-17:")
print(con.execute("""
    SELECT tu_first_workcenter, COUNT(*) as cnt
    FROM clean_yield
    WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY cnt DESC
""").df())

print("\nct_workcenter distribution on 2026-08-17:")
print(con.execute("""
    SELECT ct_workcenter, COUNT(*) as cnt
    FROM clean_yield
    WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY cnt DESC
    LIMIT 10
""").df())

