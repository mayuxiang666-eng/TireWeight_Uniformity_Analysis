import pandas as pd
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
parquet_path = os.path.join(backend_dir, "data", "yield_flat_table_joined_100_cleaned.parquet")

if os.path.exists(parquet_path):
    df = pd.read_parquet(parquet_path)
    print("Columns in cleaned parquet:")
    print(df.columns.tolist()[:10], "... total:", len(df.columns))
    print("\nCheck if conny_usl and conny_lsl exist:")
    print("conny_usl in df.columns:", 'conny_usl' in df.columns)
    print("conny_lsl in df.columns:", 'conny_lsl' in df.columns)
    
    # Check populated value counts
    print("\nValue counts of conny_usl:")
    print(df['conny_usl'].value_counts(dropna=False).head(10))
    print("\nValue counts of conny_lsl:")
    print(df['conny_lsl'].value_counts(dropna=False).head(10))
    
    # Check sample matched rows
    matched = df[['article10', 'cony_first', 'conny_usl', 'conny_lsl']].dropna()
    print("\nSample matched rows (count: {}):".format(len(matched)))
    print(matched.head(20))
else:
    print("Parquet file not found")
