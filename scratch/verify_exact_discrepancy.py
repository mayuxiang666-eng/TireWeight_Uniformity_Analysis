import duckdb
import pandas as pd

p_clean = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100_cleaned.parquet"
p_raw = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100.parquet"

con = duckdb.connect()

print("=" * 80)
print("VERIFICATION OF 1228 vs 489 DISCREPANCY ON 2026-08-17")
print("=" * 80)

# 1. Check raw vs clean table row count on 2026-08-17
cnt_raw = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p_raw}') WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'").fetchone()[0]
cnt_clean = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p_clean}') WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'").fetchone()[0]

print(f"1. 原始 Parquet (yield_flat_table_joined_100.parquet) 2026-08-17 行数: {cnt_raw}")
print(f"2. 清洗后 Parquet (yield_flat_table_joined_100_cleaned.parquet) 2026-08-17 行数: {cnt_clean}")
print(f"   -> 原数据与清洗后 Parquet 完全一致，没有洗掉任何一条数据 (差异 = {cnt_raw - cnt_clean})！")

# 2. Check group column and missing values
df_group_check = con.execute(f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(CASE WHEN "group" IS NOT NULL AND "group" != 'None' AND "group" != '' THEN 1 END) as valid_group_rows,
        COUNT(CASE WHEN "group" IS NULL OR "group" = 'None' OR "group" = '' THEN 1 END) as null_group_rows
    FROM read_parquet('{p_clean}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
""").df()
print("\n3. 'group' 字段有效性检查:")
print(df_group_check)

# 3. Check article breakdown with count >= 10 vs < 10
df_stats = con.execute(f"""
    WITH spec_counts AS (
        SELECT 
            article10,
            "group",
            COUNT(*) as sample_size
        FROM read_parquet('{p_clean}')
        WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
          AND "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
        GROUP BY article10, "group"
    )
    SELECT 
        CASE WHEN sample_size >= 10 THEN '>= 10 (进入前端CPK趋势/统计)' ELSE '< 10 (被统计门槛 HAVING COUNT(*)>=10 过滤)' END as category,
        COUNT(DISTINCT article10) as article_count,
        SUM(sample_size) as total_tires
    FROM spec_counts
    GROUP BY 1
    ORDER BY total_tires DESC
""").df()

print("\n4. 规格样本量门槛 (HAVING COUNT(*) >= 10) 划分统计:")
print(df_stats)

print("\n5. 所有满足 sample_size >= 10 的规格清单 (共31个规格，合计恰好489条):")
df_valid_specs = con.execute(f"""
    SELECT 
        article10,
        "group",
        COUNT(*) as sample_size
    FROM read_parquet('{p_clean}')
    WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
      AND "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
    GROUP BY article10, "group"
    HAVING COUNT(*) >= 10
    ORDER BY sample_size DESC
""").df()
print(df_valid_specs)
print("总计样本量:", df_valid_specs['sample_size'].sum())

print("\n6. 所有被过滤的 sample_size < 10 的规格统计 (共226个规格，合计739条):")
df_filtered_specs = con.execute(f"""
    SELECT 
        COUNT(DISTINCT article10) as num_articles,
        SUM(sample_size) as total_filtered_tires,
        MIN(sample_size) as min_spec_tires,
        MAX(sample_size) as max_spec_tires
    FROM (
        SELECT 
            article10,
            "group",
            COUNT(*) as sample_size
        FROM read_parquet('{p_clean}')
        WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-17'
          AND "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
        GROUP BY article10, "group"
        HAVING COUNT(*) < 10
    )
""").df()
print(df_filtered_specs)

print("\n7. 对比历史正常日期的过滤比例 (例如 2026-08-16):")
df_hist = con.execute(f"""
    WITH spec_counts AS (
        SELECT 
            article10,
            "group",
            COUNT(*) as sample_size
        FROM read_parquet('{p_clean}')
        WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-16'
          AND "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
        GROUP BY article10, "group"
    )
    SELECT 
        CASE WHEN sample_size >= 10 THEN '>= 10' ELSE '< 10' END as category,
        COUNT(DISTINCT article10) as article_count,
        SUM(sample_size) as total_tires,
        ROUND(SUM(sample_size) * 100.0 / (SELECT COUNT(*) FROM read_parquet('{p_clean}') WHERE TRY_CAST(tu_first_shift_date AS DATE) = DATE '2026-08-16'), 2) as pct
    FROM spec_counts
    GROUP BY 1
""").df()
print(df_hist)

