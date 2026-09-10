import os
import duckdb
import pandas as pd

pd.set_option('display.max_columns', 50)
pd.set_option('display.width', 1000)

p_raw = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100.parquet"
p_clean = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100_cleaned.parquet"

con = duckdb.connect()

print("=" * 80)
print("1. FILE SIZE AND BASIC INFO")
print("=" * 80)
print(f"Raw file size: {os.path.getsize(p_raw) / (1024*1024):.2f} MB")
print(f"Clean file size: {os.path.getsize(p_clean) / (1024*1024):.2f} MB")

raw_total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p_raw}')").fetchone()[0]
clean_total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p_clean}')").fetchone()[0]
print(f"Raw total rows: {raw_total}")
print(f"Clean total rows: {clean_total}")

print("\n" + "=" * 80)
print("2. DATE RANGE IN BOTH FILES")
print("=" * 80)
print("Raw date stats:")
print(con.execute(f"""
    SELECT 
        MIN(TRY_CAST(tu_first_shift_date AS DATE)) as min_date,
        MAX(TRY_CAST(tu_first_shift_date AS DATE)) as max_date,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN tu_first_shift_date IS NULL THEN 1 END) as null_date_rows
    FROM read_parquet('{p_raw}')
""").df())

print("\nClean date stats:")
print(con.execute(f"""
    SELECT 
        MIN(TRY_CAST(tu_first_shift_date AS DATE)) as min_date,
        MAX(TRY_CAST(tu_first_shift_date AS DATE)) as max_date,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN tu_first_shift_date IS NULL THEN 1 END) as null_date_rows
    FROM read_parquet('{p_clean}')
""").df())

print("\n" + "=" * 80)
print("3. 2026-08-17 SPECIFIC COUNTS")
print("=" * 80)

# Check all possible date representations for 2026-08-17
print("Raw rows on 2026-08-17 (tu_first_shift_date):")
raw_20260817 = con.execute(f"""
    SELECT COUNT(*) 
    FROM read_parquet('{p_raw}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
       OR tu_first_shift_date LIKE '2026-08-17%'
       OR tu_first_shift_date LIKE '2026/08/17%'
""").fetchone()[0]
print(f"  Count: {raw_20260817}")

print("Clean rows on 2026-08-17 (tu_first_shift_date):")
clean_20260817 = con.execute(f"""
    SELECT COUNT(*) 
    FROM read_parquet('{p_clean}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
       OR tu_first_shift_date LIKE '2026-08-17%'
       OR tu_first_shift_date LIKE '2026/08/17%'
""").fetchone()[0]
print(f"  Count: {clean_20260817}")

print("\n" + "=" * 80)
print("4. CHECK OTHER DATE COLUMNS FOR 2026-08-17 IN RAW & CLEAN")
print("=" * 80)
date_cols_raw = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p_raw}') LIMIT 1").fetchall() if 'date' in r[0].lower() or 'timestamp' in r[0].lower()]
print("Date/timestamp columns:", date_cols_raw)

for dc in date_cols_raw:
    try:
        cnt_raw = con.execute(f"""
            SELECT COUNT(*) FROM read_parquet('{p_raw}')
            WHERE TRY_CAST(SUBSTRING(CAST({dc} AS VARCHAR), 1, 10) AS DATE) = DATE '2026-08-17'
        """).fetchone()[0]
        cnt_clean = con.execute(f"""
            SELECT COUNT(*) FROM read_parquet('{p_clean}')
            WHERE TRY_CAST(SUBSTRING(CAST({dc} AS VARCHAR), 1, 10) AS DATE) = DATE '2026-08-17'
        """).fetchone()[0] if dc in [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p_clean}') LIMIT 1").fetchall()] else "N/A"
        print(f"Column '{dc}': Raw={cnt_raw}, Clean={cnt_clean}")
    except Exception as e:
        print(f"Column '{dc}': Error ({e})")

print("\n" + "=" * 80)
print("5. RECENT DATES (LAST 10 DAYS) COUNT BREAKDOWN")
print("=" * 80)
print(con.execute(f"""
    WITH r AS (
        SELECT TRY_CAST(tu_first_shift_date AS DATE) as dt, COUNT(*) as raw_cnt
        FROM read_parquet('{p_raw}')
        GROUP BY dt
    ),
    c AS (
        SELECT TRY_CAST(tu_first_shift_date AS DATE) as dt, COUNT(*) as clean_cnt
        FROM read_parquet('{p_clean}')
        GROUP BY dt
    )
    SELECT 
        COALESCE(r.dt, c.dt) as shift_date,
        COALESCE(r.raw_cnt, 0) as raw_count,
        COALESCE(c.clean_cnt, 0) as clean_count,
        COALESCE(r.raw_cnt, 0) - COALESCE(c.clean_cnt, 0) as diff
    FROM r FULL OUTER JOIN c ON r.dt = c.dt
    WHERE COALESCE(r.dt, c.dt) >= DATE '2026-08-01'
    ORDER BY shift_date DESC
""").df())

