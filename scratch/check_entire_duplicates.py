import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

total_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{new_path}')").fetchone()[0]
unique_rows = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM read_parquet('{new_path}'))").fetchone()[0]

print(f"Total Rows: {total_rows}")
print(f"Unique Rows (DISTINCT *): {unique_rows}")
print(f"Completely duplicate rows count: {total_rows - unique_rows}")

con.close()
