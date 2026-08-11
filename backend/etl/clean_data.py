import os
import pandas as pd
import numpy as np

def clean_main(input_path=None, output_path=None, recipes_path=None):
    etl_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(etl_dir)
    data_dir = os.path.join(backend_dir, "data")
    
    if input_path is None:
        input_path = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    if output_path is None:
        output_path = os.path.join(data_dir, "yield_flat_table_joined_100_cleaned.parquet")
    if recipes_path is None:
        recipes_path = os.path.join(data_dir, "Recipes.csv")
        
    print("--- 步骤 1: 读取原始 Parquet 数据集 ---")
    if not os.path.exists(input_path):
        print(f"[Error] 未找到输入文件: {input_path}。")
        return False
        
    df = pd.read_parquet(input_path)
    initial_rows = len(df)
    initial_cols = len(df.columns)
    print(f"原始数据集大小: {initial_rows} 行, {initial_cols} 列。")
    
    print("\n--- 步骤 1.2: 基于 Recipes.csv 检查并更新物理上限标准值 (standard_rfpp/standard_rfh1) ---")
    if os.path.exists(recipes_path):
        try:
            recipes_df = pd.read_csv(recipes_path, dtype={'ART10': str})
            recipes_filtered = recipes_df[pd.to_numeric(recipes_df['INFLATION'], errors='coerce') != 200000].copy()
            
            recipes_filtered['ART10_clean'] = recipes_filtered['ART10'].astype(str).str.strip().str.zfill(10)
            recipes_filtered = recipes_filtered.drop_duplicates(subset=['ART10_clean'])
            
            recipes_filtered['RFPP_T1_val'] = pd.to_numeric(recipes_filtered['RFPP_T1'], errors='coerce') / 10.0
            recipes_filtered['RFH1_T1_val'] = pd.to_numeric(recipes_filtered['RFH1_T1'], errors='coerce') / 10.0
            
            recipes_filtered['update_limit_dt'] = pd.to_datetime(recipes_filtered['UPDATE_LIMIT'], errors='coerce')
            
            rfpp_map = recipes_filtered.set_index('ART10_clean')['RFPP_T1_val'].to_dict()
            rfh1_map = recipes_filtered.set_index('ART10_clean')['RFH1_T1_val'].to_dict()
            limit_dt_map = recipes_filtered.set_index('ART10_clean')['update_limit_dt'].to_dict()
            
            df['article10_clean'] = df['article10'].astype(str).str.strip().str.zfill(10)
            
            match_mask = df['article10_clean'].isin(rfpp_map.keys())
            matched_count = match_mask.sum()
            
            if matched_count > 0:
                df.loc[match_mask, 'recipe_update_dt'] = df.loc[match_mask, 'article10_clean'].map(limit_dt_map)
                
                df['record_dt'] = pd.to_datetime(df['tu_first_shift_date'], errors='coerce')
                df['record_dt'] = df['record_dt'].fillna(pd.to_datetime(df['ct_loc_timestamp'], errors='coerce'))
                df['record_dt'] = df['record_dt'].fillna(pd.to_datetime(df['gt_loc_timestamp'], errors='coerce'))
                
                time_mask = match_mask & (df['record_dt'] >= df['recipe_update_dt'])
                matched_time_count = time_mask.sum()
                
                orig_rfpp = df.loc[time_mask, 'standard_rfpp'].copy()
                orig_rfh1 = df.loc[time_mask, 'standard_rfh1'].copy()
                
                new_rfpp = df.loc[time_mask, 'article10_clean'].map(rfpp_map)
                new_rfh1 = df.loc[time_mask, 'article10_clean'].map(rfh1_map)
                
                df.loc[time_mask, 'standard_rfpp'] = new_rfpp
                df.loc[time_mask, 'standard_rfh1'] = new_rfh1
                
                changed_mask = (new_rfpp != orig_rfpp) | (new_rfh1 != orig_rfh1)
                changed_mask = changed_mask & ~((new_rfpp.isna() & orig_rfpp.isna()) & (new_rfh1.isna() & orig_rfh1.isna()))
                
                changed_df = pd.DataFrame({
                    'article10': df.loc[time_mask][changed_mask]['article10'],
                    'orig_rfpp': orig_rfpp[changed_mask],
                    'new_rfpp': new_rfpp[changed_mask],
                    'orig_rfh1': orig_rfh1[changed_mask],
                    'new_rfh1': new_rfh1[changed_mask]
                }).drop_duplicates()
                
                print(f"  匹配成功，共 {matched_count} 行匹配到规格配方，其中 {matched_time_count} 行在修改日期之后进行生产。")
                print(f"  其中数值实际发生修改的行数: {changed_mask.sum()} 行，涉及 {changed_df['article10'].nunique() if 'article10' in changed_df.columns else 0} 个规格。")
            else:
                print("  未匹配到符合条件的配方数据限制更新，物理上限值保持原样不变。")
            
            df = df.drop(columns=['article10_clean'])
            if 'recipe_update_dt' in df.columns:
                df = df.drop(columns=['recipe_update_dt'])
            if 'record_dt' in df.columns:
                df = df.drop(columns=['record_dt'])
            
        except Exception as e:
            print(f"[Error] 读取或处理 Recipes.csv 发生异常: {e}")
    else:
        print(f"[Warning] 未找到配方表: {recipes_path}，跳过标准上限值检查与更新。")
        
    print("\n--- 步骤 1.5: 过滤不需要的冗余或无用字段 ---")
    initial_cols_to_drop = [
        "articleno",
        "articleno_7",
        "articlevariant",
        "branddesignation",
        "loadindexsingle",
        "speedsymbol",
        "ssr"
    ]
    existing_initial_drops = [col for col in initial_cols_to_drop if col in df.columns]
    df = df.drop(columns=existing_initial_drops)
    print(f"已剔除初始字段: {existing_initial_drops}，剩余列数: {len(df.columns)} 列。")
    
    print("\n--- 步骤 2: 删除 article10 缺失的记录 ---")
    df['article10'] = df['article10'].astype(str).str.strip()
    df = df[df['article10'] != ""]
    df = df[df['article10'].notna() & (df['article10'] != 'None') & (df['article10'] != 'nan')]
    
    deleted_rows_art = initial_rows - len(df)
    print(f"已删除 article10 缺失的记录: {deleted_rows_art} 行，剩余: {len(df)} 行。")
    
    print("\n--- 步骤 3: 删除缺失值比例过大 (>= 50%) 的字段 ---")
    cols_to_drop = [
        "yt_workcenter",
        "ssr_insert_bead_cushion_workcenter",
        "ssr_insert_bead_cushion_lot",
        "bead_reinforcement_workcenter",
        "bead_reinforcement_lot",
        "second_ply_lot",
        "second_ply_workcenter"
    ]
    existing_drops = [col for col in cols_to_drop if col in df.columns]
    df = df.drop(columns=existing_drops)
    print(f"已删除缺失列: {existing_drops}，剩余列数: {len(df.columns)} 列。")
    
    print("\n--- 步骤 4: 计算评级异常标记并增加 grade_anomaly 及子指标列 ---")
    anomaly_cols = ['anomaly_code', 'anomaly_code_1', 'anomaly_code_2', 'anomaly_code_3']
    existing_anomaly_cols = [col for col in anomaly_cols if col in df.columns]
    
    if len(existing_anomaly_cols) > 0:
        is_rfpp = pd.Series(False, index=df.index)
        is_rfh1 = pd.Series(False, index=df.index)
        
        for col in existing_anomaly_cols:
            col_str = df[col].astype(str).str.strip()
            is_rfpp |= (col_str == '90A')
            is_rfh1 |= (col_str == '90B')
            
        df['rfpp_anomaly'] = is_rfpp.astype(int)
        df['rfh1_anomaly'] = is_rfh1.astype(int)
        df['grade_anomaly'] = (is_rfpp | is_rfh1).astype(int)
    else:
        print("[Warning] 未在数据中找到任何 anomaly_code 相关字段，默认全部设为正常 (0)。")
        df['rfpp_anomaly'] = 0
        df['rfh1_anomaly'] = 0
        df['grade_anomaly'] = 0
    
    print(f"新标记列分布情况 (总行数: {len(df)}):")
    print(f"  RFPP 异常 (90A): {df['rfpp_anomaly'].sum()} 行 ({df['rfpp_anomaly'].mean()*100:.2f}%)")
    print(f"  RFH1 异常 (90B): {df['rfh1_anomaly'].sum()} 行 ({df['rfh1_anomaly'].mean()*100:.2f}%)")
    print(f"  综合异常 (grade_anomaly): {df['grade_anomaly'].sum()} 行 ({df['grade_anomaly'].mean()*100:.2f}%)")
        
    print("\n--- 步骤 5: 原子化保存清洗后的数据文件 (Atomic Replacement) ---")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = output_path + ".tmp"
    df.to_parquet(tmp_path, compression='snappy', index=False)
    # 原子化替换，避免 FastAPI 在写入过程中读取到未完成的半写入文件
    os.replace(tmp_path, output_path)
    print(f"[Success] 原子化清洗完成！终态保存至: {output_path}")
    print(f"最终数据集大小: {len(df)} 行, {len(df.columns)} 列。")
    return True

if __name__ == "__main__":
    clean_main()
