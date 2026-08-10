import duckdb
DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
df_cols = db_conn.execute(f"SELECT * FROM read_parquet('{DATA_PATH}') LIMIT 1").df().columns.tolist()
print("All columns in the new parquet file:")
for c in sorted(df_cols):
    if 'rf' in c.lower() or 'first' in c.lower() or 'val' in c.lower():
        print(f"  - {c}")
