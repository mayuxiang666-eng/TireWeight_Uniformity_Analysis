import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_0714_cleaned.parquet"

con = duckdb.connect()

print("Checking table dates:")
res = con.execute(f"SELECT MIN(ct_shiftdate), MAX(ct_shiftdate), COUNT(*) FROM read_parquet('{new_path}')").fetchone()
print(f"Min Date: {res[0]}")
print(f"Max Date: {res[1]}")
print(f"Total Rows: {res[2]}")

con.close()
