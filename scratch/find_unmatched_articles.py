import pandas as pd
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
parquet_path = os.path.join(backend_dir, "data", "yield_flat_table_joined_100_cleaned.parquet")
recipes_path = os.path.join(backend_dir, "data", "Recipes.csv")

if os.path.exists(parquet_path) and os.path.exists(recipes_path):
    df = pd.read_parquet(parquet_path)
    recipes = pd.read_csv(recipes_path, dtype={'ART10': str})
    
    recipes['ART10_clean'] = recipes['ART10'].astype(str).str.strip().str.zfill(10)
    df['article10_clean'] = df['article10'].astype(str).str.strip().str.zfill(10)
    
    # Unmatched rows in df (where conny_usl is NaN)
    unmatched_df = df[df['conny_usl'].isna()]
    print("Total unmatched rows in df:", len(unmatched_df))
    
    unmatched_articles = unmatched_df['article10_clean'].value_counts()
    print("\nTop 15 unmatched unique articles in df and their row counts:")
    print(unmatched_articles.head(15))
    
    print("\nChecking if these unmatched article10 exist in Recipes.csv:")
    recipes_art10_set = set(recipes['ART10_clean'].unique())
    for art, count in unmatched_articles.head(15).items():
        in_csv = art in recipes_art10_set
        # Let's also check if it exists in a slightly different form, e.g. without zfill
        raw_art = art.lstrip('0')
        in_csv_raw = raw_art in set(recipes['ART10'].astype(str).str.strip().unique())
        print("Article10: {} (count: {}) -> in Recipes.csv? {} (raw match: {})".format(art, count, in_csv, in_csv_raw))
        
        # Let's show some sample rows in Recipes.csv containing similar numbers if not matched
        if not in_csv:
            similar = [r for r in recipes_art10_set if r.endswith(art[-6:])]
            print("  Similar ART10 ending in '{}' in Recipes.csv: {}".format(art[-6:], similar[:5]))
            
else:
    print("Files not found")
