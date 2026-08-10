import duckdb
import numpy as np

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

grain = "daily"
if grain == "daily":
    time_expr = "ct_shiftdate::DATE"
else:
    time_expr = "DATE_TRUNC('week', ct_shiftdate::DATE)"

sql = f"""
WITH spec_daily_stats AS (
    SELECT
        {time_expr} AS time_period,
        "group",
        article10,
        COUNT(*) AS sample_size,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
        COALESCE(ANY_VALUE(standard_rfpp), 
                 CASE "group" 
                     WHEN 'GROUP 1'  THEN 10.5 
                     WHEN 'GROUP 2A' THEN 11.5 
                     WHEN 'GROUP 2B' THEN 12.5 
                     WHEN 'GROUP 3'  THEN 12.5 
                 END) * 10.0 AS usl_rfpp,
        COALESCE(ANY_VALUE(standard_rfh1), 
                 CASE "group" 
                     WHEN 'GROUP 1'  THEN 7.5 
                     WHEN 'GROUP 2A' THEN 8.5 
                     WHEN 'GROUP 2B' THEN 9.0 
                     WHEN 'GROUP 3'  THEN 9.5 
                 END) * 10.0 AS usl_rfh1
    FROM clean_yield
    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
    GROUP BY 1, 2, 3
    HAVING COUNT(*) >= 5
),
spec_cpk AS (
    SELECT
        time_period,
        sample_size,
        CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp,
        CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS cpk_rfh1
    FROM spec_daily_stats
)
SELECT
    time_period,
    SUM(sample_size) AS total_n,
    SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfpp,
    SUM(cpk_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfh1
FROM spec_cpk
GROUP BY 1
ORDER BY 1
"""

try:
    res = db_conn.execute(sql).df()
    print("SQL execution succeeded!")
    print(res.to_string())
except Exception as e:
    print("SQL execution failed:", e)
