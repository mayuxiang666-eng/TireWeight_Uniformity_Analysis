import pandas as pd
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
parquet_path = os.path.join(backend_dir, "data", "yield_flat_table_joined_100_cleaned.parquet")
recipes_path = os.path.join(backend_dir, "data", "Recipes.csv")

if os.path.exists(parquet_path):
    df = pd.read_parquet(parquet_path)
    print("Parquet cony_first stats:")
    print(df["cony_first"].describe())
    print("\nSample cony_first values:")
    print(df["cony_first"].dropna().head(10))
else:
    print("Parquet file not found")

if os.path.exists(recipes_path):
    recipes = pd.read_csv(recipes_path, dtype={'ART10': str})
    print("\nRecipes CONU_T1 and CONL_T1 stats:")
    print(recipes[["CONU_T1", "CONL_T1"]].describe())
    print("\nSample Recipes rows:")
    print(recipes[["ART10", "CONU_T1", "CONL_T1"]].dropna().head(10))
else:
    print("Recipes.csv not found")
