import os
import sys
import time
import json
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

# 配置路径与日志
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cgrs_export.log")
CHECKPOINT_FILE = os.path.join(LOG_DIR, "cgrs_checkpoint.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "cgrs_data")
DB_SERVER = r"OTTM09RMSMS02.tiremes.contiwan.com\OTT_I1"
DB_NAME = "CGRS_GLOBAL_REPORTS"

# 1. 成型 KM 工序 (ProcessTypeID: 119 - 24 项参数)
KM_PARAMS_PRIORITY = {
    "IL 安装摩擦": 1,
    "安装高度_IL": 3,
    "安装高度_PLY1": 3,
    "顶部辊压力 PLY1": 3,
    "高度_SW": 3,
    "左卷边罩位置_胎圈芯定位": 1,
    "右卷边罩位置_胎圈芯定位": 1,
    "卷边终端压力冲击": 2,
    "胶囊充气后的卷边罩等待时间": 1,
    "左侧胶囊高压时间": 2,
    "右侧胶囊高压时间": 2,
    "安装位置_IL": 1,
    "安装位置_PLY1": 1,
    "安装位置_PLY2": 1,
    "IL 安装速度": 1,
    "PLY 1 安装速度": 1,
    "PLY 1 安装摩擦": 1,
    "径向位置 PLY 1": 3,
    "左侧波纹管式支撑件胎圈芯放置位置": 3,
    "胎圈芯放置时间": 1,
    "安装位置_SW": 1,
    "SW 安装速度": 1,
    "左侧波纹管式支撑件安装位置": 3,
    "右侧波纹管式支撑件安装位置": 3,
}

# 2. 成型 PU 工序 (ProcessTypeID: 125 - 30 项参数)
PU_PARAMS_PRIORITY = {
    "胎面安装位置": 1,
    "带束层传输位置": 1,
    "胎面检查位置": 3,
    "BL安装速度": 2,
    "BR安装速度": 2,
    "TR安装速度": 2,
    "BTR": 1,
    "铁液罐距离": 3,
    "BD1胎面切割位置": 3,
    "BD2胎面切割位置": 3,
    "结合分段安装压力": 1,
    "结合分段接合压力": 1,
    "滚压辊压力": 1,
    "后定心辊压力": 2,
    "中间定心辊压力": 2,
    "前定心辊压力": 2,
    "带滚压辊速度": 2,
    "BL到BD的间距": 1,
    "BR到BD的间距": 1,
    "SH放置胎体位置": 1,
    "SH拉伸胎体位置": 1,
    "SH预弯曲成型位置": 1,
    "SH滚压位置": 1,
    "取出轮胎的SH位置": 3,
    "SH预弯曲成型压力": 1,
    "压制胎纹的 SH 压力": 1,
    "SH滚压压力": 1,
    "CTR直径": 3,
    "胎体装料机直径": 3,
    "胎体装载装置宽度偏移": 3
}

# 3. 硫化工序 (ProcessTypeID: 123 - 14 项参数)
CURING_PARAMS_PRIORITY = {
    "合模力": 1,
    "机械手装胎高度": 1,
    "二次定型-新胶囊": 1,
    "一次定型-新胶囊": 1,
    "一次定型": 1,
    "二次定型": 1,
    "中心机构定型位置（生胎高度）": 1,
    "定型阀门开启度（新胶囊）": 2,
    "定型阀门开启度": 2,
    "合模暂停时间": 3,
    "开模暂停时间": 3,
    "开模暂停压力": 3,
    "开模暂停位置（机器）": 3,
    "下环下降延迟（在脱模时）": 3
}

ALL_PARAMS_PRIORITY_MAP = {
    **KM_PARAMS_PRIORITY,
    **PU_PARAMS_PRIORITY,
    **CURING_PARAMS_PRIORITY
}

PROCESS_CONFIGS = [
    {
        "item": "KM",
        "process_type_id": "119",
        "name": "KM TBM Stage 1 (成型工序 KM)",
        "params_dict": KM_PARAMS_PRIORITY
    },
    {
        "item": "PU",
        "process_type_id": "125",
        "name": "PU TBM Stage 2 (成型工序 PU)",
        "params_dict": PU_PARAMS_PRIORITY
    },
    {
        "item": "Curing",
        "process_type_id": "123",
        "name": "Curing (硫化工序)",
        "params_dict": CURING_PARAMS_PRIORITY
    }
]

def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=60)

