import duckdb
DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

sql = """
WITH daily_spec AS (
    SELECT 
        article10,
        ct_shiftdate::DATE AS date,
        ANY_VALUE(specissue) AS spec_val
    FROM clean_yield
    WHERE article10 IS NOT NULL AND specissue IS NOT NULL
    GROUP BY 1, 2
),
lagged AS (
    SELECT 
        *,
        LAG(spec_val) OVER (PARTITION BY article10 ORDER BY date) AS prev_spec_val
    FROM daily_spec
)
SELECT * 
FROM lagged 
WHERE prev_spec_val IS NOT NULL AND spec_val != prev_spec_val
LIMIT 10
"""

print(db_conn.execute(sql).df())
