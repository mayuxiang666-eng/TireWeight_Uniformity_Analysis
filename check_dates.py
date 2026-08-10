import duckdb
import os

_BASE = os.path.dirname(__file__)
DATA_PATH = os.path.join(_BASE, "src", "yield_flat_table_30d_2_cleaned.parquet")

con = duckdb.connect()
res = con.execute(f"SELECT MIN(ct_shiftdate)::DATE, MAX(ct_shiftdate)::DATE, COUNT(*) FROM read_parquet('{DATA_PATH}')").fetchall()
print("Dataset Date bounds and count:", res)

# Check counts in the specific range selected by the user:
# baseline: 2026-05-30 to 2026-06-01, study: 2026-06-04 to 2026-06-06
# Wait, let's see what date range is actually in the parquet
con.close()