def get_last_watermark_local(output_dir):
    """
    基于本地时间 TechOffsetHistoryLocalDate 作为核心锚点：
    1. 优先读取 cgrs_checkpoint.json 中的 last_sync_local
    2. 若 checkpoint 不存在，扫描最新 Parquet 文件的 TechOffsetHistoryLocalDate 最大值
    3. 若为首次运行，默认回溯 3 天
    返回: (local_anchor_str, source_desc)
    """
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
                last_local_str = ckpt.get("last_sync_local")
                if last_local_str:
                    last_local = datetime.strptime(last_local_str, "%Y-%m-%d %H:%M:%S")
                    # 安全缓冲 2 分钟，防止并发修改遗漏
                    safe_local = last_local - timedelta(minutes=2)
                    return safe_local.strftime("%Y-%m-%d %H:%M:%S"), "Checkpoint文件"
        except Exception as e:
            logging.warning(f"读取 Checkpoint 文件失败: {e}，将扫描 Parquet 文件")

    if os.path.exists(output_dir):
        parquet_files = [f for f in os.listdir(output_dir) if f.startswith("recipe_offset_changes_") and f.endswith(".parquet")]
        if parquet_files:
            latest_file = sorted(parquet_files)[-1]
            file_path = os.path.join(output_dir, latest_file)
            try:
                df = pd.read_parquet(file_path, columns=["TechOffsetHistoryLocalDate"])
                if not df.empty and df["TechOffsetHistoryLocalDate"].notna().any():
                    max_local = pd.to_datetime(df["TechOffsetHistoryLocalDate"]).max()
                    safe_local = max_local.to_pydatetime() - timedelta(minutes=2)
                    return safe_local.strftime("%Y-%m-%d %H:%M:%S"), f"已存文件({latest_file})"
            except Exception as e:
                logging.warning(f"扫描最新 Parquet 文件失败: {e}")

    default_local = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    return default_local, "默认回溯3天"

