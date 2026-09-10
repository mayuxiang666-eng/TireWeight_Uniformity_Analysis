import duckdb
import pandas as pd

pd.set_option('display.max_columns', 50)
pd.set_option('display.width', 1000)

p_clean = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100_cleaned.parquet"
p_raw = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100.parquet"

con = duckdb.connect()

print("=" * 80)
print("1. BREAKDOWN OF 2026-08-17 DATA IN CLEANED PARQUET")
print("=" * 80)

# Check total rows on 2026-08-17
df_17 = con.execute(f"""
    SELECT *
    FROM read_parquet('{p_clean}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
""").df()

print(f"Total rows on 2026-08-17: {len(df_17)}")

print("\n--- Non-null counts for key columns on 2026-08-17 ---")
for col in df_17.columns:
    non_null = df_17[col].notna().sum()
    null_cnt = df_17[col].isna().sum()
    empty_cnt = (df_17[col].astype(str).str.strip().isin(['', 'None', 'nan', 'NULL'])).sum()
    if null_cnt > 0 or empty_cnt > 0 or non_null < len(df_17):
        print(f"  {col:35s}: non_null={non_null}, null={null_cnt}, empty_str={empty_cnt}")

print("\n--- Value counts of ct_shop on 2026-08-17 ---")
print(df_17['ct_shop'].value_counts(dropna=False))

print("\n--- Indicator availability on 2026-08-17 ---")
print("rfppwc_first not null & >0:", df_17['rfppwc_first'].apply(pd.to_numeric, errors='coerce').gt(0).sum())
print("rfh1wc_first not null & >0:", df_17['rfh1wc_first'].apply(pd.to_numeric, errors='coerce').gt(0).sum())
print("cony_first not null:", df_17['cony_first'].apply(pd.to_numeric, errors='coerce').notna().sum())
print("tire_weight_actual_first not null & >0:", df_17['tire_weight_actual_first'].apply(pd.to_numeric, errors='coerce').gt(0).sum())
print("tire_weight_target_first not null & >0:", df_17['tire_weight_target_first'].apply(pd.to_numeric, errors='coerce').gt(0).sum())

print("\n--- Check combinations that might equal 489 ---")
# Check various filters to see which one equals 489!
queries = [
    ("rfppwc_first not null", "rfppwc_first IS NOT NULL AND TRY_CAST(rfppwc_first AS DOUBLE) > 0"),
    ("rfh1wc_first not null", "rfh1wc_first IS NOT NULL AND TRY_CAST(rfh1wc_first AS DOUBLE) > 0"),
    ("cony_first not null", "cony_first IS NOT NULL AND TRY_CAST(cony_first AS DOUBLE) IS NOT NULL"),
    ("weight actual & target > 0", "tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0"),
    ("ct_shop LIKE '%P4%'", "ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%'"),
    ("ct_shop NOT LIKE '%P4%' (P3)", "ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%'"),
    ("tb_first_workcenter not null", "tb_first_workcenter IS NOT NULL AND TRIM(CAST(tb_first_workcenter AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("gt_workcenter not null", "gt_workcenter IS NOT NULL AND TRIM(CAST(gt_workcenter AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("ct_workcenter not null", "ct_workcenter IS NOT NULL AND TRIM(CAST(ct_workcenter AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("tu_first_workcenter not null", "tu_first_workcenter IS NOT NULL AND TRIM(CAST(tu_first_workcenter AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("tread_lot not null", "tread_lot IS NOT NULL AND TRIM(CAST(tread_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("inner_liner_lot not null", "inner_liner_lot IS NOT NULL AND TRIM(CAST(inner_liner_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("sidewall_lot not null", "sidewall_lot IS NOT NULL AND TRIM(CAST(sidewall_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("first_breaker_lot not null", "first_breaker_lot IS NOT NULL AND TRIM(CAST(first_breaker_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("second_breaker_lot not null", "second_breaker_lot IS NOT NULL AND TRIM(CAST(second_breaker_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("first_ply_lot not null", "first_ply_lot IS NOT NULL AND TRIM(CAST(first_ply_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
    ("bead_lot not null", "bead_lot IS NOT NULL AND TRIM(CAST(bead_lot AS VARCHAR)) NOT IN ('', 'None', 'nan')"),
]

for label, cond in queries:
    cnt = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{p_clean}')
        WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
          AND ({cond})
    """).fetchone()[0]
    print(f"Filter [{label:35s}]: {cnt} rows")

print("\n--- Check by article10 on 2026-08-17 ---")
df_arts = con.execute(f"""
    SELECT 
        article10,
        COUNT(*) as total_rows,
        COUNT(CASE WHEN ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 END) as p4_cnt,
        COUNT(CASE WHEN ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' THEN 1 END) as p3_cnt,
        COUNT(CASE WHEN rfppwc_first IS NOT NULL AND TRY_CAST(rfppwc_first AS DOUBLE) > 0 THEN 1 END) as rfpp_cnt,
        COUNT(CASE WHEN cony_first IS NOT NULL THEN 1 END) as cony_cnt,
        COUNT(CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0 THEN 1 END) as weight_cnt
    FROM read_parquet('{p_clean}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
    GROUP BY article10
    ORDER BY total_rows DESC
""").df()
print(df_arts)

print("\nSum of total_rows across articles:", df_arts['total_rows'].sum())
print("Articles with total_rows >= 30:", df_arts[df_arts['total_rows'] >= 30]['total_rows'].sum(), f"({len(df_arts[df_arts['total_rows'] >= 30])} articles)")
print("Articles with total_rows >= 50:", df_arts[df_arts['total_rows'] >= 50]['total_rows'].sum(), f"({len(df_arts[df_arts['total_rows'] >= 50])} articles)")

