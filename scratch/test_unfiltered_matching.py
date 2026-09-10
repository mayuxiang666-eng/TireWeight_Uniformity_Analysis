import pandas as pd
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
parquet_path = os.path.join(backend_dir, "data", "yield_flat_table_joined_100_cleaned.parquet")
recipes_path = os.path.join(backend_dir, "data", "Recipes.csv")

if os.path.exists(parquet_path) and os.path.exists(recipes_path):
    df = pd.read_parquet(parquet_path)
    recipes_df = pd.read_csv(recipes_path, dtype={'ART10': str})
    
    # 1. Total unique articles in df
    df['article10_clean'] = df['article10'].astype(str).str.strip().str.zfill(10)
    unique_df_articles = df['article10_clean'].unique()
    print("Total unique article10 in df:", len(unique_df_articles))
    
    # 2. Total unique articles in Recipes.csv (unfiltered)
    recipes_df['ART10_clean'] = recipes_df['ART10'].astype(str).str.strip().str.zfill(10)
    unique_recipes_articles = recipes_df['ART10_clean'].unique()
    print("Total unique ART10 in Recipes.csv:", len(unique_recipes_articles))
    
    # 3. Intersection without any filters
    matched_articles = set(unique_df_articles).intersection(set(unique_recipes_articles))
    print("Matched unique articles (unfiltered):", len(matched_articles))
    
    # 4. Total rows matched in df
    total_matched_rows = df['article10_clean'].isin(unique_recipes_articles).sum()
    print("Total rows matched in df (unfiltered):", total_matched_rows)
    print("Total rows in df:", len(df))
    
    # 5. Let's see how duplicate ART10 are resolved in Recipes.csv
    # When we drop duplicates, does keeping the last or first make a difference?
    # Or should we sort by VER or RELEASE_TIME?
    recipes_df['RELEASE_TIME_dt'] = pd.to_datetime(recipes_df['RELEASE_TIME'], errors='coerce')
    # Sort by RELEASE_TIME descending so latest release is kept
    recipes_latest = recipes_df.sort_values(by='RELEASE_TIME_dt', ascending=False).drop_duplicates(subset=['ART10_clean'], keep='first')
    
    conu_map = recipes_latest.set_index('ART10_clean')['CONU_T1'].to_dict()
    conl_map = recipes_latest.set_index('ART10_clean')['CONL_T1'].to_dict()
    
    df['conny_usl_unfiltered'] = df['article10_clean'].map(conu_map)
    df['conny_lsl_unfiltered'] = df['article10_clean'].map(conl_map)
    
    print("\nWith latest release matching:")
    print("Populated conny_usl_unfiltered count:", df['conny_usl_unfiltered'].notna().sum())
    
else:
    print("Files not found")
