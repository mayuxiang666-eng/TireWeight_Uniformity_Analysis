import duckdb
import pandas as pd
import numpy as np
import json

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
cgrs_path = "untitled1_v2/backend/data/CGRS.csv"

event_time_str = "2026-07-18 18:05:00"
next_change_str = "2026-08-11 08:24:00"

sql = f"""
    SELECT 
        gt_workcenter,
        ct_workcenter,
        tu_first_workcenter,
        TRY_CAST(gt_loc_timestamp AS TIMESTAMP) as gt_time,
        TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as tu_time,
        TRY_CAST(rfppwc_first AS DOUBLE) as rfpp,
        TRY_CAST(rfh1wc_first AS DOUBLE) as rfh1
    FROM read_parquet('{parquet_path}')
    WHERE article10_intended LIKE '031598%'
      AND gt_workcenter = 'TB243'
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) IS NOT NULL
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) < '{next_change_str}'::TIMESTAMP
    ORDER BY gt_time ASC
"""
df = con.execute(sql).df()

def calc_cpk_upper(vals, usl):
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    mean = float(np.mean(vals))
    if len(vals) == 1:
        return mean, 0.0, np.nan
    std = float(np.std(vals, ddof=1))
    if std <= 1e-6:
        cpk = 5.0
    else:
        cpk = (usl - mean) / (3.0 * std)
    return mean, std, max(0.0, min(5.0, cpk))

USL_RFPP = 105.0
USL_RFH1 = 75.0

df_before = df[df['gt_time'] < pd.to_datetime(event_time_str)].sort_values('gt_time', ascending=False)
df_after = df[df['gt_time'] >= pd.to_datetime(event_time_str)].sort_values('gt_time', ascending=True)

paths = df.groupby(['gt_workcenter', 'ct_workcenter', 'tu_first_workcenter'], dropna=False).size().reset_index()[['gt_workcenter', 'ct_workcenter', 'tu_first_workcenter']].values.tolist()

