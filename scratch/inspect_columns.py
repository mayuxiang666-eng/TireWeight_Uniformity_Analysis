import os
import duckdb

_BASE = os.path.dirname(__file__)
data_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

print("Sample rfppwc_first non-null values:")
df_rfpp = con.execute(f"SELECT \"rfppwc_first\", COUNT(*) FROM read_parquet('{data_path}') WHERE \"rfppwc_first\" IS NOT NULL GROUP BY \"rfppwc_first\" LIMIT 10").df()
print(df_rfpp.to_string())

print("\nSample rfh1wc_first non-null values:")
df_rfh1 = con.execute(f"SELECT \"rfh1wc_first\", COUNT(*) FROM read_parquet('{data_path}') WHERE \"rfh1wc_first\" IS NOT NULL GROUP BY \"rfh1wc_first\" LIMIT 10").df()
print(df_rfh1.to_string())

con.close()
