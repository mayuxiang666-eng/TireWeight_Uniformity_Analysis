import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{parquet_path}')")
cols = [r[0] for r in con.execute("DESCRIBE cy").fetchall()]
time_cols = [c for c in cols if 'time' in c.lower() or 'date' in c.lower()]
print("Time columns in Parquet:", time_cols)

res = con.execute(f"SELECT {', '.join(time_cols)} FROM cy LIMIT 3").df()
print(res)
