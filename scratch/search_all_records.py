import duckdb
import os
import glob
import sys
import pandas as pd

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

data_dir = r'd:\Ava\untitled1\untitled1_v2\backend\data'
cgrs_dir = os.path.join(data_dir, 'cgrs_data')

con = duckdb.connect()

cgrs_glob = os.path.join(cgrs_dir, '*.parquet').replace(os.sep, '/')
con.execute(f"CREATE OR REPLACE VIEW cgrs_all AS SELECT * FROM read_parquet('{cgrs_glob}', union_by_name=true)")

yield_pq = os.path.join(data_dir, 'yield_flat_table_joined_100_cleaned.parquet').replace(os.sep, '/')
con.execute(f"CREATE OR REPLACE VIEW yield_table AS SELECT * FROM read_parquet('{yield_pq}')")

# Also raw parquet if needed
raw_yield_pq = os.path.join(data_dir, 'yield_flat_table_joined_100.parquet').replace(os.sep, '/')
if os.path.exists(raw_yield_pq):
    con.execute(f"CREATE OR REPLACE VIEW raw_yield_table AS SELECT * FROM read_parquet('{raw_yield_pq}')")

# Also check CGRS.csv
cgrs_csv = os.path.join(data_dir, 'CGRS.csv').replace(os.sep, '/')
if os.path.exists(cgrs_csv):
    con.execute(f"CREATE OR REPLACE VIEW cgrs_csv_table AS SELECT * FROM read_csv_auto('{cgrs_csv}')")

articles = [
    {"art": "316867", "tbm": "176", "date": "08-13", "param": "SSR: 245->165", "target": "RFPP"},
    {"art": "316925", "tbm": "122", "date": "08-15", "param": "SW: 125->215, PLY: 325->275", "target": "SBALW/BBALW"},
    {"art": "359734", "tbm": "2B1", "date": "07-29", "param": "BC: 0->125", "target": "RFPP/RFH1"},
    {"art": "315642", "tbm": "1B1", "date": "08-06", "param": "PLY2: 150->70", "target": "RFPP/RFH1"},
    {"art": "315124", "tbm": "121", "date": "08-11", "param": "SW: 125->215", "target": "SBALW/BBALW"},
    {"art": "359773", "tbm": "176", "date": "08-11", "param": "SSR: 245->175", "target": "RFPP"},
]

for item in articles:
    art = item["art"]
    print(f"\n=======================================================")
    print(f"Target: Art={art}, TBM={item['tbm']}, Date={item['date']}, Param={item['param']}, TargetMetric={item['target']}")
    print(f"=======================================================")
    
    # 1. 查找 CGRS 中的参数变更记录
    df_cgrs = con.execute(f"""
        SELECT 
            Workcenter,
            ParameterName,
            ParameterGlobalName,
            ParameterLocalName,
            TechOffsetHistoryValueFrom,
            TechOffsetHistoryValueTo,
            TechOffsetValue,
            TechOffsetHistoryLocalDate,
            TechOffsetLocalDate,
            UserName,
            TechOffsetComments,
            MaterialMasterID,
            ProdSpecific1,
            ProdSpecific2
        FROM cgrs_all
        WHERE CAST(MaterialMasterID AS VARCHAR) LIKE '%{art}%'
           OR CAST(ProdSpecific1 AS VARCHAR) LIKE '%{art}%'
           OR CAST(ProdSpecific2 AS VARCHAR) LIKE '%{art}%'
           OR CAST(RecipeDescription AS VARCHAR) LIKE '%{art}%'
        ORDER BY COALESCE(TechOffsetHistoryLocalDate, TechOffsetLocalDate) DESC
    """).df()
    
    print(f"[CGRS Parquet 记录数]: {len(df_cgrs)}")
    if not df_cgrs.empty:
        for idx, row in df_cgrs.iterrows():
            print(f"  - 机台: {row['Workcenter']} | 参数: {row['ParameterName']} ({row['ParameterGlobalName']}/{row['ParameterLocalName']}) | 变更: {row['TechOffsetHistoryValueFrom']} -> {row['TechOffsetHistoryValueTo']} (现值:{row['TechOffsetValue']}) | 变更时间(Local): {row['TechOffsetHistoryLocalDate']} / {row['TechOffsetLocalDate']} | 用户: {row['UserName']} | 备注: {row['TechOffsetComments']}")
    
    # 2. 查找 yield_table 中的生产记录与机台
    df_yield = con.execute(f"""
        SELECT 
            article10,
            gt_workcenter,
            MIN(gt_loc_timestamp) as min_gt,
            MAX(gt_loc_timestamp) as max_gt,
            MIN(tu_first_loc_timestamp) as min_tu,
            MAX(tu_first_loc_timestamp) as max_tu,
            COUNT(*) as total_count,
            COUNT(TRY_CAST(rfppwc_first AS DOUBLE)) as rfpp_count,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
            AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) as mean_rfh1
        FROM yield_table
        WHERE CAST(article10 AS VARCHAR) LIKE '%{art}%'
           OR CAST(article10_intended AS VARCHAR) LIKE '%{art}%'
           OR CAST(articleid AS VARCHAR) LIKE '%{art}%'
        GROUP BY article10, gt_workcenter
        ORDER BY total_count DESC
    """).df()
    
    print(f"\n[Yield 数据统计]:")
    if df_yield.empty:
        print("  【未在 yield_table (近100天/当前数据集) 找到该 article 的生产记录!】")
    else:
        print(df_yield.to_string())

