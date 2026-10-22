import os
import sys
import time
import re
import argparse
import logging
from datetime import datetime, timedelta
import pyodbc
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 配置日志与路径
# 支持位于 etl/ 或 backend/etl/ 两级或三级目录结构，自适应定位项目根目录
_curr_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(os.path.dirname(_curr_dir)).lower() == 'tu ai' or os.path.exists(os.path.join(os.path.dirname(os.path.dirname(_curr_dir)), "CGRS_full_history_data")):
    BASE_DIR = os.path.dirname(os.path.dirname(_curr_dir))
elif os.path.exists(os.path.join(os.path.dirname(_curr_dir), "CGRS_full_history_data")):
    BASE_DIR = os.path.dirname(_curr_dir)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(_curr_dir))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cgrs_full_history_export.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# 默认导出目录与数据库连接配置
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "CGRS_full_history_data")
DB_SERVER = r"OTTM09RMSMS02.tiremes.contiwan.com\OTT_I1"
DB_NAME = "CGRS_GLOBAL_REPORTS"

# 硫化工序重点关注参数ID (13项)
CURING_PARAM_IDS = [
    1230307,  # 合模力 (Squeeze Pressure)
    1230030,  # 机械手装胎高度 (Loader Shaping Position)
    1230273,  # 二次定型-新胶囊 (Shapepressure 2 new bladder)
    1230275,  # 一次定型-新胶囊 (Shapepressure 1 new bladder)
    1230294,  # 一次定型 (Shaping Step 1)
    1230296,  # 二次定型 (Shaping Step 2)
    1230265,  # 中心机构定型位置（生胎高度） (Center Post Shaping Pos.)
    1230287,  # 定型阀门开启度（新胶囊） (Shaping Max. Open (New Bladder))
    1230288,  # 定型阀门开启度 (Shaping Max. Open)
    1231163,  # 合模暂停时间 (Time Shaping Stop)
    1231164,  # 开模暂停时间 (Time Opening Stop)
    1230385,  # 开模暂停位置（机器） (Position Opening Stop (press))
    1230483   # 下环下降延迟（在脱模时） (Delay Lower Ring down (at Demolding))
]

# 成型一段 KM 核心参数ID (26项)
KM_PARAM_IDS = [
    1190003, 1190005, 1190068, 1190075, 1190212, 1190259, 1190260, 1190261, 
    1190269, 1190293, 1190294, 1190316, 1191574, 1190318, 1190319, 1190338, 
    1190349, 1190066, 1191577, 1190073, 1190251, 1190272, 1190323, 1190392, 
    1190395, 1190396
]

# 成型二段 PU 核心参数ID (30项)
PU_PARAM_IDS = [
    1250094, 1250128, 1250495, 1252086, 1252096, 1250068, 1250143, 1250421, 
    1250280, 1250281, 1250284, 1250285, 1250283, 1250499, 1250498, 1250497, 
    1250091, 1252361, 1252377, 1250148, 1250149, 1250146, 1250150, 1250147, 
    1250153, 1250154, 1250156, 1250296, 1250297, 1250299
]

# 全量配方参数视图配置
PROCESS_VIEW_CONFIGS = [
    {
        "process_type_id": "119",
        "item": "KM",
        "name": "KM TBM Stage 1 (成型工序 KM)",
        "view_name": "vwRecipeReleasedParameterDataFor119_9200",
        "enabled": True,  # 当前生效
        "filter_param_ids": KM_PARAM_IDS  # 仅拉取指定的26项关键参数
    },
    {
        "process_type_id": "123",
        "item": "Curing",
        "name": "Curing (硫化工序)",
        "view_name": "vwRecipeReleasedParameterDataFor123_9200",
        "enabled": True,  # 硫化工序生效启用
        "filter_param_ids": CURING_PARAM_IDS  # 仅拉取指定的13项关键参数
    },
    {
        "process_type_id": "125",
        "item": "PU",
        "name": "PU TBM Stage 2 (成型工序 PU)",
        "view_name": "vwRecipeReleasedParameterDataFor125_9200",
        "enabled": True,  # 成型二段 PU 生效启用
        "filter_param_ids": PU_PARAM_IDS  # 仅拉取指定的30项关键参数
    }
]

