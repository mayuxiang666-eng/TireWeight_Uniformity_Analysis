import os
import sys
import duckdb
import pandas as pd

print("=" * 80)
print("TESTING ETL & BACKEND MODIFICATIONS")
print("=" * 80)

# Add backend directory to sys.path
backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 1. Test watermark calculation
from etl.fetch_data import get_watermark_from_parquet, SELECT_QUERY, SELECT_QUERY_INCREMENTAL
print("1. Watermark test:")
wm = get_watermark_from_parquet(r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100.parquet")
print("   Calculated Watermark:", wm)

print("\n2. SELECT_QUERY check:")
assert "tu_first_loc_timestamp" in SELECT_QUERY
assert "tu_first_shift_date" not in SELECT_QUERY
print("   [OK] SELECT_QUERY has tu_first_loc_timestamp and does not have tu_first_shift_date.")

assert "tu_first_loc_timestamp" in SELECT_QUERY_INCREMENTAL
assert "tu_first_shift_date" not in SELECT_QUERY_INCREMENTAL
print("   [OK] SELECT_QUERY_INCREMENTAL has tu_first_loc_timestamp and does not have tu_first_shift_date.")

# 3. Test main.py DuckDB reload and queries
from main import db_conn, reload_duckdb_data, qry

print("\n3. Testing main.py DuckDB reload:")
ok = reload_duckdb_data()
print("   Reload successful:", ok)

# Test daily query
daily_res = qry("""
    SELECT 
        TRY_CAST(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) AS DATE) as dt,
        COUNT(*) as cnt
    FROM clean_yield
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 5
""")
print("\n4. Daily aggregation via tu_first_loc_timestamp:")
print(pd.DataFrame(daily_res))

# Test hourly query on recent date
hourly_res = qry("""
    SELECT 
        STRFTIME(DATE_TRUNC('hour', TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)), '%Y-%m-%d %H:00') as hr,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE TRY_CAST(tu_first_loc_timestamp AS DATE) = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY 1
""")
print("\n5. Hourly aggregation for 2026-08-17 via tu_first_loc_timestamp:")
print(pd.DataFrame(hourly_res))

# Test minute query
min_res = qry("""
    SELECT 
        STRFTIME(DATE_TRUNC('minute', TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)), '%Y-%m-%d %H:%M') as minute_bin,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE TRY_CAST(tu_first_loc_timestamp AS DATE) = DATE '2026-08-17'
    GROUP BY 1
    ORDER BY 1
    LIMIT 10
""")
print("\n6. Minute aggregation for 2026-08-17 via tu_first_loc_timestamp:")
print(pd.DataFrame(min_res))

print("\n" + "=" * 80)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
print("=" * 80)
