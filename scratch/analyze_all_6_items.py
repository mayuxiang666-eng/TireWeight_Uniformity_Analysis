import duckdb
import os
import glob
import sys
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

data_dir = r'd:\Ava\untitled1\untitled1_v2\backend\data'
cgrs_dir = os.path.join(data_dir, 'cgrs_data')
yield_pq = os.path.join(data_dir, 'yield_flat_table_joined_100_cleaned.parquet').replace(os.sep, '/')
raw_yield_pq = os.path.join(data_dir, 'yield_flat_table_joined_100.parquet').replace(os.sep, '/')
cgrs_glob = os.path.join(cgrs_dir, '*.parquet').replace(os.sep, '/')
cgrs_csv = os.path.join(data_dir, 'CGRS.csv').replace(os.sep, '/')
recipes_csv = os.path.join(data_dir, 'Recipes.csv').replace(os.sep, '/')

con = duckdb.connect()
con.execute(f"CREATE OR REPLACE VIEW cgrs_all AS SELECT * FROM read_parquet('{cgrs_glob}', union_by_name=true)")
con.execute(f"CREATE OR REPLACE VIEW yield_table AS SELECT * FROM read_parquet('{yield_pq}')")
if os.path.exists(raw_yield_pq):
    con.execute(f"CREATE OR REPLACE VIEW raw_yield_table AS SELECT * FROM read_parquet('{raw_yield_pq}')")
if os.path.exists(cgrs_csv):
    con.execute(f"CREATE OR REPLACE VIEW cgrs_csv_table AS SELECT * FROM read_csv_auto('{cgrs_csv}')")
if os.path.exists(recipes_csv):
    con.execute(f"CREATE OR REPLACE VIEW recipes_csv_table AS SELECT * FROM read_csv_auto('{recipes_csv}')")

def calc_cpk_stats(vals, usl):
    vals = [v for v in vals if v is not None and not np.isnan(v)]
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "cpk": None}
    mean = float(np.mean(vals))
    if n == 1:
        return {"n": 1, "mean": mean, "std": 0.0, "cpk": 0.0}
    std = float(np.std(vals, ddof=1))
    if std <= 1e-6:
        cpk = 1.33
    else:
        # 单侧上限 USL CPK = (USL - Mean) / (3 * Std)
        cpk = (usl - mean) / (3.0 * std)
    return {"n": n, "mean": mean, "std": std, "cpk": cpk}

items = [
    {
        "id": 1,
        "art": "316867",
        "tbm": "176",
        "date": "2026-08-13",
        "param_desc": "SSR安装位置: 245→165",
        "param_keywords": ["SSR", "Position", "245", "165"],
        "metric_desc": "RFPP下降0.6daN",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    },
    {
        "id": 2,
        "art": "316925",
        "tbm": "122",
        "date": "2026-08-15",
        "param_desc": "SW安装位置: 125→215, PLY安装位置: 325→275",
        "param_keywords": ["SW", "PLY", "Position", "125", "215", "325", "275"],
        "metric_desc": "SBALW/BBALW下降3-4g",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    },
    {
        "id": 3,
        "art": "359734",
        "tbm": "2B1",
        "date": "2026-07-29",
        "param_desc": "BC rotation position: 0→125",
        "param_keywords": ["BC", "rotation", "position", "125"],
        "metric_desc": "RFPP/RFH1下降3-4daN",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    },
    {
        "id": 4,
        "art": "315642",
        "tbm": "1B1",
        "date": "2026-08-06",
        "param_desc": "PLY2安装位置: 150→70",
        "param_keywords": ["PLY2", "PLY 2", "Position", "150", "70"],
        "metric_desc": "RFPP/RFH1下降2daN",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    },
    {
        "id": 5,
        "art": "315124",
        "tbm": "121",
        "date": "2026-08-11",
        "param_desc": "SW安装位置: 125→215",
        "param_keywords": ["SW", "Position", "125", "215"],
        "metric_desc": "SBALW/BBALW下降5-6g",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    },
    {
        "id": 6,
        "art": "359773",
        "tbm": "176",
        "date": "2026-08-11",
        "param_desc": "SSR安装位置: 245→175",
        "param_keywords": ["SSR", "Position", "245", "175"],
        "metric_desc": "RFPP下降1.5daN",
        "metric_col": "rfppwc_first",
        "usl_col": "standard_rfpp"
    }
]

