import duckdb
from datetime import datetime

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

col = 'tread_workcenter'
indicator_col = 'rfh1wc_first'
article10 = '0312050000'
target_date = '2026-07-13'

sql = f"""
WITH spec_stats AS (
    SELECT 
        '{col}' AS workcenter_col,
        {col} AS machine,
        COUNT(*) AS spec_n,
        AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_avg,
        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_std
    FROM clean_yield
    WHERE {col} IS NOT NULL AND article10 = ? AND ct_shiftdate::DATE = ?
    GROUP BY 1, 2
),
all_stats AS (
    SELECT 
        '{col}' AS workcenter_col,
        {col} AS machine,
        COUNT(*) AS all_n,
        AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS all_avg,
        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS all_std
    FROM clean_yield
    WHERE {col} IS NOT NULL AND ct_shiftdate::DATE = ?
    GROUP BY 1, 2
)
SELECT 
    s.workcenter_col,
    s.machine,
    s.spec_n,
    s.spec_avg + 3.0 * COALESCE(s.spec_std, 0.0) AS spec_avg_3sigma,
    a.all_n,
    a.all_avg + 3.0 * COALESCE(a.all_std, 0.0) AS all_avg_3sigma
FROM spec_stats s
JOIN all_stats a ON s.workcenter_col = a.workcenter_col AND s.machine = a.machine
"""

res = db_conn.execute(sql, [article10, target_date, target_date]).fetchall()
print("Results:", res)