def get_existing_snapshot_files(output_dir):
    """
    扫描输出目录下所有现存的 recipe_full_params_YYYY-MM-DD.parquet 文件，
    返回按日期升序排序的字典: {date_str: file_path}
    """
    pattern = re.compile(r"^recipe_full_params_(\d{4}-\d{2}-\d{2})\.parquet$")
    existing = {}
    if not os.path.exists(output_dir):
        return existing
    for fname in os.listdir(output_dir):
        m = pattern.match(fname)
        if m:
            existing[m.group(1)] = os.path.join(output_dir, fname)
    return dict(sorted(existing.items()))

def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=180)

def build_view_sql(view_name, start_date=None, end_date=None, filter_param_ids=None):
    """
    构建查询 SQL，支持基于 RecipeLastModifiedDate 的高效索引范围查询以及特定参数ID过滤
    """
    conditions = []
    if start_date:
        conditions.append(f"RecipeLastModifiedDate >= '{start_date}'")
    if end_date:
        conditions.append(f"RecipeLastModifiedDate < '{end_date}'")
    if filter_param_ids:
        ids_str = ', '.join(str(i) for i in filter_param_ids)
        conditions.append(f"ParameterID IN ({ids_str})")
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return f"""
    SELECT 
           [RecipeID],
           [MaterialMasterID],
           [BomAlternative],
           [ProdIssue],
           [RecipeEdition],
           [RecipeDescription],
           [ParameterID],
           [ParameterGlobalName],
           [ParameterLocalName],
           [ParameterValue],
           [Workcenter],
           [TechOffsetValue],
           [RecipeCreatedDate],
           [RecipeLastModifiedDate]
    FROM [CGRS_GLOBAL_REPORTS].[dbo].[{view_name}]
    {where_clause}
    """

def fetch_view_data(cursor, config, start_date=None, end_date=None):
    proc_id = config["process_type_id"]
    item_label = config["item"]
    view_name = config["view_name"]
    filter_param_ids = config.get("filter_param_ids")
    
    filter_desc = f", 过滤重点 {len(filter_param_ids)} 项参数" if filter_param_ids else ""
    range_desc = f"从 {start_date} 至 {end_date or '最新'}" if start_date else "全量"
    logging.info(f"--> 开始查询视图 [{proc_id} - {item_label}] {view_name} ({range_desc}{filter_desc})...")
    sql = build_view_sql(view_name, start_date=start_date, end_date=end_date, filter_param_ids=filter_param_ids)
    
    t0 = time.time()
    cursor.arraysize = 10000
    cursor.execute(sql)
    
    columns = [c[0] for c in cursor.description]
    rows = []
    
    batch_count = 0
    batch_count = 0
    while True:
        batch = cursor.fetchmany(10000)
        if not batch:
            break
        rows.extend(batch)
        batch_count += len(batch)
        if batch_count % 30000 == 0 or len(batch) < 10000:
            logging.info(f"    [{item_label}] 已检索流式读取 {batch_count} 行 (耗时: {time.time() - t0:.2f}s)...")
            
    t1 = time.time()
    total_fetched = len(rows)
    logging.info(f"    [{item_label}] 视图查询完毕！共拉取 {total_fetched} 行记录，耗时: {t1 - t0:.2f} 秒")
    
    if total_fetched == 0:
        return pd.DataFrame()
        
    data_dict = {col: [r[i] for r in rows] for i, col in enumerate(columns)}
    df = pd.DataFrame(data_dict)
    df["ProcessTypeID"] = proc_id
    df["Item"] = item_label
    
    return df

