import pandas as pd
import os

backend_dir = r"d:\Ava\untitled1\untitled1_v2\backend"
parquet_path = os.path.join(backend_dir, "data", "yield_flat_table_joined_100_cleaned.parquet")
recipes_path = os.path.join(backend_dir, "data", "Recipes.csv")

if os.path.exists(parquet_path) and os.path.exists(recipes_path):
    df = pd.read_parquet(parquet_path)
    recipes = pd.read_csv(recipes_path, dtype={'ART10': str})
    
    # Clean ART10 and article10
    recipes['ART10_clean'] = recipes['ART10'].astype(str).str.strip().str.zfill(10)
    recipes_filtered = recipes.drop_duplicates(subset=['ART10_clean'])
    
    df['article10_clean'] = df['article10'].astype(str).str.strip().str.zfill(10)
    
    # Merge or map
    conu_map = recipes_filtered.set_index('ART10_clean')['CONU_T1'].to_dict()
    conl_map = recipes_filtered.set_index('ART10_clean')['CONL_T1'].to_dict()
    
    df['conny_usl'] = df['article10_clean'].map(conu_map)
    df['conny_lsl'] = df['article10_clean'].map(conl_map)
    
    print("Match statistics:")
    print(df[['cony_first', 'conny_usl', 'conny_lsl']].dropna().head(20))
    
    # Let's convert to numeric and check range
    df['cony_first_num'] = pd.to_numeric(df['cony_first'], errors='coerce')
    matched = df[['cony_first_num', 'conny_usl', 'conny_lsl']].dropna()
    print("\nMatched numeric count:", len(matched))
    print("Min cony:", matched['cony_first_num'].min(), "Max cony:", matched['cony_first_num'].max())
    print("Sample matched rows with diffs:")
    print(matched.head(10))
    
    # Check if CONU_T1/CONL_T1 division by 10.0 makes sense
    print("\nComparing cony_first with CONU_T1:")
    print("Percent of cony_first > CONU_T1:", (matched['cony_first_num'] > matched['conny_usl']).mean() * 100)
    print("Percent of cony_first < CONL_T1:", (matched['cony_first_num'] < matched['conny_lsl']).mean() * 100)
    print("Percent of cony_first > CONU_T1/10:", (matched['cony_first_num'] > (matched['conny_usl']/10.0)).mean() * 100)
    print("Percent of cony_first < CONL_T1/10:", (matched['cony_first_num'] < (matched['conny_lsl']/10.0)).mean() * 100)
else:
    print("Files not found")
