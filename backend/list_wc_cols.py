import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

col_sql = """
    SELECT column_name
    FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
    WHERE column_name LIKE '%workcenter%'
"""
wc_cols = [r[0] for r in db_conn.execute(col_sql).fetchall()]
print("All workcenter columns:", wc_cols)
