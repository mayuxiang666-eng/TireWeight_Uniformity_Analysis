import os
import sys
import pandas as pd
import datetime

server_root = r"\\10.246.97.159\TU AI\TireWeight_Uniformity_Analysis"
base_p = os.path.join(server_root, "backend", "data", "yield_flat_table_joined_100.parquet")
inc_p = os.path.join(server_root, "data", "yield_flat_table_joined_100.parquet")
out_p = os.path.join(server_root, "backend", "data", "yield_flat_table_joined_100_cleaned.parquet")
recipes_p = os.path.join(server_root, "backend", "data", "Recipes.csv")

print("1. 读取服务器已有的基准宽表 (backend/data/)...")
if os.path.exists(base_p):
    df_base = pd.read_parquet(base_p)
    print(f"   基准数据: {len(df_base)} 行, 列数: {len(df_base.columns)}")
else:
    print(f"   [Error] 未找到基准宽表: {base_p}")
    sys.exit(1)

print("2. 读取服务器 14:00 提取的增量数据 (data/)...")
if os.path.exists(inc_p):
    df_inc = pd.read_parquet(inc_p)
    print(f"   增量数据: {len(df_inc)} 行, 列数: {len(df_inc.columns)}")
else:
    df_inc = pd.DataFrame()
    print("   未找到增量数据，直接清洗已有数据。")

# 执行 upsert
if not df_inc.empty and "barcode" in df_base.columns and "barcode" in df_inc.columns:
    inc_barcodes = set(df_inc["barcode"].dropna().astype(str).unique())
    df_base_filtered = df_base[~df_base["barcode"].astype(str).isin(inc_barcodes)]
    print(f"   Upsert: 剔除重复旧条码 {len(df_base) - len(df_base_filtered)} 条，追加增量 {len(df_inc)} 条...")
    df_merged = pd.concat([df_base_filtered, df_inc], ignore_index=True)
else:
    df_merged = df_base.copy()

print(f"3. 合并后全量行数: {len(df_merged)} 行。")

# 滚动 30 天保留窗口
retention_days = 30
cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
if "tu_first_shift_date" in df_merged.columns:
    df_merged["tu_first_shift_date"] = pd.to_datetime(df_merged["tu_first_shift_date"], errors="coerce")
    date_valid_mask = df_merged["tu_first_shift_date"].notna()
    within_window = df_merged["tu_first_shift_date"] >= cutoff_date
    df_merged = df_merged[~date_valid_mask | within_window]
    print(f"   保留 30 天窗口（截止 {cutoff_date.strftime('%Y-%m-%d')}）: 最终保留 {len(df_merged)} 行。")

# 保存回 base_p
print("4. 保存合并后的完整基准宽表...")
df_merged.to_parquet(base_p, compression="snappy", index=False)
# 同时镜像备份到 root data
root_base_p = os.path.join(server_root, "data", "yield_flat_table_joined_100.parquet")
df_merged.to_parquet(root_base_p, compression="snappy", index=False)
print("   基准宽表保存完成！")

# 5. 执行 clean_main 进行全量清洗
print("5. 执行 clean_main 清洗数据...")
sys.path.insert(0, r"d:\Ava\untitled1\untitled1_v2")
from backend.etl.clean_data import clean_main

# 清洗 backend/data
ok = clean_main(input_path=base_p, output_path=out_p, recipes_path=recipes_p)
print("   清洗完成结果:", ok)

# 同时镜像一份到 root data
root_out_p = os.path.join(server_root, "data", "yield_flat_table_joined_100_cleaned.parquet")
import shutil
shutil.copy2(out_p, root_out_p)
print(f"   镜像输出同步完成: {root_out_p}")

print("=========================================")
print("全流程合并清洗与镜像同步完成！")
print("=========================================")