def save_daily_snapshot_parquet(df_data, output_dir, snapshot_date_str):
    """
    保存为指定日期的全量生效配方快照 Parquet 文件：
    文件名: recipe_full_params_YYYY-MM-DD.parquet
    去重逻辑：按 [ProcessTypeID, MaterialMasterID, ParameterID, Workcenter] 去重，保留最新 RecipeLastModifiedDate
    """
    os.makedirs(output_dir, exist_ok=True)
    file_name = f"recipe_full_params_{snapshot_date_str}.parquet"
    file_path = os.path.join(output_dir, file_name)
    
    t0 = time.time()
    df_save = df_data.copy()
    
    # 确保日期类型并降序排序
    if "RecipeLastModifiedDate" in df_save.columns:
        df_save["RecipeLastModifiedDate"] = pd.to_datetime(df_save["RecipeLastModifiedDate"])
        df_save = df_save.sort_values(by="RecipeLastModifiedDate", ascending=False).reset_index(drop=True)
        
    # 按工序、规格、参数、机台精准去重，保留最新生效参数记录
    dedup_cols = ["ProcessTypeID", "MaterialMasterID", "ParameterID", "Workcenter"]
    if all(c in df_save.columns for c in dedup_cols):
        df_save = df_save.drop_duplicates(subset=dedup_cols, keep="first")
    else:
        df_save = df_save.drop_duplicates(keep="first")
        
    df_save.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    duration = time.time() - t0
    
    km_cnt = (df_save["Item"] == "KM").sum() if "Item" in df_save.columns else 0
    cur_cnt = (df_save["Item"] == "Curing").sum() if "Item" in df_save.columns else 0
    pu_cnt = (df_save["Item"] == "PU").sum() if "Item" in df_save.columns else 0
    
    km_mats = df_save[df_save["Item"] == "KM"]["MaterialMasterID"].nunique() if "Item" in df_save.columns else 0
    cur_mats = df_save[df_save["Item"] == "Curing"]["MaterialMasterID"].nunique() if "Item" in df_save.columns else 0
    pu_mats = df_save[df_save["Item"] == "PU"]["MaterialMasterID"].nunique() if "Item" in df_save.columns else 0
    
    logging.info(f"    -> [保存快照] 日期: {snapshot_date_str} | 总记录: {len(df_save)} 行 (KM: {km_cnt}行/{km_mats}规格, 硫化: {cur_cnt}行/{cur_mats}规格, PU: {pu_cnt}行/{pu_mats}规格) | 文件: {file_name} ({file_size_mb:.2f} MB, 耗时: {duration:.2f}s)")
    return file_path

def save_baseline_parquet(df_data, output_dir):
    """
    保存持久化全量参数基准底表 recipe_full_baseline.parquet
    """
    os.makedirs(output_dir, exist_ok=True)
    file_name = "recipe_full_baseline.parquet"
    file_path = os.path.join(output_dir, file_name)
    
    t0 = time.time()
    df_save = df_data.copy()
    
    if "RecipeLastModifiedDate" in df_save.columns:
        df_save["RecipeLastModifiedDate"] = pd.to_datetime(df_save["RecipeLastModifiedDate"])
        df_save = df_save.sort_values(by="RecipeLastModifiedDate", ascending=False).reset_index(drop=True)
        
    dedup_cols = ["ProcessTypeID", "MaterialMasterID", "ParameterID", "Workcenter"]
    if all(c in df_save.columns for c in dedup_cols):
        df_save = df_save.drop_duplicates(subset=dedup_cols, keep="first")
    else:
        df_save = df_save.drop_duplicates(keep="first")
        
    df_save.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logging.info(f"--> [保存基准底表] 总记录: {len(df_save)} 行 | 文件: {file_name} ({file_size_mb:.2f} MB, 耗时: {time.time()-t0:.2f}s)")
    return file_path

def extract_single_process_baseline(conn, cfg, date_cond, cache_file, force_rebuild=False):
    """
    抽取单个工序的全量在产生效配方参数基准
    """
    proc_id = cfg["process_type_id"]
    item_label = cfg["item"]
    view_name = cfg["view_name"]
    param_ids = cfg.get("filter_param_ids")
    
    if os.path.exists(cache_file) and not force_rebuild:
        try:
            logging.info(f"[{item_label}] 发现已有全量缓存 {cache_file}，直接加载...")
            df_cached = pd.read_parquet(cache_file)
            logging.info(f"[{item_label}] 缓存加载完成: {len(df_cached)} 行, {df_cached['MaterialMasterID'].nunique()} 个独立规格")
            return df_cached
        except Exception as e:
            logging.warning(f"读取缓存 {cache_file} 失败: {e}，将重新从数据库抽取")

    ids_str = ", ".join(str(p) for p in param_ids) if param_ids else ""
    where_parts = []
    if ids_str:
        where_parts.append(f"ParameterID IN ({ids_str})")
    if date_cond:
        where_parts.append(date_cond)
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    
    sql = f"""
    SELECT [RecipeID], [MaterialMasterID], [BomAlternative], [ProdIssue], [RecipeEdition],
           [RecipeDescription], [ParameterID], [ParameterGlobalName], [ParameterLocalName],
           [ParameterValue], [Workcenter], [TechOffsetValue], [RecipeCreatedDate], [RecipeLastModifiedDate]
    FROM dbo.{view_name}
    {where_clause}
    """
    logging.info(f"[{item_label}] 开始执行冷启动全量数据抽取 ({where_clause})...")
    t0 = time.time()
    cur = conn.cursor()
    cur.arraysize = 50000
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    
    rows = []
    while True:
        b = cur.fetchmany(50000)
        if not b:
            break
        rows.extend(b)
        if len(rows) % 50000 == 0 or len(b) < 50000:
            logging.info(f"    [{item_label}] 已检索流式读取 {len(rows)} 行 (耗时: {time.time()-t0:.1f}s)...")
            
    t_fetch = time.time() - t0
    logging.info(f"[{item_label}] 原始数据读取完毕: 共 {len(rows)} 行，耗时: {t_fetch:.1f}s. 正在去重...")
    
    df = pd.DataFrame.from_records(rows, columns=cols)
    del rows
    
    df["ProcessTypeID"] = str(proc_id)
    df["Item"] = item_label
    df["RecipeLastModifiedDate"] = pd.to_datetime(df["RecipeLastModifiedDate"])
    
    dedup_keys = ["ProcessTypeID", "MaterialMasterID", "ParameterID", "Workcenter"]
    df = df.sort_values(by="RecipeLastModifiedDate", ascending=False).drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
    
    logging.info(f"[{item_label}] 去重完成！最终基准: {len(df)} 行, {df['MaterialMasterID'].nunique()} 独立规格. 正在保存缓存...")
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    df.to_parquet(cache_file, index=False, engine="pyarrow", compression="snappy")
    return df