rows = []
for gt, ct, tu in paths:
    cond_b = (df_before['gt_workcenter'] == gt)
    cond_b = cond_b & (df_before['ct_workcenter'] == ct if pd.notna(ct) else df_before['ct_workcenter'].isna())
    cond_b = cond_b & (df_before['tu_first_workcenter'] == tu if pd.notna(tu) else df_before['tu_first_workcenter'].isna())
    
    cond_a = (df_after['gt_workcenter'] == gt)
    cond_a = cond_a & (df_after['ct_workcenter'] == ct if pd.notna(ct) else df_after['ct_workcenter'].isna())
    cond_a = cond_a & (df_after['tu_first_workcenter'] == tu if pd.notna(tu) else df_after['tu_first_workcenter'].isna())
    
    sub_b = df_before[cond_b].head(100)
    sub_a = df_after[cond_a].head(100)
    
    n_b = len(sub_b)
    n_a = len(sub_a)
    if n_b == 0 and n_a == 0:
        continue
        
    rfpp_b = sub_b['rfpp'].dropna().values
    rfpp_a = sub_a['rfpp'].dropna().values
    m_rfpp_b, s_rfpp_b, cpk_rfpp_b = calc_cpk_upper(rfpp_b, USL_RFPP)
    m_rfpp_a, s_rfpp_a, cpk_rfpp_a = calc_cpk_upper(rfpp_a, USL_RFPP)
    
    rfh1_b = sub_b['rfh1'].dropna().values
    rfh1_a = sub_a['rfh1'].dropna().values
    m_rfh1_b, s_rfh1_b, cpk_rfh1_b = calc_cpk_upper(rfh1_b, USL_RFH1)
    m_rfh1_a, s_rfh1_a, cpk_rfh1_a = calc_cpk_upper(rfh1_a, USL_RFH1)
    
    # 状态
    if n_b >= 10 and n_a >= 10:
        category = '有效对比路径 (样本充足 >=10)'
    elif n_b > 0 and n_a > 0:
        category = '小样本对比路径 (<10)'
    elif n_b > 0:
        category = '仅修改前存在路径'
    else:
        category = '仅修改后存在路径'
        
    rows.append({
        'path': f"{gt} -> {ct} -> {tu}",
        'gt': str(gt),
        'ct': str(ct) if pd.notna(ct) else 'None',
        'tu': str(tu) if pd.notna(tu) else 'None',
        'category': category,
        'n_b': n_b,
        'n_a': n_a,
        # RFPP
        'rfpp_m_b': round(m_rfpp_b, 2) if pd.notna(m_rfpp_b) else None,
        'rfpp_m_a': round(m_rfpp_a, 2) if pd.notna(m_rfpp_a) else None,
        'rfpp_m_diff': round(m_rfpp_a - m_rfpp_b, 2) if pd.notna(m_rfpp_b) and pd.notna(m_rfpp_a) else None,
        'rfpp_s_b': round(s_rfpp_b, 2) if pd.notna(s_rfpp_b) else None,
        'rfpp_s_a': round(s_rfpp_a, 2) if pd.notna(s_rfpp_a) else None,
        'rfpp_s_diff': round(s_rfpp_a - s_rfpp_b, 2) if pd.notna(s_rfpp_b) and pd.notna(s_rfpp_a) else None,
        'rfpp_cpk_b': round(cpk_rfpp_b, 3) if pd.notna(cpk_rfpp_b) else None,
        'rfpp_cpk_a': round(cpk_rfpp_a, 3) if pd.notna(cpk_rfpp_a) else None,
        'rfpp_cpk_diff': round(cpk_rfpp_a - cpk_rfpp_b, 3) if pd.notna(cpk_rfpp_b) and pd.notna(cpk_rfpp_a) else None,
        'rfpp_cpk_pct': round((cpk_rfpp_a - cpk_rfpp_b) / cpk_rfpp_b * 100, 2) if pd.notna(cpk_rfpp_b) and pd.notna(cpk_rfpp_a) and cpk_rfpp_b > 1e-4 else None,
        # RFH1
        'rfh1_m_b': round(m_rfh1_b, 2) if pd.notna(m_rfh1_b) else None,
        'rfh1_m_a': round(m_rfh1_a, 2) if pd.notna(m_rfh1_a) else None,
        'rfh1_m_diff': round(m_rfh1_a - m_rfh1_b, 2) if pd.notna(m_rfh1_b) and pd.notna(m_rfh1_a) else None,
        'rfh1_s_b': round(s_rfh1_b, 2) if pd.notna(s_rfh1_b) else None,
        'rfh1_s_a': round(s_rfh1_a, 2) if pd.notna(s_rfh1_a) else None,
        'rfh1_s_diff': round(s_rfh1_a - s_rfh1_b, 2) if pd.notna(s_rfh1_b) and pd.notna(s_rfh1_a) else None,
        'rfh1_cpk_b': round(cpk_rfh1_b, 3) if pd.notna(cpk_rfh1_b) else None,
        'rfh1_cpk_a': round(cpk_rfh1_a, 3) if pd.notna(cpk_rfh1_a) else None,
        'rfh1_cpk_diff': round(cpk_rfh1_a - cpk_rfh1_b, 3) if pd.notna(cpk_rfh1_b) and pd.notna(cpk_rfh1_a) else None,
        'rfh1_cpk_pct': round((cpk_rfh1_a - cpk_rfh1_b) / cpk_rfh1_b * 100, 2) if pd.notna(cpk_rfh1_b) and pd.notna(cpk_rfh1_a) and cpk_rfh1_b > 1e-4 else None,
    })

res_df = pd.DataFrame(rows)
res_df.to_json("untitled1_v2/scratch/cgrs_path_results.json", orient="records", indent=2, force_ascii=False)

print("=== Classification Counts ===")
print(res_df['category'].value_counts())

print("\n=== Valid Paths (n_b >= 10 and n_a >= 10) ===")
valid = res_df[res_df['category'] == '有效对比路径 (样本充足 >=10)'].sort_values('rfpp_cpk_diff', ascending=False)
for _, r in valid.iterrows():
    print(f"{r['path']} | n=({r['n_b']}, {r['n_a']}) | RFPP: mean({r['rfpp_m_b']}->{r['rfpp_m_a']}, diff={r['rfpp_m_diff']}), std({r['rfpp_s_b']}->{r['rfpp_s_a']}, diff={r['rfpp_s_diff']}), cpk({r['rfpp_cpk_b']}->{r['rfpp_cpk_a']}, diff={r['rfpp_cpk_diff']}, {r['rfpp_cpk_pct']}%) | RFH1: mean({r['rfh1_m_b']}->{r['rfh1_m_a']}, diff={r['rfh1_m_diff']}), std({r['rfh1_s_b']}->{r['rfh1_s_a']}, diff={r['rfh1_s_diff']}), cpk({r['rfh1_cpk_b']}->{r['rfh1_cpk_a']}, diff={r['rfh1_cpk_diff']}, {r['rfh1_cpk_pct']}%)")