for item in items:
    art = item["art"]
    print("\n" + "="*80)
    print(f"【条目 {item['id']}】 Article: {art} | 机器: {item['tbm']} | 日期: {item['date']} | 调参: {item['param_desc']} | 预期影响: {item['metric_desc']}")
    print("="*80)
    
    # 1. 查找 CGRS 中的相关参数变更
    sql_cgrs = f"""
        SELECT 
            Workcenter,
            ParameterName,
            ParameterGlobalName,
            ParameterLocalName,
            TechOffsetHistoryValueFrom as FromVal,
            TechOffsetHistoryValueTo as ToVal,
            TechOffsetValue as CurrVal,
            TechOffsetHistoryLocalDate as HistDate,
            TechOffsetLocalDate as LocalDate,
            UserName,
            TechOffsetComments as Comments,
            MaterialMasterID,
            ProdSpecific1,
            ProdSpecific2
        FROM cgrs_all
        WHERE CAST(MaterialMasterID AS VARCHAR) LIKE '%{art}%'
           OR CAST(ProdSpecific1 AS VARCHAR) LIKE '%{art}%'
           OR CAST(ProdSpecific2 AS VARCHAR) LIKE '%{art}%'
           OR CAST(RecipeDescription AS VARCHAR) LIKE '%{art}%'
        ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
    """
    df_cgrs = con.execute(sql_cgrs).df()
    
    print(f"\n1. [CGRS 参数修改记录检索] (共找到 {len(df_cgrs)} 条记录):")
    if df_cgrs.empty:
        print(f"   -> 未在 CGRS 中检索到 Article {art} 的任何调参记录！")
    else:
        for _, row in df_cgrs.iterrows():
            d_str = str(row['HistDate'])[:19] if pd.notna(row['HistDate']) else str(row['LocalDate'])[:19]
            print(f"   * 机台: {row['Workcenter']:<6} | 时间: {d_str} | 参数: {row['ParameterName']} ({row['ParameterGlobalName']}/{row['ParameterLocalName']}) | 变动: {row['FromVal']} -> {row['ToVal']} (当前Offset:{row['CurrVal']}) | 操作人: {row['UserName']}")

    # 2. 检查 yield 数据中是否有生产记录
    sql_yield_summary = f"""
        SELECT 
            article10,
            gt_workcenter,
            MIN(gt_loc_timestamp) as min_gt,
            MAX(gt_loc_timestamp) as max_gt,
            MIN(tu_first_loc_timestamp) as min_tu,
            MAX(tu_first_loc_timestamp) as max_tu,
            COUNT(*) as total_samples,
            COUNT(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_valid_count,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_mean,
            STDDEV_SAMP(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_std,
            AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) as rfh1_mean,
            STDDEV_SAMP(TRY_CAST(rfh1wc_first AS DOUBLE)) as rfh1_std,
            AVG(TRY_CAST(standard_rfpp AS DOUBLE)) as std_rfpp,
            AVG(TRY_CAST(standard_rfh1 AS DOUBLE)) as std_rfh1
        FROM yield_table
        WHERE CAST(article10 AS VARCHAR) LIKE '%{art}%'
           OR CAST(article10_intended AS VARCHAR) LIKE '%{art}%'
           OR CAST(articleid AS VARCHAR) LIKE '%{art}%'
        GROUP BY article10, gt_workcenter
        ORDER BY total_samples DESC
    """
    df_y_sum = con.execute(sql_yield_summary).df()
    print(f"\n2. [Yield 生产与检验数据概况]:")
    if df_y_sum.empty:
        print(f"   -> 数据库 yield_flat_table 中完全无 Article {art} 的生产与终检记录！")
    else:
        for _, row in df_y_sum.iterrows():
            print(f"   * 规格: {row['article10']} | 成型机: {row['gt_workcenter']} | 总胎数: {row['total_samples']} (有效RFPP数: {row['rfpp_valid_count']}) | 生产时间跨度: {str(row['min_gt'])[:16]} ~ {str(row['max_gt'])[:16]} | RFPP均值: {row['rfpp_mean']:.2f}, RFH1均值: {row['rfh1_mean']:.2f}")

    # 3. 如果在 yield 中有数据，按目标日期计算修改前后的对比
    target_date = item['date']
    sql_before_after = f"""
        SELECT 
            article10,
            gt_workcenter,
            CASE 
                WHEN COALESCE(gt_loc_timestamp, tu_first_loc_timestamp) < '{target_date} 00:00:00' THEN '修改前(截止至{target_date})'
                WHEN COALESCE(gt_loc_timestamp, tu_first_loc_timestamp) >= '{target_date} 00:00:00' THEN '修改后({target_date}起)'
                ELSE '未知'
            END as period,
            COUNT(*) as sample_count,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_mean,
            STDDEV_SAMP(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_std,
            AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) as rfh1_mean,
            STDDEV_SAMP(TRY_CAST(rfh1wc_first AS DOUBLE)) as rfh1_std,
            AVG(TRY_CAST(standard_rfpp AS DOUBLE)) as std_rfpp,
            AVG(TRY_CAST(standard_rfh1 AS DOUBLE)) as std_rfh1,
            MIN(COALESCE(gt_loc_timestamp, tu_first_loc_timestamp)) as period_min_t,
            MAX(COALESCE(gt_loc_timestamp, tu_first_loc_timestamp)) as period_max_t
        FROM yield_table
        WHERE CAST(article10 AS VARCHAR) LIKE '%{art}%'
           OR CAST(article10_intended AS VARCHAR) LIKE '%{art}%'
           OR CAST(articleid AS VARCHAR) LIKE '%{art}%'
        GROUP BY article10, gt_workcenter, period
        ORDER BY article10, gt_workcenter, period DESC
    """
    df_ba = con.execute(sql_before_after).df()
    if not df_ba.empty:
        print(f"\n3. [按调参基准日 ({target_date}) 前后分段统计]:")
        for _, row in df_ba.iterrows():
            usl_rfpp = (row['std_rfpp'] * 10.0) if pd.notna(row['std_rfpp']) and row['std_rfpp'] < 30 else row['std_rfpp']
            usl_rfh1 = (row['std_rfh1'] * 10.0) if pd.notna(row['std_rfh1']) and row['std_rfh1'] < 30 else row['std_rfh1']
            
            # cpk
            cpk_rfpp = ((usl_rfpp - row['rfpp_mean']) / (3.0 * row['rfpp_std'])) if (pd.notna(row['rfpp_std']) and row['rfpp_std'] > 1e-4 and pd.notna(usl_rfpp)) else None
            cpk_rfh1 = ((usl_rfh1 - row['rfh1_mean']) / (3.0 * row['rfh1_std'])) if (pd.notna(row['rfh1_std']) and row['rfh1_std'] > 1e-4 and pd.notna(usl_rfh1)) else None
            
            cpk_rfpp_str = f"{cpk_rfpp:.3f}" if cpk_rfpp is not None else "N/A"
            cpk_rfh1_str = f"{cpk_rfh1:.3f}" if cpk_rfh1 is not None else "N/A"
            rfpp_std_str = f"{row['rfpp_std']:.3f}" if pd.notna(row['rfpp_std']) else "N/A"
            rfh1_std_str = f"{row['rfh1_std']:.3f}" if pd.notna(row['rfh1_std']) else "N/A"
            
            print(f"   [{row['period']}] 机台:{row['gt_workcenter']} | N={row['sample_count']:<4} | RFPP均值={row['rfpp_mean']:.2f}, 标准差={rfpp_std_str}, CPK={cpk_rfpp_str} (USL={usl_rfpp}) | RFH1均值={row['rfh1_mean']:.2f}, 标准差={rfh1_std_str}, CPK={cpk_rfh1_str} (USL={usl_rfh1}) | 时间: {str(row['period_min_t'])[:16]} ~ {str(row['period_max_t'])[:16]}")