def run_full_refresh(active_configs, output_dir, force_rebuild=False):
    """
    全量冷启动初始化模式 (Full Refresh Mode):
    不限制最近几天的修改时间，直接抽取 2026 年以来在产的全部 Released 配方参数，
    构建包含全厂所有成熟规格的完备 master baseline，并生成今日全量快照。
    """
    logging.info("===================================================================")
    logging.info("========== 开始执行 CGRS 全量生效配方参数冷启动初始化抽取 (Full Refresh) ==========")
    logging.info("===================================================================")
    t_all = time.time()
    cache_dir = os.path.join(output_dir, "_baseline_cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    conn = get_connection()
    dfs = []
    
    for cfg in active_configs:
        proc_id = cfg["process_type_id"]
        item_label = cfg["item"]
        
        # 针对各工序适配最优历史跨度 (KM/PU 2026整年; 硫化 2026 Q3 7月~9月覆盖全部在产模具)
        if proc_id == "123":
            cache_file = os.path.join(cache_dir, "curing_q3_2026_baseline.parquet")
            date_cond = "RecipeLastModifiedDate >= '2026-07-01'"
        elif proc_id == "119":
            cache_file = os.path.join(cache_dir, "km_2026_baseline.parquet")
            date_cond = "RecipeLastModifiedDate >= '2026-01-01'"
        else:
            cache_file = os.path.join(cache_dir, "pu_2026_baseline.parquet")
            date_cond = "RecipeLastModifiedDate >= '2026-01-01'"
            
        df_proc = extract_single_process_baseline(conn, cfg, date_cond, cache_file, force_rebuild=force_rebuild)
        dfs.append(df_proc)
        
    conn.close()
    
    logging.info("\n==================== 正在合并 Master Baseline ====================")
    df_master = pd.concat(dfs, ignore_index=True)
    dedup_keys = ["ProcessTypeID", "MaterialMasterID", "ParameterID", "Workcenter"]
    df_master["RecipeLastModifiedDate"] = pd.to_datetime(df_master["RecipeLastModifiedDate"])
    df_master = df_master.sort_values(by="RecipeLastModifiedDate", ascending=False).drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
    
    logging.info(f"Master Baseline 记录数: {len(df_master)} 行")
    for item, g in df_master.groupby("Item"):
        logging.info(f"  * [{item}]: {len(g)} 行, {g['MaterialMasterID'].nunique()} 个独立规格")
        
    save_baseline_parquet(df_master, output_dir)
    
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    today_fp = save_daily_snapshot_parquet(df_master, output_dir, snapshot_date_str=today_str)
    
    logging.info(f"全量冷启动初始化完成！总耗时: {time.time()-t_all:.2f} 秒")
    logging.info("===================================================================")
    return [(today_str, today_fp, len(df_master), "冷启动全量初始化")]

def export_cgrs_full_history(days=7, output_dir=DEFAULT_OUTPUT_DIR, enable_123=True, enable_125=True, force=False, full_refresh=False):
    """
    核心导出与自检校准引擎：
    1. 自动扫描历史已有快照文件，智能识别缺口与缺失日期
    2. 从最早缺失日期向数据库进行增量或补录查询（支持 119 KM, 123 Curing, 125 PU）
    3. 按工序独立进行时序生效配方继承，并合并保存为每日统一快照
    """
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    
    # 动态覆盖工序启用状态
    active_configs = []
    for cfg in PROCESS_VIEW_CONFIGS:
        cfg_copy = dict(cfg)
        if cfg_copy["process_type_id"] == "123" and not enable_123:
            cfg_copy["enabled"] = False
        if cfg_copy["process_type_id"] == "125" and not enable_125:
            cfg_copy["enabled"] = False
        if cfg_copy["enabled"]:
            active_configs.append(cfg_copy)
            
    active_names = [f"{c['item']}({c['process_type_id']})" for c in active_configs]
    
    if full_refresh:
        return run_full_refresh(active_configs, output_dir, force_rebuild=force)
    
    logging.info("===================================================================")
    logging.info(f"========== 开始执行 CGRS 全量生效配方参数每日自检校准与导出 [{today_str}] ==========")
    logging.info(f"启用视图: {', '.join(active_names)}")
    logging.info(f"快照保存目录: {output_dir}")
    logging.info("===================================================================")
    
    t_start = time.time()
    
    # 1. 扫描已有文件
    existing_files = get_existing_snapshot_files(output_dir)
    logging.info(f"[自检] 目录现有快照文件共 {len(existing_files)} 个: {list(existing_files.keys())}")
    
    # 确定检查的起始日期
    lookback_days = days if days is not None else 7
    check_start_date = today - timedelta(days=lookback_days)
    
    all_check_dates = []
    curr = check_start_date
    while curr <= today:
        all_check_dates.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
        
    # 识别缺失日期（以及今日始终需要校验）
    missing_dates = []
    for d_str in all_check_dates:
        if d_str not in existing_files or force:
            missing_dates.append(d_str)
        elif d_str == today_str:
            # 今日文件始终纳入校准范围
            missing_dates.append(d_str)
            
    # 特殊自检校准：检查 2026-09-13 与 2026-09-14 的错位
    if "2026-09-14" in existing_files and "2026-09-13" not in existing_files:
        try:
            df_check = pd.read_parquet(existing_files["2026-09-14"])
            if "RecipeLastModifiedDate" in df_check.columns:
                mod_dates = pd.to_datetime(df_check["RecipeLastModifiedDate"]).dt.date.unique()
                if len(mod_dates) > 0 and max(mod_dates) == datetime.strptime("2026-09-13", "%Y-%m-%d").date():
                    logging.info("[自检校准] 检测到原 2026-09-14.parquet 实际存储的是 2026-09-13 数据，加入 2026-09-13 补齐！")
                    if "2026-09-13" not in missing_dates:
                        missing_dates.append("2026-09-13")
        except Exception as e:
            logging.warning(f"读取校验 2026-09-14 文件异常: {e}")
            
    missing_dates = sorted(list(set(missing_dates)))
    logging.info(f"[自检] 待校准/补齐目标日期序列: {missing_dates}")
    logging.info(f"[自检] 待校准/补齐目标日期序列: {missing_dates}")
    
    if not missing_dates:
        logging.info("所有日期快照均已完整，无须补充。")
        return
        
    earliest_missing_str = missing_dates[0]
    logging.info(f"[自检] 最早需要回溯补充的日期为: {earliest_missing_str}")
    
    # 2. 从数据库拉取从最早缺失日期至今日的所有修改记录
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        all_dfs = []
        for cfg in active_configs:
            df_view = fetch_view_data(cursor, cfg, start_date=f"{earliest_missing_str} 00:00:00")
            if not df_view.empty:
                all_dfs.append(df_view)
                
        conn.close()
        
        df_fetched = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
        if not df_fetched.empty and "RecipeLastModifiedDate" in df_fetched.columns:
            df_fetched["RecipeLastModifiedDate"] = pd.to_datetime(df_fetched["RecipeLastModifiedDate"])
            df_fetched["ModDateStr"] = df_fetched["RecipeLastModifiedDate"].dt.strftime("%Y-%m-%d")
            logging.info(f"[数据库检索完成] 共检索到 {len(df_fetched)} 行新修改记录，分布工序与日期:")
            for item_name in df_fetched["Item"].unique():
                df_sub = df_fetched[df_fetched["Item"] == item_name]
                logging.info(f"  - [{item_name}] 共 {len(df_sub)} 行，分布: {df_sub['ModDateStr'].value_counts().to_dict()}")
        else:
            logging.info("[数据库检索完成] 该时间段内数据库无新修改记录。")
            
    except Exception as e:
        logging.error(f"数据库查询异常: {e}", exc_info=True)
        raise

    # 3. 初始化各工序基准生效配方快照（优先加载持久化基准底表）
    latest_active_dfs = {}  # item_label -> DataFrame
    baseline_path = os.path.join(output_dir, "recipe_full_baseline.parquet")
    
    if os.path.exists(baseline_path):
        try:
            logging.info(f"[基准加载] 发现持久化基准底表 {baseline_path}，正在加载作为全量初始基准...")
            df_base = pd.read_parquet(baseline_path)
            if "Item" in df_base.columns:
                for item_name in df_base["Item"].unique():
                    latest_active_dfs[item_name] = df_base[df_base["Item"] == item_name].reset_index(drop=True)
                    logging.info(f"   * [{item_name}] 初始基准: {len(latest_active_dfs[item_name])} 行, {latest_active_dfs[item_name]['MaterialMasterID'].nunique()} 规格")
        except Exception as e:
            logging.warning(f"读取持久化基准底表失败: {e}")
            
    # 若无持久化基准底表，回退扫描历史已有快照文件
    if not latest_active_dfs:
        earliest_missing_dt = datetime.strptime(earliest_missing_str, "%Y-%m-%d").date()
        for d_str, fpath in reversed(existing_files.items()):
            f_dt = datetime.strptime(d_str, "%Y-%m-%d").date()
            if f_dt < earliest_missing_dt:
                try:
                    logging.info(f"[基准加载] 加载已有快照 {d_str} 作为初始生效配方基准...")
                    df_base = pd.read_parquet(fpath)
                    if "Item" in df_base.columns:
                        for item_name in df_base["Item"].unique():
                            latest_active_dfs[item_name] = df_base[df_base["Item"] == item_name].reset_index(drop=True)
                    break
                except Exception as e:
                    logging.warning(f"读取基准文件 {fpath} 失败: {e}")
                    
    # 校验基准底盘健康度：若底表不存在或总规格过少（<100），说明尚未完成冷启动初始化，自动触发冷启动全量抽取
    total_baseline_mats = sum(df_sub['MaterialMasterID'].nunique() for df_sub in latest_active_dfs.values()) if latest_active_dfs else 0
    if total_baseline_mats < 100:
        logging.warning(f"[基准健康检查] 基准规格数不足 (当前仅 {total_baseline_mats} 个规格)，自动触发冷启动全量初始化抽取...")
        return run_full_refresh(active_configs, output_dir, force_rebuild=False)
                
    # 4. 按连续日期时序逐日增量刷新并校准（确保规格全量继承，绝不丢失）
    generated_files = []
    process_dates = [d for d in all_check_dates if d >= earliest_missing_str]
    dedup_keys = ["ProcessTypeID", "MaterialMasterID", "ParameterID", "Workcenter"]
    
    for d_str in process_dates:
        if d_str in missing_dates:
            logging.info(f"--> [正在增量刷新/校准日期] {d_str} ...")
            
            day_dfs = []
            item_counts = {}
            for cfg in active_configs:
                item_label = cfg["item"]
                # 检查数据库中当天该工序是否有修改
                df_item = pd.DataFrame()
                if not df_fetched.empty and "ModDateStr" in df_fetched.columns and "Item" in df_fetched.columns:
                    df_item = df_fetched[(df_fetched["ModDateStr"] == d_str) & (df_fetched["Item"] == item_label)].drop(columns=["ModDateStr"]).reset_index(drop=True)
                    
                if not df_item.empty:
                    # 当天有新修改，将新修改记录与前序基准合并
                    if item_label in latest_active_dfs and not latest_active_dfs[item_label].empty:
                        df_comb = pd.concat([df_item, latest_active_dfs[item_label]], ignore_index=True)
                    else:
                        df_comb = df_item
                        
                    df_comb["RecipeLastModifiedDate"] = pd.to_datetime(df_comb["RecipeLastModifiedDate"])
                    df_comb = df_comb.sort_values(by="RecipeLastModifiedDate", ascending=False)
                    # 按规格、参数、机台精准去重：修改的规格更新最新参数，未修改的规格全量继承原值
                    df_merged_item = df_comb.drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
                    
                    latest_active_dfs[item_label] = df_merged_item
                    day_dfs.append(df_merged_item)
                    item_counts[item_label] = (len(df_merged_item), df_merged_item['MaterialMasterID'].nunique(), f"增量更新({len(df_item)}条变更/{df_item['MaterialMasterID'].nunique()}规格)")
                else:
                    # 当天无新修改，100% 沿用上一日生效配方全量参数，确保任何规格不缺失
                    if item_label in latest_active_dfs and not latest_active_dfs[item_label].empty:
                        day_dfs.append(latest_active_dfs[item_label])
                        item_counts[item_label] = (len(latest_active_dfs[item_label]), latest_active_dfs[item_label]['MaterialMasterID'].nunique(), "全量继承")
                    else:
                        logging.warning(f"    [{item_label}] 当天无修改且无前序生效配方基准。")
                        
            if day_dfs:
                df_combined = pd.concat(day_dfs, ignore_index=True)
                fpath = save_daily_snapshot_parquet(df_combined, output_dir, snapshot_date_str=d_str)
                summary_items = ", ".join([f"{k}: {v[0]}行/{v[1]}规格({v[2]})" for k, v in item_counts.items()])
                generated_files.append((d_str, fpath, len(df_combined), summary_items))
            else:
                logging.warning(f"    [警告] 日期 {d_str} 无任何工序数据，跳过生成。")
        else:
            # 该日期文件已存在且不在缺失列表中，读取已存在的快照并增量合并至基准（只增不减）
            if d_str in existing_files:
                try:
                    logging.info(f"--> [已有快照更新基准] 读取已存在的 {d_str} 快照合并至继承基准...")
                    df_exist = pd.read_parquet(existing_files[d_str])
                    if "Item" in df_exist.columns:
                        for item_name in df_exist["Item"].unique():
                            df_sub = df_exist[df_exist["Item"] == item_name].reset_index(drop=True)
                            if item_name in latest_active_dfs and not latest_active_dfs[item_name].empty:
                                df_comb = pd.concat([df_sub, latest_active_dfs[item_name]], ignore_index=True)
                                df_comb["RecipeLastModifiedDate"] = pd.to_datetime(df_comb["RecipeLastModifiedDate"])
                                df_comb = df_comb.sort_values(by="RecipeLastModifiedDate", ascending=False)
                                latest_active_dfs[item_name] = df_comb.drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
                            else:
                                latest_active_dfs[item_name] = df_sub
                except Exception as e:
                    logging.warning(f"读取已有快照 {existing_files[d_str]} 失败: {e}")

    # 5. 更新持久化全量基准底表 recipe_full_baseline.parquet
    if latest_active_dfs:
        df_all_baseline = pd.concat(list(latest_active_dfs.values()), ignore_index=True)
        save_baseline_parquet(df_all_baseline, output_dir)
                
    t_end = time.time()
    logging.info("===================================================================")
    logging.info(f"================ CGRS 全量配方自检校准与补齐执行完成！ ================")
    logging.info(f"本次处理共生成/更新 {len(generated_files)} 个快照文件:")
    for d_str, fp, cnt, src in generated_files:
        logging.info(f"  - {d_str}: {os.path.basename(fp)} ({cnt} 行) [{src}]")
    logging.info(f"总耗时: {t_end - t_start:.2f} 秒")
    logging.info("===================================================================")
    return generated_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CGRS Full Recipe Released Parameters Auto-Calibrating Daily Exporter")
    parser.add_argument("--days", type=int, default=7, help="回溯检查天数 (默认: 7 天)")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Parquet 输出目录")
    parser.add_argument("--disable-123", action="store_true", help="临时禁用 123 硫化视图")
    parser.add_argument("--disable-125", action="store_true", help="临时禁用 125 PU 视图")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在日期的快照文件或强制重建缓存")
    parser.add_argument("--full-refresh", "--init", action="store_true", help="强制执行冷启动全量初始化抽取，重建 Master Baseline")
    
    args = parser.parse_args()
    export_cgrs_full_history(
        days=args.days,
        output_dir=args.output_dir,
        enable_123=not args.disable_123,
        enable_125=not args.disable_125,
        force=args.force,
        full_refresh=args.full_refresh
    )
