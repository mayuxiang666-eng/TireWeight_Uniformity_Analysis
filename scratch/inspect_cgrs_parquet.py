import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
df_cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')").df()
all_cols = df_cols['column_name'].tolist()

print("All columns in parquet:")
print(all_cols)

# Check if there is tu_first_loc_timestamp or similar
tu_cols = [c for c in all_cols if 'tu' in c.lower()]
print("\nTU related columns:", tu_cols)