def save_watermark_local(max_local_dt, new_records_count):
    """持久化记录当前成功同步的 TechOffsetHistoryLocalDate 本地时间戳锚点"""
    if max_local_dt is None:
        return
    try:
        data = {
            "last_sync_local": max_local_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "last_sync_utc": (max_local_dt - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            "sync_executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_batch_records": new_records_count
        }
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logging.info(f"[Checkpoint] 已更新本地时间锚点 (TechOffsetHistoryLocalDate) 至: {data['last_sync_local']}")
    except Exception as e:
        logging.warning(f"保存 Checkpoint 失败: {e}")

def local_to_query_start_date(local_dt_str):
    """将本地时间锚点转换为 SQL Server SP 所需的 StartDate (自动转换时区)"""
    try:
        dt = datetime.strptime(local_dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.strptime(local_dt_str, "%Y-%m-%d")
    # SQL Server SP 内部对比的是 UTC 时间 (Local - 8小时)
    query_dt = dt - timedelta(hours=8)
    return query_dt.strftime("%Y-%m-%d %H:%M:%S")

def build_openquery_sql(process_type_id, parameters_str, query_start_date_str):
    return f"""
    DECLARE @StartDate      NVARCHAR(30)  = N'{query_start_date_str}';
    DECLARE @ParameterNames NVARCHAR(MAX) = N'{parameters_str}';

    DECLARE @innerSql NVARCHAR(MAX) =
        'EXEC [dbo].[sp_CGRSReports_GetRecipeOffsetChanges] @ProcessTypeID = N''{process_type_id}'', @StartDate = '''
        + @StartDate + ''', @ParameterNames = N''' + @ParameterNames + '''';
    SET @innerSql = REPLACE(@innerSql, '''', '''''');

    DECLARE @sql NVARCHAR(MAX) =
        N'SELECT *
          FROM OPENQUERY([CGRS_9200], ''' + @innerSql + N''')
          ORDER BY TechOffsetHistoryLocalDate DESC';

    EXEC sp_executesql @sql;
    """

def fetch_process_data(cursor, config, local_anchor_str):
    item_label = config["item"]
    proc_id = config["process_type_id"]
    proc_name = config["name"]
    params_dict = config["params_dict"]
    params_str = ",".join(params_dict.keys())
    
    query_start_date_str = local_to_query_start_date(local_anchor_str)
    logging.info(f"--> 正在增量查询 [{item_label}] 工序 [{proc_id} - {proc_name}] (本地锚点: {local_anchor_str} 起)...")
    t0 = time.time()
    
    sql = build_openquery_sql(proc_id, params_str, query_start_date_str)
    cursor.execute(sql)
    
    columns = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    t1 = time.time()
    
    logging.info(f"    [{item_label}] 查询完成！耗时: {t1-t0:.2f} 秒, 增量获取: {len(rows)} 行")
    if not rows:
        return pd.DataFrame()
        
    data_dict = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
    df = pd.DataFrame(data_dict)
    
    df['Item'] = item_label
    df['Priority'] = df['ParameterLocalName'].map(params_dict).fillna(3).astype(int)
    return df

def save_and_merge_daily_parquets(df_new, output_dir):
    """基于本地时间 TechOffsetHistoryLocalDate 拆分日份并智能去重合并"""
    date_col = 'TechOffsetHistoryLocalDate'
    df_new[date_col] = pd.to_datetime(df_new[date_col])
    df_new['export_date_str'] = df_new[date_col].dt.strftime('%Y-%m-%d')
    
    saved_files = []
    t_save_start = time.time()
    
    for date_str, group in df_new.groupby('export_date_str'):
        clean_new = group.drop(columns=['export_date_str'])
        file_name = f"recipe_offset_changes_{date_str}.parquet"
        file_path = os.path.join(output_dir, file_name)
        
        if os.path.exists(file_path):
            try:
                df_existing = pd.read_parquet(file_path)
                df_merged = pd.concat([df_existing, clean_new], ignore_index=True)
                
                # 去重判定 (按 配方ID + 参数ID + 机台 + 本地修改时间)
                dedup_cols = ['RecipeID', 'ParameterID', 'Workcenter', 'TechOffsetHistoryLocalDate']
                if all(c in df_merged.columns for c in dedup_cols):
                    df_merged = df_merged.drop_duplicates(subset=dedup_cols, keep='last')
                else:
                    df_merged = df_merged.drop_duplicates(keep='last')
                    
                df_to_save = df_merged
                action = f"增量合并 (累计 {len(df_to_save)} 行)"
            except Exception as e:
                logging.warning(f"读取已有文件 {file_name} 失败: {e}，将直接覆盖")
                df_to_save = clean_new
                action = f"直接覆盖 ({len(df_to_save)} 行)"
        else:
            df_to_save = clean_new
            action = f"新建文件 ({len(df_to_save)} 行)"
            
        # 排序：按本地时间倒序、优先级升序
        df_to_save = df_to_save.sort_values(by=[date_col, 'Priority'], ascending=[False, True]).reset_index(drop=True)
        df_to_save.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")
        
        file_size_kb = os.path.getsize(file_path) / 1024
        saved_files.append(file_path)
        
        km_count = (df_to_save['Item'] == 'KM').sum() if 'Item' in df_to_save.columns else 0
        pu_count = (df_to_save['Item'] == 'PU').sum() if 'Item' in df_to_save.columns else 0
        curing_count = (df_to_save['Item'] == 'Curing').sum() if 'Item' in df_to_save.columns else 0
        
        logging.info(f"[更新 Parquet] 日期: {date_str} | {action} (KM: {km_count}, PU: {pu_count}, 硫化: {curing_count}) | 文件: {file_name} ({file_size_kb:.2f} KB)")
        
    t_save_end = time.time()
    return saved_files, t_save_end - t_save_start

def export_cgrs_data(days=None, start_date=None, output_dir=DEFAULT_OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    
    # 确定本地时间锚点
    if start_date:
        local_anchor_str = start_date
        mode_desc = f"指定本地起始日期: {local_anchor_str}"
    elif days is not None:
        local_anchor_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        mode_desc = f"指定本地回溯天数: {days} 天 (自 {local_anchor_str} 起)"
    else:
        local_anchor_str, source_desc = get_last_watermark_local(output_dir)
        mode_desc = f"本地时间锚点智能增量 (来源: {source_desc}, 锚点起始: {local_anchor_str})"
        
    logging.info("===================================================================")
    logging.info("========== 开始执行 CGRS 数据同步 (KM + PU + Curing) ==========")
    logging.info(f"模式: {mode_desc}")
    logging.info(f"目标数据库: {DB_SERVER} -> {DB_NAME}")
    logging.info(f"保存目录: {output_dir}")
    logging.info("===================================================================")

    t_start_all = time.time()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        all_dfs = []
        for config in PROCESS_CONFIGS:
            df_proc = fetch_process_data(cursor, config, local_anchor_str)
            if not df_proc.empty:
                all_dfs.append(df_proc)
                
        conn.close()
        
        if not all_dfs:
            logging.info("--> 检查完毕：自上次同步以来，无新的参数修改记录，Parquet 文件已是最新状态。")
            logging.info("===================================================================")
            return []
            
        df_combined = pd.concat(all_dfs, ignore_index=True)
        new_records_count = len(df_combined)
        logging.info(f"\n[增量抓取成功] 本次抓取到新变更记录: {new_records_count} 行")
        
        # 智能合并写入 Parquet
        saved_files, save_duration = save_and_merge_daily_parquets(df_combined, output_dir)
        
        # 更新 Checkpoint 本地时间锚点
        if 'TechOffsetHistoryLocalDate' in df_combined.columns and df_combined['TechOffsetHistoryLocalDate'].notna().any():
            max_local_dt = pd.to_datetime(df_combined['TechOffsetHistoryLocalDate']).max().to_pydatetime()
            save_watermark_local(max_local_dt, new_records_count)
            
        t_end_all = time.time()
        logging.info("===================================================================")
        logging.info(f"================ 同步完成！更新了 {len(saved_files)} 个日份文件 ================")
        logging.info(f"总耗时: {t_end_all - t_start_all:.2f} 秒 (其中 Parquet 合并写入耗时: {save_duration:.2f} 秒)")
        logging.info("===================================================================")
        
        return saved_files
        
    except Exception as e:
        logging.error(f"同步数据过程发生错误: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CGRS SQL Server Incremental Parquet Exporter (TechOffsetHistoryLocalDate Anchor)")
    parser.add_argument("--days", type=int, default=None, help="手动指定回溯天数 (默认: 智能从上一次 TechOffsetHistoryLocalDate 未读取的水印开始)")
    parser.add_argument("--start-date", type=str, default=None, help="手动指定本地起始时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Parquet 文件导出目录")
    
    args = parser.parse_args()
    export_cgrs_data(days=args.days, start_date=args.start_date, output_dir=args.output_dir)
