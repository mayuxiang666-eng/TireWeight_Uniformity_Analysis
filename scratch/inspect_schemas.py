import duckdb
import os
import glob
import pandas as pd

data_dir = r'd:\Ava\untitled1\untitled1_v2\backend\data'
cgrs_dir = os.path.join(data_dir, 'cgrs_data')
files = sorted(glob.glob(os.path.join(cgrs_dir, '*.parquet')))
print(f"Total cgrs parquet files: {len(files)}")

con = duckdb.connect()
if files:
    df_sample = con.execute(f"SELECT * FROM read_parquet('{files[0].replace(os.sep, '/')}') LIMIT 5").df()
    print("CGRS parquet columns:", df_sample.columns.tolist())
    print("Sample row:")
    print(df_sample.iloc[0].to_dict())

yield_pq = os.path.join(data_dir, 'yield_flat_table_joined_100_cleaned.parquet').replace(os.sep, '/')
df_yield_cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{yield_pq}') LIMIT 1").df()
print("\nYield flat table columns:")
print(df_yield_cols['column_name'].tolist())
