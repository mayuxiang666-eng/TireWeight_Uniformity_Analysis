import os
import duckdb

_BASE = os.path.dirname(__file__)
data_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

print("--- Anomaly Fields Distribution ---")
for col in ['grade_anomaly', 'rfpp_anomaly', 'rfh1_anomaly']:
    df = con.execute(f"SELECT \"{col}\", COUNT(*), COUNT(*)*100.0/(SELECT COUNT(*) FROM read_parquet('{data_path}')) FROM read_parquet('{data_path}') GROUP BY \"{col}\"").df()
    print(f"\n{col} distribution:")
    print(df.to_string())

print("\n--- Group Distribution ---")
df_group = con.execute(f"SELECT \"group\", COUNT(*) FROM read_parquet('{data_path}') GROUP BY \"group\"").df()
print(df_group.to_string())

print("\n--- SpecIssue (Top 10) ---")
df_spec = con.execute(f"SELECT \"specissue\", COUNT(*) FROM read_parquet('{data_path}') GROUP BY \"specissue\" ORDER BY COUNT(*) DESC LIMIT 10").df()
print(df_spec.to_string())

print("\n--- Anomaly Code Distribution (Top 10) ---")
df_anom_code = con.execute(f"SELECT \"anomaly_code\", COUNT(*) FROM read_parquet('{data_path}') WHERE \"anomaly_code\" IS NOT NULL GROUP BY \"anomaly_code\" ORDER BY COUNT(*) DESC LIMIT 10").df()
print(df_anom_code.to_string())

print("\n--- Workcenters ---")
# Check which columns have 'workcenter'
schema_df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{data_path}')").df()
wc_cols = [c for c in schema_df['column_name'] if 'workcenter' in c]
for wc in wc_cols:
    null_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{data_path}') WHERE \"{wc}\" IS NULL").fetchone()[0]
    uniq_cnt = con.execute(f"SELECT COUNT(DISTINCT \"{wc}\") FROM read_parquet('{data_path}')").fetchone()[0]
    print(f"Workcenter column: {wc} | Null count: {null_cnt} | Unique count: {uniq_cnt}")

con.close()
