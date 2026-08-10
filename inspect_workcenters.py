import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

col_sql = """
    SELECT column_name
    FROM (DESCRIBE SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet') LIMIT 1)
    WHERE column_name LIKE '%workcenter%'
"""
cols = [r[0] for r in conn.execute(col_sql).fetchall()]
print("Workcenter cols:", cols)

# Inspect a sample row for workcenter columns and tu / tu_first
sql = """
SELECT article10, tu_first_workcenter, ct_workcenter, tu_first_lot, AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_rfpp
FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')
WHERE article10 = '0312423000'
GROUP BY 1, 2, 3, 4
LIMIT 5
"""
print(conn.execute(sql).fetchall())
