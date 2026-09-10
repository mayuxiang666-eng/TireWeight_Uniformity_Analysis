# -*- coding: utf-8 -*-
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import duckdb
import os
import sys
import json
from datetime import datetime, timedelta
import numpy as np
import math
# from kmeans_service import get_kmeans_diagnostics, get_kmeans_paths, get_kmeans_labeled_data

if getattr(sys, 'frozen', False):
    _static_base = sys._MEIPASS
else:
    _static_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_frontend_dist_candidate = os.path.join(_static_base, "frontend", "dist")
_root_dist_candidate = os.path.join(_static_base, "dist")
FRONTEND_DIST = _frontend_dist_candidate if os.path.isdir(_frontend_dist_candidate) else _root_dist_candidate

app = FastAPI(title="轮胎质量分析看板 API", version="1.1.1")


def sanitize_data(obj):
    if isinstance(obj, dict):
        return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_data(x) for x in obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_data(x) for x in obj.tolist()]
    elif hasattr(obj, "item") and callable(getattr(obj, "item", None)):
        return obj.item()
    else:
        return obj

# ... (rest of middleware, paths, and qry helper unchanged) ...

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_cleaned_data_path():
    _BASE = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(_BASE)
    candidates = [
        os.path.join(_BASE, "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(root_dir, "backend", "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(root_dir, "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(os.getcwd(), "backend", "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(os.getcwd(), "data", "yield_flat_table_joined_100_cleaned.parquet"),
        "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
    ]
    existing = [c for c in candidates if os.path.exists(c)]
    if existing:
        return max(existing, key=os.path.getmtime)
    return os.path.join(_BASE, "data", "yield_flat_table_joined_100_cleaned.parquet")

def get_cgrs_data_path():
    _BASE = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(_BASE)
    # 优先检查 cgrs_data 目录（包含每日 Parquet 增量文件，优先使用服务器共享或项目根目录路径）
    dir_candidates = [
        r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data",
        os.path.join(root_dir, "cgrs_data"),
        os.path.join(_BASE, "..", "cgrs_data"),
        os.path.join(_BASE, "data", "cgrs_data"),
        os.path.join(root_dir, "backend", "data", "cgrs_data"),
        os.path.join(root_dir, "data", "cgrs_data"),
        os.path.join(os.getcwd(), "cgrs_data"),
        os.path.join(os.getcwd(), "backend", "data", "cgrs_data"),
        os.path.join(os.getcwd(), "data", "cgrs_data"),
    ]
    for d in dir_candidates:
        if os.path.isdir(d):
            import glob
            if glob.glob(os.path.join(d, "*.parquet")):
                return os.path.abspath(d) if not d.startswith("\\\\") else d
    
    # 备用兼容单个 CGRS.parquet 或 CGRS.csv 文件
    candidates = [
        r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data\CGRS.parquet",
        os.path.join(root_dir, "cgrs_data", "CGRS.parquet"),
        os.path.join(_BASE, "data", "CGRS.parquet"),
        os.path.join(root_dir, "backend", "data", "CGRS.parquet"),
        os.path.join(_BASE, "data", "CGRS.csv"),
        os.path.join(root_dir, "backend", "data", "CGRS.csv"),
        os.path.join(root_dir, "data", "CGRS.csv"),
        os.path.join(os.getcwd(), "backend", "data", "CGRS.csv"),
        os.path.join(os.getcwd(), "data", "CGRS.csv"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c) if not c.startswith("\\\\") else c
    return r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data"

DATA_PATH = get_cleaned_data_path()
CACHED_ROW_COUNT = 0

# 全局 DuckDB 常驻连接与内存表，将 Parquet 数据与 CGRS 载入内存以提升并发检索速度
db_conn = duckdb.connect()

def reload_duckdb_data():
    """重新加载数据并重建内存表"""
    global DATA_PATH, CACHED_ROW_COUNT
    DATA_PATH = get_cleaned_data_path()
    if os.path.exists(DATA_PATH):
        db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")
        try:
            cols = [r[0] for r in db_conn.execute("DESCRIBE clean_yield").fetchall()]
            if 'tu_first_shift_date' not in cols:
                db_conn.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_shift_date VARCHAR")
            if 'tu_first_loc_timestamp' in cols:
                db_conn.execute("UPDATE clean_yield SET tu_first_shift_date = STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')")
            elif 'tu_first_shift_date' in cols and 'tu_first_loc_timestamp' not in cols:
                db_conn.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_loc_timestamp VARCHAR")
                db_conn.execute("UPDATE clean_yield SET tu_first_loc_timestamp = tu_first_shift_date")
            
            cnt_res = db_conn.execute("SELECT COUNT(*) FROM clean_yield").fetchone()
            CACHED_ROW_COUNT = cnt_res[0] if cnt_res else 0
        except Exception:
            pass
    
    cgrs_path = get_cgrs_data_path()
    if cgrs_path and os.path.exists(cgrs_path):
        normalized_cgrs = cgrs_path.replace('\\', '/')
        if os.path.isdir(cgrs_path) or 'cgrs_data' in normalized_cgrs or normalized_cgrs.endswith('.parquet'):
            parquet_target = os.path.join(normalized_cgrs, "*.parquet").replace('\\', '/') if os.path.isdir(cgrs_path) else normalized_cgrs
            db_conn.execute(f"""
                CREATE OR REPLACE TABLE cgrs_records AS 
                SELECT 
                    *,
                    TRY_CAST(TechOffsetHistoryLocalDate AS DATE) AS match_date,
                    TRY_CAST(TechOffsetHistoryLocalDate AS TIMESTAMP) AS event_timestamp
                FROM read_parquet('{parquet_target}', union_by_name=True)
            """)
        else:
            db_conn.execute(f"""
                CREATE OR REPLACE TABLE cgrs_records AS 
                SELECT 
                    *,
                    COALESCE(
                        TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetHistoryLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
                        TRY_CAST(SPLIT_PART(TechOffsetHistoryLocalDate, ' ', 1) AS DATE),
                        TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
                        TRY_CAST(SPLIT_PART(TechOffsetLocalDate, ' ', 1) AS DATE)
                    ) AS match_date,
                    COALESCE(
                        TRY_CAST(STRPTIME(TechOffsetHistoryLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetHistoryLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
                        TRY_CAST(TechOffsetHistoryLocalDate AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
                        TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
                    ) AS event_timestamp
                FROM read_csv_auto('{normalized_cgrs}', all_varchar=True)
            """)
        return True
    return os.path.exists(DATA_PATH)

reload_duckdb_data()

def build_production_time_where(
    time_col: str = "tu_first_loc_timestamp",
    date_single: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    shift: Optional[str] = None
) -> str:
    """
    构造 DuckDB SQL WHERE 时间条件。
    天的划分：精细到分，从第一天 08:00:00 到第二天 08:00:00 作为一天的划分。
    班组划分：
      - 'all' / None: 08:00 ~ 次日08:00
      - 'morning': 08:00 ~ 16:00
      - 'middle': 16:00 ~ 24:00
      - 'night': 24:00 ~ 08:00 (次日00:00~08:00)
    """
    col_ref = time_col if time_col else "tu_first_loc_timestamp"
    ts_expr = f"TRY_CAST({col_ref} AS TIMESTAMP)"
    prod_date_expr = f"CAST(({ts_expr} - INTERVAL 8 HOUR) AS DATE)"
    
    conds = [f"{col_ref} IS NOT NULL"]
    
    if date_single:
        conds.append(f"{prod_date_expr} = '{date_single}'")
    elif date_from and date_to:
        conds.append(f"{prod_date_expr} BETWEEN '{date_from}' AND '{date_to}'")
    elif date_from:
        conds.append(f"{prod_date_expr} >= '{date_from}'")
    elif date_to:
        conds.append(f"{prod_date_expr} <= '{date_to}'")
        
    if shift and shift != 'all':
        hr_expr = f"EXTRACT(HOUR FROM {ts_expr})"
        if shift == 'morning':
            conds.append(f"({hr_expr} >= 8 AND {hr_expr} < 16)")
        elif shift == 'middle':
            conds.append(f"({hr_expr} >= 16 AND {hr_expr} < 24)")
        elif shift == 'night':
            conds.append(f"({hr_expr} >= 0 AND {hr_expr} < 8)")
            
    return " AND ".join(conds)

@app.post("/api/system/restart")
@app.get("/api/system/restart")
def restart_service():
    """重启后端服务进程（由 NSSM 服务监控守护进程自动拉起最新代码）"""
    import threading
    import time
    def _do_restart():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "success", "message": "后端服务正在重启重载..."}


@app.get("/api/cgrs/records")
def get_cgrs_records(
    workcenter: str = Query(..., description="成型机台编号，如 TB122 或 TB283"),
    date: str = Query(..., description="查询日期，格式 YYYY-MM-DD"),
    article: Optional[str] = Query(None, description="规格代码 article10 (可选，支持精确与7位前缀匹配)"),
    indicator: Optional[str] = Query("rfpp", description="指标类型，如 rfpp, rfh1, cony, weight")
):
    """根据成型机台编号、日期以及规格代码查询 CGRS 参数修改记录（支持精确匹配与一段/二段机台编号兼容映射、规格7位/10位代码兼容匹配，并附带修改前后 50 条 CPK 对比数据）"""
    try:
        if hasattr(workcenter, "default"):
            workcenter = workcenter.default if workcenter.default is not ... else ""
        if hasattr(date, "default"):
            date = date.default if date.default is not ... else ""
        if hasattr(article, "default"):
            article = article.default if article.default is not ... else None
        if hasattr(indicator, "default"):
            indicator = indicator.default if indicator.default is not ... else "rfpp"
        
        wc_clean = str(workcenter or "").strip().upper()
        # 兼容映射候选集（成型机 TB2xx 与 TB1xx 双向自动关联，硫化机 CUxx 精确匹配）
        is_cu = wc_clean.startswith("CU")
        cgrs_candidates = [wc_clean]
        mach_candidates = [wc_clean]
        if is_cu:
            wc_col = "ct_workcenter"
            time_col = "ct_loc_timestamp"
        else:
            wc_col = "gt_workcenter"
            time_col = "gt_loc_timestamp"
            if wc_clean.startswith("TB2"):
                cgrs_candidates.append("TB1" + wc_clean[3:])
                mach_candidates.append("TB" + wc_clean[3:])
            elif wc_clean.startswith("TB1"):
                cgrs_candidates.append("TB2" + wc_clean[3:])
                mach_candidates.append("TB2" + wc_clean[3:])
                mach_candidates.append("TB" + wc_clean[3:])
            elif wc_clean.startswith("TB") and len(wc_clean) >= 4:
                cgrs_candidates.append("TB1" + wc_clean[2:])
                cgrs_candidates.append("TB2" + wc_clean[2:])
                mach_candidates.append("TB2" + wc_clean[2:])
        cgrs_candidates = list(dict.fromkeys(cgrs_candidates))
        mach_candidates = list(dict.fromkeys(mach_candidates))
        
        cgrs_placeholders = ",".join(["?"] * len(cgrs_candidates))
        mach_placeholders = ",".join(["?"] * len(mach_candidates))
        
        # 优先按当天 TU 终检轮胎的成型(GT)/硫化(CT)生产时间区间 [min_time, max_time] 圈定调参
        range_sql_parts = [
            f"{wc_col} IN ({mach_placeholders})",
            "TRY_CAST(tu_first_loc_timestamp AS DATE) = ?::DATE",
            f"{time_col} IS NOT NULL"
        ]
        range_params = list(mach_candidates) + [date]
        if not is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            range_sql_parts.append("(article10 = ? OR article10 LIKE ?)")
            range_params.extend([art_clean, f"{prefix7}%"])

        range_sql = f"""
            SELECT
                MIN(TRY_CAST({time_col} AS TIMESTAMP)) AS min_time,
                MAX(TRY_CAST({time_col} AS TIMESTAMP)) AS max_time
            FROM clean_yield
            WHERE {" AND ".join(range_sql_parts)}
        """
        try:
            range_rows = qry(range_sql, range_params)
            min_time = range_rows[0]['min_time'] if range_rows else None
            max_time = range_rows[0]['max_time'] if range_rows else None
        except Exception:
            min_time, max_time = None, None

        if not (min_time and max_time):
            comparison = calculate_cgrs_cpk_comparison(
                workcenter=workcenter,
                article10=article,
                target_date=date,
                indicator=indicator or "rfpp",
                limit_n=20
            )
            return {
                "status": "success",
                "data": [],
                "comparison": sanitize_data(comparison),
                "meta": {
                    "workcenter": workcenter,
                    "date": date,
                    "article": article,
                    "indicator": indicator,
                    "count": 0,
                    "matched_candidates": cgrs_candidates,
                    "no_samples": True,
                    "message": f"机台 [{workcenter}] 在 [{date}] 无生产样本数据"
                }
            }

        sql = f"""
            SELECT 
                event_timestamp,
                TechOffsetHistoryLocalDate,
                TechOffsetLocalDate,
                Workcenter,
                COALESCE(NULLIF(ParameterLocalName, ''), ParameterGlobalName, ParameterName) AS ParameterLocalName,
                ParameterGlobalName,
                ParameterName,
                ParameterValue,
                TechOffsetHistoryValueFrom,
                TechOffsetHistoryValueTo,
                TechOffsetValue,
                ParameterUnitSymbol,
                ProdSpecific2,
                RecipeDescription,
                UserName,
                ProcessTypeName,
                COALESCE(CAST(Item AS VARCHAR), '') AS Item,
                Priority,
                COALESCE(CAST(TechOffsetComments AS VARCHAR), CAST(TechOffsetHistoryComments AS VARCHAR), '') AS comments
            FROM cgrs_records
            WHERE Workcenter IN ({cgrs_placeholders})
              AND event_timestamp IS NOT NULL
              AND TRY_CAST(event_timestamp AS TIMESTAMP) >= ?::TIMESTAMP
              AND TRY_CAST(event_timestamp AS TIMESTAMP) <= ?::TIMESTAMP
        """
        params = list(cgrs_candidates) + [str(min_time), str(max_time)]
        
        if not is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            sql += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ? OR RecipeDescription LIKE ?)"
            params.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%", f"%{prefix7}%"])
        
        sql += " ORDER BY event_timestamp DESC, TechOffsetHistoryLocalDate DESC"
        rows = qry(sql, params)
        
        # 计算该机台在当前日期与规格下的前后 50 条 CPK 对比数据
        comparison = calculate_cgrs_cpk_comparison(
            workcenter=workcenter,
            article10=article,
            target_date=date,
            indicator=indicator or "rfpp",
            limit_n=20
        )
        
        return {
            "status": "success",
            "data": sanitize_data(rows),
            "comparison": sanitize_data(comparison),
            "meta": {
                "workcenter": workcenter,
                "date": date,
                "article": article,
                "indicator": indicator,
                "count": len(rows),
                "matched_candidates": cgrs_candidates
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"查询 CGRS 记录失败: {str(e)}",
            "data": [],
            "comparison": {"has_cgrs": False, "events_count": 0, "events": []}
        }



def qry(sql: str, params=None):
    """执行 DuckDB 查询，使用线程安全 Cursor 并支持参数化绑定以消除 SQL 注入风险"""
    cursor = db_conn.cursor()
    if params:
        rel = cursor.execute(sql, params)
    else:
        rel = cursor.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    cursor.close()
    return [dict(zip(cols, r)) for r in rows]


def get_spec_usl(article10: str, indicator: str) -> float:
    """获取指定规格在数据库中的规格上限值 (标准值 * 10)"""
    if not article10:
        return 100.0
    if indicator == "weight":
        return 0.28
    if indicator == "rfpp":
        sql = """
            SELECT COALESCE(ANY_VALUE(standard_rfpp),
                            CASE ANY_VALUE("group")
                                WHEN 'GROUP 1'  THEN 10.5
                                WHEN 'GROUP 2A' THEN 11.5
                                WHEN 'GROUP 2B' THEN 12.5
                                WHEN 'GROUP 3'  THEN 12.5
                                WHEN 'GROUP 4'  THEN 14.5
                            END) * 10.0 AS usl
            FROM clean_yield
            WHERE article10 = ?
        """
    elif indicator == "cony":
        sql = """
            SELECT ANY_VALUE(conny_usl) AS usl
            FROM clean_yield
            WHERE article10 = ? AND conny_usl IS NOT NULL
        """
        res = qry(sql, [article10])
        if res and res[0]['usl'] is not None:
            return float(res[0]['usl'])
        return 95.0
    else:
        sql = """
            SELECT COALESCE(ANY_VALUE(standard_rfh1),
                            CASE ANY_VALUE("group")
                                WHEN 'GROUP 1'  THEN 7.5
                                WHEN 'GROUP 2A' THEN 8.5
                                WHEN 'GROUP 2B' THEN 9.0
                                WHEN 'GROUP 3'  THEN 9.5
                                WHEN 'GROUP 4'  THEN 10.0
                            END) * 10.0 AS usl
            FROM clean_yield
            WHERE article10 = ?
        """
    res = qry(sql, [article10])
    if res and res[0]['usl'] is not None:
        return float(res[0]['usl'])
    return 100.0
@app.get("/api/article/phase")
def get_article_phase_endpoint(article10: str = Query(...)):
    if not article10:
        return {"status": "success", "data": {"phase_label": "", "p3_count": 0, "p4_count": 0}}
    try:
        parquet_path = get_cleaned_data_path()
        con = duckdb.connect()
        sql = f"""
            SELECT 
                SUM(CASE WHEN LOWER(ct_shop) LIKE '%p4%' THEN 1 ELSE 0 END) as p4_cnt,
                SUM(CASE WHEN LOWER(ct_shop) NOT LIKE '%p4%' OR ct_shop IS NULL THEN 1 ELSE 0 END) as p3_cnt
            FROM read_parquet('{parquet_path}')
            WHERE article10 = '{article10}'
        """
        df_res = con.execute(sql).df()
        con.close()
        p4 = int(df_res.iloc[0]['p4_cnt'] or 0)
        p3 = int(df_res.iloc[0]['p3_cnt'] or 0)
        if p4 > 0 and p3 == 0:
            phase_label = "四期"
        elif p3 > 0 and p4 == 0:
            phase_label = "三期"
        elif p3 + p4 > 0:
            phase_label = "三期 & 四期"
        else:
            phase_label = ""
        return {
            "status": "success",
            "data": {
                "article10": article10,
                "phase_label": phase_label,
                "p3_count": p3,
                "p4_count": p4
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_spec_limits(article10: str, indicator: str):
    """获取指定规格的上下限元组 (usl, lsl)
    - rfpp/rfh1: 返回 (usl, None)  — 单侧上限
    - cony:      返回 (conny_usl, conny_lsl) — 从数据库取双侧限
    - weight:    返回 (0.28, -0.28) — 固定 ±0.28% 公差
    """
    if indicator == "weight":
        return 0.28, -0.28
    if indicator in ("rfpp", "rfh1"):
        return get_spec_usl(article10, indicator), None
    if indicator == "cony":
        if not article10:
            return 95.0, -95.0
        sql = """
            SELECT ANY_VALUE(conny_usl) as usl_v, ANY_VALUE(conny_lsl) as lsl_v
            FROM clean_yield
            WHERE article10 = ? AND conny_usl IS NOT NULL AND conny_lsl IS NOT NULL
        """
        res = qry(sql, [article10])
        if res and res[0]['usl_v'] is not None and res[0]['lsl_v'] is not None:
            return float(res[0]['usl_v']), float(res[0]['lsl_v'])
        return 95.0, -95.0
    return 100.0, None


def calc_cpk(mean: float, std: float, usl: float, lsl=None) -> float:
    """统一计算单侧或双侧 CPK (支持负值以真实反映超差程度)
    - lsl 为 None 时：单侧上限 CPK = (usl - mean) / (3 * std)
    - lsl 存在时：  双侧 CPK = min((usl - mean)/(3*std), (mean - lsl)/(3*std))
    """
    if std <= 1e-6:
        return 1.33
    if lsl is None:
        return max(-5.0, min(5.0, (usl - mean) / (3.0 * std)))
    cpu = (usl - mean) / (3.0 * std)
    cpl = (mean - lsl) / (3.0 * std)
    return max(-5.0, min(5.0, min(cpu, cpl)))


def compute_cgrs_controlled_analysis_data(
    workcenter: str,
    date: str,
    article: Optional[str] = None,
    indicator: str = "rfpp",
    top_machines: Optional[str] = None,
    same_day_only: bool = False,
    limit_per_path: int = 20,
    min_samples_threshold: int = 1
):
    """
    成型机 CGRS 控制变量分析核心计算引擎（成型 GT ➔ 硫化 CT ➔ 终检 TU 全流程路径拆分与有效路径加总 CPK 对照）
    """
    if not workcenter:
        return {"status": "error", "message": "缺少成型机台编号 workcenter", "has_cgrs": False, "events": []}
        
    wc_clean = str(workcenter).strip().upper()
    is_cu = wc_clean.startswith("CU")
    
    cgrs_candidates = [wc_clean]
    mach_candidates = [wc_clean]

    if is_cu:
        wc_col = "ct_workcenter"
        time_col = "ct_loc_timestamp"
    else:
        wc_col = "gt_workcenter"
        time_col = "gt_loc_timestamp"
        if wc_clean.startswith("TB2"):
            cgrs_candidates.append("TB1" + wc_clean[3:])
            mach_candidates.append("TB" + wc_clean[3:])
        elif wc_clean.startswith("TB1"):
            cgrs_candidates.append("TB2" + wc_clean[3:])
            mach_candidates.append("TB2" + wc_clean[3:])
            mach_candidates.append("TB" + wc_clean[3:])
        elif wc_clean.startswith("TB") and len(wc_clean) >= 4:
            cgrs_candidates.append("TB1" + wc_clean[2:])
            cgrs_candidates.append("TB2" + wc_clean[2:])
            mach_candidates.append("TB2" + wc_clean[2:])

    cgrs_candidates = list(dict.fromkeys(cgrs_candidates))
    mach_candidates = list(dict.fromkeys(mach_candidates))

    # 解析前端传入的 Top 3 嫌疑机台
    suspect_list = []
    if top_machines:
        suspect_list = [m.strip().upper() for m in str(top_machines).split(',') if m.strip()]

    cgrs_placeholders = ",".join(["?"] * len(cgrs_candidates))
    mach_placeholders = ",".join(["?"] * len(mach_candidates))

    # 圈出样本池（根据 tu_first_shift_date = 目标日期 圈选，提取生产时间范围 [min_time, max_time]）
    range_sql_parts = [
        f"{wc_col} IN ({mach_placeholders})",
        "TRY_CAST(tu_first_loc_timestamp AS DATE) = ?::DATE",
        f"{time_col} IS NOT NULL"
    ]
    range_params = list(mach_candidates) + [date]
    if article and article.strip():
        art_clean = article.strip()
        prefix7 = art_clean[:7]
        range_sql_parts.append("(article10 = ? OR article10 LIKE ?)")
        range_params.extend([art_clean, f"{prefix7}%"])

    range_sql = f"""
        SELECT
            MIN(TRY_CAST({time_col} AS TIMESTAMP)) AS min_time,
            MAX(TRY_CAST({time_col} AS TIMESTAMP)) AS max_time
        FROM clean_yield
        WHERE {" AND ".join(range_sql_parts)}
    """
    try:
        range_rows = qry(range_sql, range_params)
        min_time = range_rows[0]['min_time'] if range_rows else None
        max_time = range_rows[0]['max_time'] if range_rows else None
    except Exception:
        min_time, max_time = None, None

    if not (min_time and max_time):
        return {
            "status": "success",
            "has_cgrs": False,
            "events_count": 0,
            "message": f"机台 [{workcenter}] 在 [{date}] 当天无生产样本数据，无法计算时间匹配 CGRS 调参记录",
            "conclusion_type": "no_samples",
            "conclusion_title": "无生产样本数据",
            "conclusion_text": f"机台 [{workcenter}] 在 [{date}] 未查询到生产样本数据，无法计算时间段匹配 CGRS 调参记录",
            "events": []
        }

    # 放宽观察范围：从这批圈定样本最早加工时间前 48 小时（涵盖开机调试/前置调参）到最晚加工时间
    cgrs_sql = f"""
        SELECT
            event_timestamp,
            TechOffsetHistoryLocalDate,
            TechOffsetLocalDate,
            Workcenter,
            COALESCE(NULLIF(ParameterLocalName, ''), ParameterGlobalName, ParameterName) AS ParameterLocalName,
            ParameterGlobalName,
            ParameterName,
            ParameterValue,
            TechOffsetHistoryValueFrom,
            TechOffsetHistoryValueTo,
            TechOffsetValue,
            ParameterUnitSymbol,
            ProdSpecific2,
            UserName,
            ProcessTypeName,
            COALESCE(CAST(Item AS VARCHAR), '') AS Item,
            Priority,
            COALESCE(CAST(TechOffsetComments AS VARCHAR), CAST(TechOffsetHistoryComments AS VARCHAR), '') AS comments
        FROM cgrs_records
        WHERE Workcenter IN ({cgrs_placeholders})
          AND event_timestamp IS NOT NULL
          AND TRY_CAST(event_timestamp AS TIMESTAMP) >= ?::TIMESTAMP
          AND TRY_CAST(event_timestamp AS TIMESTAMP) <= ?::TIMESTAMP
    """
    cgrs_params = list(cgrs_candidates) + [str(min_time), str(max_time)]

    if not is_cu and article and article.strip():
        art_clean = article.strip()
        prefix7 = art_clean[:7]
        cgrs_sql += " AND (ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ?)"
        cgrs_params.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%"])

    cgrs_sql += " ORDER BY event_timestamp DESC, TechOffsetHistoryLocalDate DESC"

    try:
        cgrs_rows = qry(cgrs_sql, cgrs_params)
    except Exception:
        cgrs_rows = []

    if not cgrs_rows:
        return {
            "status": "success",
            "has_cgrs": False,
            "events_count": 0,
            "message": f"机台 [{workcenter}] 在 [{date}] 未查询到 CGRS 调参记录",
            "conclusion_type": "no_cgrs",
            "conclusion_title": "未查询到调参记录",
            "conclusion_text": f"机台 [{workcenter}] 在 [{date}] 未查询到 CGRS 调参记录，无法执行控制变量排查",
            "events": []
        }

    # 聚合成调参事件（自动合并 5 分钟 / 300 秒内同批次调参记录，避免多参数分布式提交导致拆解成 0 样本事件）
    clustered_events = []
    for r in cgrs_rows:
        ts = r.get('event_timestamp')
        if not ts:
            continue
        matched_cluster = None
        for cl in clustered_events:
            if abs((cl['timestamp'] - ts).total_seconds()) <= 300:
                matched_cluster = cl
                break

        def format_val_num(val):
            if val is None:
                return '0'
            try:
                f = float(val)
                if abs(f - round(f)) < 1e-6:
                    return str(int(round(f)))
                return f"{round(f, 3):g}"
            except (ValueError, TypeError):
                return str(val)

        def safe_float(v, default=0.0):
            if v is None or v == '' or v == 'None' or str(v).strip() == '':
                return default
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        # 3. 修改后变更值 = ParameterValue + TechOffsetHistoryValueTo (优先使用历史变更目标值)
        param_base = safe_float(r.get('ParameterValue'), 0.0)
        offset_from = safe_float(r.get('TechOffsetHistoryValueFrom'), 0.0)

        offset_to_raw = r.get('TechOffsetHistoryValueTo')
        if offset_to_raw is None or str(offset_to_raw).strip() == '':
            offset_to_raw = r.get('TechOffsetValue')
        offset_to = safe_float(offset_to_raw, 0.0)

        calc_from_val = param_base + offset_from
        calc_to_val = param_base + offset_to

        p_name = r.get('ParameterLocalName') or r.get('ParameterGlobalName') or r.get('ParameterName') or '参数变更'
        param_item = {
            "param_local": p_name,
            "param_global": r.get('ParameterGlobalName', ''),
            "param_code": r.get('ParameterName', ''),
            "std_val": format_val_num(param_base),
            "offset_from": format_val_num(offset_from),
            "offset_to": format_val_num(offset_to),
            "from_val": format_val_num(calc_from_val),
            "to_val": format_val_num(calc_to_val),
            "unit": r.get('ParameterUnitSymbol', ''),
            "comments": r.get('comments', ''),
            "user_name": r.get('UserName', ''),
            "process_type": r.get('ProcessTypeName', ''),
            "priority": r.get('Priority')
        }

        if matched_cluster:
            # 同一事件会话中若对同一个参数进行多次修改调整：
            # 由于 cgrs_rows 按时间倒序（最新在前），已存在的 record 保留了最新的 target To 值，
            # 遇到更早的记录时，更新其初始 From 值为最早的 TechOffsetHistoryValueFrom
            existing_param = None
            for p in matched_cluster["params_changed"]:
                if p["param_code"] == param_item["param_code"] and p["param_local"] == param_item["param_local"]:
                    existing_param = p
                    break
            if existing_param:
                existing_param["offset_from"] = param_item["offset_from"]
                existing_param["from_val"] = param_item["from_val"]
            else:
                matched_cluster["params_changed"].append(param_item)

            if ts > matched_cluster["timestamp"]:
                matched_cluster["timestamp"] = ts
                matched_cluster["date_time_str"] = str(r.get('TechOffsetHistoryLocalDate') or r.get('TechOffsetLocalDate') or ts)
        else:
            clustered_events.append({
                "timestamp": ts,
                "date_time_str": str(r.get('TechOffsetHistoryLocalDate') or r.get('TechOffsetLocalDate') or ts),
                "params_changed": [param_item]
            })

    # 查询该机台在历史库中所有调参时间线（用于边界约束：不超过上/下一次修改时间）
    all_ts_sql = f"""
        SELECT DISTINCT event_timestamp
        FROM cgrs_records
        WHERE Workcenter IN ({cgrs_placeholders})
          AND event_timestamp IS NOT NULL
    """
    all_ts_params = list(cgrs_candidates)
    if not is_cu and article and article.strip():
        art_clean = article.strip()
        prefix7 = art_clean[:7]
        all_ts_sql += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ? OR RecipeDescription LIKE ?)"
        all_ts_params.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%", f"%{prefix7}%"])
    all_ts_sql += " ORDER BY event_timestamp ASC"

    try:
        all_ts_rows = qry(all_ts_sql, all_ts_params)
        raw_all_timestamps = [r['event_timestamp'] for r in all_ts_rows if r.get('event_timestamp')]
        # 对历史时间线同样进行 300 秒（5 分钟）聚合，确保边界判定与事件会话 100% 对齐
        clustered_all_ts = []
        for t in sorted(raw_all_timestamps):
            if not clustered_all_ts or abs((t - clustered_all_ts[-1]).total_seconds()) > 300:
                clustered_all_ts.append(t)
        all_timestamps = clustered_all_ts
    except Exception:
        all_timestamps = []

    # 确定指标字段与公差限
    if indicator == "weight":
        ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        usl, lsl = None, None
    elif indicator == "cony":
        ind_col = "TRY_CAST(cony_first AS DOUBLE)"
        usl, lsl = get_spec_limits(article, indicator) if article else (100.0, None)
    else:
        col_field = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        ind_col = f"TRY_CAST({col_field} AS DOUBLE)"
        usl, lsl = get_spec_limits(article, indicator) if article else (100.0, None)

    mach_placeholders = ",".join(["?"] * len(mach_candidates))
    time_expr = f"TRY_CAST({time_col} AS TIMESTAMP)"

    # 按时间升序排序单次调参会话
    sorted_raw_events = sorted(clustered_events, key=lambda x: x["timestamp"])

    # 按【相邻两次调参之间成型样本 < 10 胎】条件进行分组合并
    merged_groups = []
    curr_group = []

    for ev in sorted_raw_events:
        if not curr_group:
            curr_group.append(ev)
        else:
            prev_ev = curr_group[-1]
            t_start = prev_ev["timestamp"]
            t_end = ev["timestamp"]

            # 统计在 [t_start, t_end) 之间的成型生产样本数
            cnt_where = [
                f"{wc_col} IN ({mach_placeholders})",
                f"{time_expr} >= ?::TIMESTAMP",
                f"{time_expr} < ?::TIMESTAMP"
            ]
            cnt_params = list(mach_candidates) + [str(t_start), str(t_end)]
            if not is_cu and article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                cnt_where.append("(article10 = ? OR article10 LIKE ?)")
                cnt_params.extend([art_clean, f"{prefix7}%"])

            try:
                cnt_sql = f"SELECT COUNT(*) as cnt FROM clean_yield WHERE {' AND '.join(cnt_where)}"
                cnt_res = qry(cnt_sql, cnt_params)
                mid_samples_count = cnt_res[0]['cnt'] if cnt_res else 0
            except Exception:
                mid_samples_count = 0

            if mid_samples_count < 15:
                # 间隔内样本少于 15 胎，判定为连续微调，合并入同一组
                curr_group.append(ev)
            else:
                # 间隔 >= 15 胎，保持为独立事件
                merged_groups.append(curr_group)
                curr_group = [ev]

    if curr_group:
        merged_groups.append(curr_group)

    events_result = []
    tot_groups = len(merged_groups)

    # 按时间倒序遍历事件分组（最新在上）
    for g_idx, g in enumerate(reversed(merged_groups)):
        start_ts = g[0]["timestamp"]
        end_ts = g[-1]["timestamp"]
        is_continuous = len(g) > 1

        # 合并组内参数变更明细：同参数取最早 From ➔ 最新 To
        group_params_map = {}
        for ev_item in g:
            for p in ev_item["params_changed"]:
                key = (p["param_code"], p["param_local"])
                if key not in group_params_map:
                    group_params_map[key] = dict(p)
                else:
                    group_params_map[key]["offset_to"] = p["offset_to"]
                    group_params_map[key]["to_val"] = p["to_val"]
                    if p.get("comments") and p["comments"] not in (group_params_map[key].get("comments") or ""):
                        group_params_map[key]["comments"] = f"{group_params_map[key].get('comments', '')} | {p['comments']}".strip(' |')

        group_params_list = list(group_params_map.values())

        # 界定边界 t_prev 与 t_next
        orig_idx = tot_groups - 1 - g_idx
        t_prev = merged_groups[orig_idx - 1][-1]["timestamp"] if orig_idx > 0 else None
        t_next = merged_groups[orig_idx + 1][0]["timestamp"] if orig_idx < tot_groups - 1 else None

        # 查找流经该机台的所有对照组组合路径
        if is_cu:
            combo_where = [
                f"ct_workcenter IN ({mach_placeholders})",
                "gt_workcenter IS NOT NULL",
                "gt_workcenter != ''",
                "tu_first_workcenter IS NOT NULL",
                "tu_first_workcenter != ''"
            ]
            combo_params = list(mach_candidates)

            if article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                combo_where.append("(article10 = ? OR article10 LIKE ?)")
                combo_params.extend([art_clean, f"{prefix7}%"])

            if t_prev:
                combo_where.append(f"{time_expr} >= ?::TIMESTAMP")
                combo_params.append(t_prev)
            if t_next:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP")
                combo_params.append(t_next)

            combo_sql = f"""
                SELECT DISTINCT 
                    CAST(gt_workcenter AS VARCHAR) as code1,
                    CAST(tu_first_workcenter AS VARCHAR) as code2
                FROM clean_yield
                WHERE {" AND ".join(combo_where)}
                ORDER BY 1, 2
            """
        else:
            combo_where = [
                f"gt_workcenter IN ({mach_placeholders})",
                "ct_workcenter IS NOT NULL",
                "ct_workcenter != ''",
                "tu_first_workcenter IS NOT NULL",
                "tu_first_workcenter != ''"
            ]
            combo_params = list(mach_candidates)

            if article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                combo_where.append("(article10 = ? OR article10 LIKE ?)")
                combo_params.extend([art_clean, f"{prefix7}%"])

            if t_prev:
                combo_where.append(f"{time_expr} >= ?::TIMESTAMP")
                combo_params.append(t_prev)
            if t_next:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP")
                combo_params.append(t_next)

            combo_sql = f"""
                SELECT DISTINCT 
                    CAST(ct_workcenter AS VARCHAR) as code1,
                    CAST(tu_first_workcenter AS VARCHAR) as code2
                FROM clean_yield
                WHERE {" AND ".join(combo_where)}
                ORDER BY 1, 2
            """

        try:
            combos = qry(combo_sql, combo_params)
        except Exception:
            combos = []

        all_path_before_vals = []
        all_path_after_vals = []
        event_paths = []

        for c in combos:
            code1 = c['code1']
            code2 = c['code2']

            if is_cu:
                path_base_where = f"ct_workcenter IN ({mach_placeholders}) AND gt_workcenter = ? AND tu_first_workcenter = ? AND {ind_col} IS NOT NULL"
                gt_code = code1
                ct_code = wc_clean
                tu_code = code2
            else:
                path_base_where = f"gt_workcenter IN ({mach_placeholders}) AND ct_workcenter = ? AND tu_first_workcenter = ? AND {ind_col} IS NOT NULL"
                gt_code = wc_clean
                ct_code = code1
                tu_code = code2

            path_base_params = list(mach_candidates) + [code1, code2]
            if article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                path_base_where += " AND (article10 = ? OR article10 LIKE ?)"
                path_base_params.extend([art_clean, f"{prefix7}%"])
            
            if same_day_only:
                path_base_where += " AND TRY_CAST(tu_first_loc_timestamp AS DATE) = ?::DATE"
                path_base_params.append(date)

            # 1. 调参前样本 (Before)：向前最多 limit_per_path 条，只取 start_ts 之前的样本
            BEFORE_FETCH_LIMIT = limit_per_path
            before_conds = [
                f"{time_expr} < ?::TIMESTAMP",
                f"{time_expr} IS NOT NULL",
                f"{time_expr} >= ?::TIMESTAMP - INTERVAL 1 DAY"
            ]
            before_params = list(path_base_params) + [start_ts, start_ts]
            if t_prev:
                before_conds.append(f"{time_expr} >= ?::TIMESTAMP")
                before_params.append(t_prev)

            sql_before = f"""
                SELECT
                    COALESCE(CAST(barcode AS VARCHAR), '') as barcode,
                    {ind_col} as val,
                    {time_expr} as prod_time
                FROM clean_yield
                WHERE {path_base_where}
                  AND {" AND ".join(before_conds)}
                ORDER BY {time_expr} DESC
                LIMIT {BEFORE_FETCH_LIMIT}
            """
            rows_before = qry(sql_before, before_params)

            # 2. 过渡段样本 (Transition)：在 [start_ts, end_ts) 之间的样本 (少于 10 胎)
            samples_transition = []
            if is_continuous and start_ts != end_ts:
                trans_conds = [
                    f"{time_expr} >= ?::TIMESTAMP",
                    f"{time_expr} < ?::TIMESTAMP",
                    f"{time_expr} IS NOT NULL"
                ]
                trans_params = list(path_base_params) + [start_ts, end_ts]
                sql_trans = f"""
                    SELECT
                        COALESCE(CAST(barcode AS VARCHAR), '') as barcode,
                        {ind_col} as val,
                        {time_expr} as prod_time
                    FROM clean_yield
                    WHERE {path_base_where} AND {" AND ".join(trans_conds)}
                    ORDER BY {time_expr} ASC
                """
                rows_trans = qry(sql_trans, trans_params)
                samples_transition = [
                    {
                        "barcode": str(r.get('barcode') or f"T{idx+1}"),
                        "val": round(float(r['val']), 3),
                        "time": str(r.get('prod_time') or ''),
                        "gt": gt_code,
                        "ct": ct_code,
                        "tu": tu_code,
                        "stage": "transition"
                    }
                    for idx, r in enumerate(rows_trans) if r.get('val') is not None
                ]

            # 3. 调参后样本 (After)：向后最多 30 条，只取 end_ts 之后的样本
            after_conds = [
                f"{time_expr} >= ?::TIMESTAMP",
                f"{time_expr} IS NOT NULL",
                f"{time_expr} < ?::TIMESTAMP + INTERVAL 1 DAY"
            ]
            after_params = list(path_base_params) + [end_ts, end_ts]
            if t_next:
                after_conds.append(f"{time_expr} < ?::TIMESTAMP")
                after_params.append(t_next)

            sql_after = f"""
                SELECT
                    COALESCE(CAST(barcode AS VARCHAR), '') as barcode,
                    {ind_col} as val,
                    {time_expr} as prod_time
                FROM clean_yield
                WHERE {path_base_where}
                  AND {" AND ".join(after_conds)}
                ORDER BY {time_expr} ASC
                LIMIT {limit_per_path}
            """
            rows_after = qry(sql_after, after_params)

            rows_before_asc = list(reversed(rows_before))
            samples_before = [
                {
                    "barcode": str(r.get('barcode') or f"B{idx+1}"),
                    "val": round(float(r['val']), 3),
                    "time": str(r.get('prod_time') or ''),
                    "gt": gt_code,
                    "ct": ct_code,
                    "tu": tu_code,
                    "stage": "before"
                }
                for idx, r in enumerate(rows_before_asc) if r.get('val') is not None
            ]
            samples_after = [
                {
                    "barcode": str(r.get('barcode') or f"A{idx+1}"),
                    "val": round(float(r['val']), 3),
                    "time": str(r.get('prod_time') or ''),
                    "gt": gt_code,
                    "ct": ct_code,
                    "tu": tu_code,
                    "stage": "after"
                }
                for idx, r in enumerate(rows_after) if r.get('val') is not None
            ]

            vals_before = [s['val'] for s in samples_before]
            vals_after = [s['val'] for s in samples_after]

            n_before = len(vals_before)
            n_after = len(vals_after)

            if n_before == 0 and n_after == 0 and len(samples_transition) == 0:
                continue

            all_path_before_vals.extend(vals_before)
            all_path_after_vals.extend(vals_after)

            mean_before = float(np.mean(vals_before)) if n_before > 0 else 0.0
            std_before = float(np.std(vals_before, ddof=1)) if n_before > 1 else (float(np.std(vals_before)) if n_before == 1 else 0.0)

            mean_after = float(np.mean(vals_after)) if n_after > 0 else 0.0
            std_after = float(np.std(vals_after, ddof=1)) if n_after > 1 else (float(np.std(vals_after)) if n_after == 1 else 0.0)

            mean_diff = (mean_after - mean_before) if (n_before > 0 and n_after > 0) else 0.0

            if indicator == "weight":
                cpk_before = mean_before if n_before > 0 else 0.0
                cpk_after = mean_after if n_after > 0 else 0.0
                cpk_diff = (cpk_after - cpk_before) if (n_before > 0 and n_after > 0) else 0.0
                if n_before > 0 and n_after > 0 and abs(mean_before) > 1e-4:
                    yoy_pct = ((abs(mean_before) - abs(mean_after)) / abs(mean_before) * 100.0)
                else:
                    yoy_pct = 0.0
            else:
                cpk_before = calc_cpk(mean_before, std_before, usl, lsl) if n_before > 0 else 0.0
                cpk_after = calc_cpk(mean_after, std_after, usl, lsl) if n_after > 0 else 0.0
                cpk_diff = (cpk_after - cpk_before) if (n_before > 0 and n_after > 0) else 0.0
                if n_before > 0 and n_after > 0 and abs(cpk_before) > 1e-4:
                    yoy_pct = ((cpk_after - cpk_before) / abs(cpk_before) * 100.0)
                else:
                    yoy_pct = 0.0

            path_suspects = [m for m in [ct_code, tu_code] if m in suspect_list]

            event_paths.append({
                "path_label": f"{workcenter} ➔ {ct_code} ➔ {tu_code}",
                "gt_workcenter": workcenter,
                "ct_workcenter": ct_code,
                "tu_workcenter": tu_code,
                "suspect_machines": path_suspects,
                "is_suspect_path": (len(path_suspects) > 0),
                "n_before": n_before,
                "n_after": n_after,
                "n_transition": len(samples_transition),
                "has_before_data": (n_before > 0),
                "has_after_data": (n_after > 0),
                "mean_before": round(mean_before, 3),
                "mean_after": round(mean_after, 3),
                "std_before": round(std_before, 3),
                "std_after": round(std_after, 3),
                "mean_diff": round(mean_diff, 3),
                "cpk_before": round(cpk_before, 3),
                "cpk_after": round(cpk_after, 3),
                "cpk_diff": round(cpk_diff, 3),
                "yoy_pct": round(yoy_pct, 2),
                "vals_before": vals_before,
                "vals_after": vals_after,
                "samples_before": samples_before,
                "samples_transition": samples_transition,
                "samples_after": samples_after
            })

        effective_paths = []
        for p in event_paths:
            nb = p.get("n_before", 0)
            na = p.get("n_after", 0)
            if nb >= 5 and na >= 5:
                ratio = max(nb, na) / min(nb, na)
                if ratio <= 2.5:
                    effective_paths.append(p)

        if effective_paths:
            eff_before_vals = []
            eff_after_vals = []
            for p in effective_paths:
                eff_before_vals.extend(p.get("vals_before", []))
                eff_after_vals.extend(p.get("vals_after", []))
        else:
            # 样本不足未能筛选出有效路径时：退避兜底，使用该机台在该规格下调参前后 50 条样本进行判定
            eff_before_vals = []
            eff_after_vals = []
            try:
                # 调参前最多 50 条
                fb_before_where = [
                    f"{wc_col} IN ({mach_placeholders})",
                    f"{ind_col} IS NOT NULL",
                    f"{time_expr} < ?::TIMESTAMP",
                    f"{time_expr} >= ?::TIMESTAMP - INTERVAL 2 DAY"
                ]
                fb_params_b = list(mach_candidates) + [start_ts, start_ts]
                if article and article.strip():
                    art_clean = article.strip()
                    prefix7 = art_clean[:7]
                    fb_before_where.append("(article10 = ? OR article10 LIKE ?)")
                    fb_params_b.extend([art_clean, f"{prefix7}%"])
                if t_prev:
                    fb_before_where.append(f"{time_expr} >= ?::TIMESTAMP")
                    fb_params_b.append(t_prev)
                
                sql_fb_b = f"""
                    SELECT {ind_col} as val
                    FROM clean_yield
                    WHERE {" AND ".join(fb_before_where)}
                    ORDER BY {time_expr} DESC
                    LIMIT 50
                """
                rows_fb_b = qry(sql_fb_b, fb_params_b)
                eff_before_vals = [float(r['val']) for r in rows_fb_b if r.get('val') is not None]

                # 调参后最多 50 条
                fb_after_where = [
                    f"{wc_col} IN ({mach_placeholders})",
                    f"{ind_col} IS NOT NULL",
                    f"{time_expr} >= ?::TIMESTAMP",
                    f"{time_expr} < ?::TIMESTAMP + INTERVAL 2 DAY"
                ]
                fb_params_a = list(mach_candidates) + [end_ts, end_ts]
                if article and article.strip():
                    art_clean = article.strip()
                    prefix7 = art_clean[:7]
                    fb_after_where.append("(article10 = ? OR article10 LIKE ?)")
                    fb_params_a.extend([art_clean, f"{prefix7}%"])
                if t_next:
                    fb_after_where.append(f"{time_expr} < ?::TIMESTAMP")
                    fb_params_a.append(t_next)

                sql_fb_a = f"""
                    SELECT {ind_col} as val
                    FROM clean_yield
                    WHERE {" AND ".join(fb_after_where)}
                    ORDER BY {time_expr} ASC
                    LIMIT 50
                """
                rows_fb_a = qry(sql_fb_a, fb_params_a)
                eff_after_vals = [float(r['val']) for r in rows_fb_a if r.get('val') is not None]
            except Exception as e:
                eff_before_vals = []
                eff_after_vals = []

        tot_nb = len(eff_before_vals)
        tot_na = len(eff_after_vals)
        tot_mb = float(np.mean(eff_before_vals)) if tot_nb > 0 else 0.0
        tot_sb = float(np.std(eff_before_vals, ddof=1)) if tot_nb > 1 else 0.0
        tot_ma = float(np.mean(eff_after_vals)) if tot_na > 0 else 0.0
        tot_sa = float(np.std(eff_after_vals, ddof=1)) if tot_na > 1 else 0.0

        if indicator == "weight":
            tot_cpk_b = tot_mb if tot_nb > 0 else 0.0
            tot_cpk_a = tot_ma if tot_na > 0 else 0.0
            tot_cpk_diff = (tot_cpk_a - tot_cpk_b) if (tot_nb > 0 and tot_na > 0) else 0.0
            tot_yoy = ((abs(tot_mb) - abs(tot_ma)) / abs(tot_mb) * 100.0) if (tot_nb > 0 and tot_na > 0 and abs(tot_mb) > 1e-4) else 0.0
        else:
            tot_cpk_b = calc_cpk(tot_mb, tot_sb, usl, lsl) if tot_nb > 0 else 0.0
            tot_cpk_a = calc_cpk(tot_ma, tot_sa, usl, lsl) if tot_na > 0 else 0.0
            tot_cpk_diff = (tot_cpk_a - tot_cpk_b) if (tot_nb > 0 and tot_na > 0) else 0.0
            tot_yoy = ((tot_cpk_a - tot_cpk_b) / abs(tot_cpk_b) * 100.0) if (tot_nb > 0 and tot_na > 0 and abs(tot_cpk_b) > 1e-4) else 0.0

        overall_summary = {
            "n_before": tot_nb,
            "n_after": tot_na,
            "mean_before": round(tot_mb, 3),
            "mean_after": round(tot_ma, 3),
            "std_before": round(tot_sb, 3),
            "std_after": round(tot_sa, 3),
            "mean_diff": round(tot_ma - tot_mb, 3) if (tot_nb > 0 and tot_na > 0) else 0.0,
            "cpk_before": round(tot_cpk_b, 3),
            "cpk_after": round(tot_cpk_a, 3),
            "cpk_diff": round(tot_cpk_diff, 3),
            "yoy_pct": round(tot_yoy, 2)
        }

        interfering_machines = set()
        for p in effective_paths:
            if p["has_before_data"] and p["has_after_data"] and p["suspect_machines"]:
                if tot_yoy > 0 and p["yoy_pct"] < 0:
                    interfering_machines.update(p["suspect_machines"])
                elif tot_yoy < 0 and p["yoy_pct"] < (tot_yoy - 15.0):
                    interfering_machines.update(p["suspect_machines"])

        if not effective_paths:
            ev_conclusion_type = "insufficient_data"
            ev_conclusion_title = "数据量不足"
            ev_conclusion_text = f"成型机 [{workcenter}] 在调参时间窗口内拆分路径的有效生产样本较少 (需双侧 ≥5 胎且样本比例 ≤2.5 倍)，暂无法得出明确方向性结论。"
        elif interfering_machines:
            ev_conclusion_type = "second_stage_interference"
            m_str = "、".join(sorted(list(interfering_machines)))
            sign_str = f"+{tot_yoy:.2f}%" if tot_yoy >= 0 else f"{tot_yoy:.2f}%"
            if tot_yoy >= 0:
                ev_conclusion_title = "算法判定：成型调参总体改善，部分路径受后工段预警机台负向干扰"
                ev_conclusion_text = (
                    f"成型机 [{workcenter}] 调参后全工序加总总体 CPK 呈改善提升趋势（总体增幅 {sign_str}）。"
                    f"但在流经全局预警机台 [{m_str}] 的组合路径中，CPK 表现为反向下滑，判定该路径主要受后工段高风险机台负向干扰，而非成型机本身调参失效。"
                )
            else:
                ev_conclusion_title = "算法判定：成型调参受后工段预警机台加剧恶化干扰"
                ev_conclusion_text = (
                    f"成型机 [{workcenter}] 调参后全工序加总总体 CPK 呈下滑变动（总体增幅 {sign_str}）。"
                    f"且在流经全局预警机台 [{m_str}] 的组合路径中质量恶化尤为突出，判定该工序质量问题显著受后工段高风险机台叠加干扰。"
                )
        elif tot_yoy > 2.0:
            ev_conclusion_type = "confirmed_gt_effect"
            ev_conclusion_title = "算法判定：排除后工段干扰，成型调参改善效果真实明确"
            ev_conclusion_text = f"全工序各拆分路径调参前后 CPK 增幅方向总体一致（全路径总体增幅 +{tot_yoy:.2f}%），排除硫化与终检后工段机台差异干扰，成型机 [{workcenter}] 调参改善效果真实有效。"
        elif tot_yoy < -2.0:
            ev_conclusion_type = "confirmed_gt_effect"
            ev_conclusion_title = "算法判定：排除后工段干扰，成型调参对全路径呈负向影响"
            ev_conclusion_text = f"全工序各拆分路径调参后 CPK 均表现为下滑（全路径总体增幅 {tot_yoy:.2f}%），排除后工段机台干扰，表明本次参数调整对各路径均未达到预期质量效果。"
        else:
            ev_conclusion_type = "confirmed_gt_effect"
            ev_conclusion_title = "算法判定：调参前后质量表现基本持平"
            ev_conclusion_text = f"成型机 [{workcenter}] 调参后总体 CPK 保持平稳（全路径总体增幅 {tot_yoy:.2f}%），各路径未见显著分歧。"

        all_event_samples_before = []
        all_event_samples_transition = []
        all_event_samples_after = []
        for p in effective_paths:
            all_event_samples_before.extend(p.get("samples_before", []))
            all_event_samples_transition.extend(p.get("samples_transition", []))
            all_event_samples_after.extend(p.get("samples_after", []))

        all_event_samples_before = sorted(all_event_samples_before, key=lambda x: x['time'])
        all_event_samples_transition = sorted(all_event_samples_transition, key=lambda x: x['time'])
        all_event_samples_after = sorted(all_event_samples_after, key=lambda x: x['time'])

        first_ev_time_str = g[0].get("date_time_str") or str(start_ts)
        last_ev_time_str = g[-1].get("date_time_str") or str(end_ts)
        time_str_display = first_ev_time_str if not is_continuous else f"{first_ev_time_str} ~ {last_ev_time_str.split(' ')[-1]}"

        events_result.append({
            "timestamp": str(end_ts),
            "start_timestamp": str(start_ts),
            "end_timestamp": str(end_ts),
            "is_continuous_adjust": is_continuous,
            "date_time_str": time_str_display,
            "params_changed": group_params_list,
            "usl": usl,
            "lsl": lsl,
            "paths": event_paths,
            "effective_paths": effective_paths,
            "overall_summary": overall_summary,
            "overall_samples_before": all_event_samples_before,
            "overall_samples_transition": all_event_samples_transition,
            "overall_samples_after": all_event_samples_after,
            "interfering_machines": sorted(list(interfering_machines)),
            "conclusion_type": ev_conclusion_type,
            "conclusion_title": ev_conclusion_title,
            "conclusion_text": ev_conclusion_text
        })

    latest_event = events_result[0] if events_result else {}

    return {
        "status": "success",
        "has_cgrs": True,
        "events_count": len(events_result),
        "conclusion_type": latest_event.get("conclusion_type", "confirmed_gt_effect"),
        "conclusion_title": latest_event.get("conclusion_title", "控制变量排查结论"),
        "conclusion_text": latest_event.get("conclusion_text", ""),
        "interfering_machines": latest_event.get("interfering_machines", []),
        "top_machines": suspect_list,
        "overall_summary": latest_event.get("overall_summary", {}),
        "events": sanitize_data(events_result),
        "meta": {
            "workcenter": workcenter,
            "date": date,
            "article": article,
            "indicator": indicator,
            "top_machines": suspect_list
        }
    }


def calculate_cgrs_cpk_comparison(
    workcenter: str,
    article10: Optional[str] = None,
    target_date: Optional[str] = None,
    indicator: str = "rfpp",
    limit_n: int = 20
):
    """
    针对成型机台计算 CGRS 参数修改前后的全工序多路径有效加总 CPK 及增幅。
    直接复用 compute_cgrs_controlled_analysis_data 计算引擎，保证全局数值 100% 严格一致。
    """
    if not workcenter or not target_date:
        return {"has_cgrs": False, "events_count": 0, "events": []}
    
    try:
        res = compute_cgrs_controlled_analysis_data(
            workcenter=workcenter,
            date=target_date,
            article=article10,
            indicator=indicator,
            same_day_only=False,
            limit_per_path=limit_n
        )
        if not res.get("has_cgrs") or not res.get("events"):
            return {"has_cgrs": False, "events_count": 0, "events": []}

        tot_events = len(res["events"])
        events_summary = []
        for idx, ev in enumerate(res["events"]):
            ev_num = tot_events - idx
            ev_ov = ev.get("overall_summary", {})
            params_changed = ev.get("params_changed", [])
            param_names = [p.get("param_local") or p.get("param_code") or "参数" for p in params_changed]
            param_str = ", ".join(param_names[:3]) + ("..." if len(param_names) > 3 else "") if param_names else "参数调整"
            eff_paths = ev.get("effective_paths", [])

            events_summary.append({
                "event_num": ev_num,
                "time_str": ev.get("date_time_str"),
                "params": param_str,
                "cpk_before": ev_ov.get("cpk_before", 0.0),
                "cpk_after": ev_ov.get("cpk_after", 0.0),
                "cpk_diff": ev_ov.get("cpk_diff", 0.0),
                "yoy_pct": ev_ov.get("yoy_pct", 0.0),
                "n_before": ev_ov.get("n_before", 0),
                "n_after": ev_ov.get("n_after", 0),
                "valid_paths_count": len(eff_paths),
                "is_disabled": len(eff_paths) == 0
            })

        latest = res["events"][0]
        ov = latest.get("overall_summary", {})
        paths = latest.get("paths", [])
        eff_paths = latest.get("effective_paths", [])
        
        return {
            "has_cgrs": True,
            "events_count": tot_events,
            "events_summary": events_summary,
            "latest_event_time": latest.get("date_time_str"),
            "latest_yoy_pct": ov.get("yoy_pct", 0.0),
            "latest_cpk_before": ov.get("cpk_before", 0.0),
            "latest_cpk_after": ov.get("cpk_after", 0.0),
            "latest_cpk_diff": ov.get("cpk_diff", 0.0),
            "latest_mean_before": ov.get("mean_before", 0.0),
            "latest_mean_after": ov.get("mean_after", 0.0),
            "latest_std_before": ov.get("std_before", 0.0),
            "latest_std_after": ov.get("std_after", 0.0),
            "latest_n_before": ov.get("n_before", 0),
            "latest_n_after": ov.get("n_after", 0),
            "latest_valid_paths_count": len(eff_paths),
            "latest_total_paths_count": len(paths),
            "latest_has_before_data": (ov.get("n_before", 0) > 0),
            "latest_has_after_data": (ov.get("n_after", 0) > 0),
            "latest_params": [p.get("param_local") for p in latest.get("params_changed", [])],
            "events": res["events"]
        }
    except Exception:
        return {"has_cgrs": False, "events_count": 0, "events": []}


ALLOWED_WORKCENTER_COLS = {
    "gt_workcenter": "生胎成型GT",
    "ct_workcenter": "硫化CT",
    "tu_first_workcenter": "终检TU",
    "tread_workcenter": "胎面",
    "bead_workcenter": "胎圈",
    "inner_liner_workcenter": "内衬",
    "sidewall_workcenter": "胎侧",
    "first_breaker_workcenter": "带束层1",
    "second_breaker_workcenter": "带束层2",
    "first_ply_workcenter": "帘布层1",
    "second_ply_workcenter": "帘布层2",
    "wound_cap_ply1_workcenter": "冠带层1",
    "wound_cap_ply2_workcenter": "冠带层2",
    "tb_first_workcenter": "动平衡TB"
}

@app.get("/api/cgrs/controlled-analysis")
def get_cgrs_controlled_analysis(
    workcenter: str = Query(..., description="成型机台编号，如 TB122 或 TB243"),
    date: str = Query(..., description="查询日期，格式 YYYY-MM-DD"),
    article: Optional[str] = Query(None, description="规格代码 article10 (可选)"),
    indicator: Optional[str] = Query("rfpp", description="指标类型，如 rfpp, rfh1, cony, weight"),
    top_machines: Optional[str] = Query(None, description="前端传入的全局影响度<0的Top 3嫌疑机台列表，逗号分隔，如 TU6,CU718,TU3"),
    same_day_only: bool = Query(False, description="是否仅看调参当天样本，False为允许跨天取样"),
    min_samples: int = Query(1, description="每条路径改前/改后最低样本门槛，低于此值的路径将被过滤，默认 1")
):
    try:
        return compute_cgrs_controlled_analysis_data(
            workcenter=workcenter,
            date=date,
            article=article,
            indicator=indicator,
            top_machines=top_machines,
            same_day_only=same_day_only,
            limit_per_path=20,
            min_samples_threshold=1
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"执行 CGRS 控制变量分析失败: {str(e)}",
            "has_cgrs": False,
            "conclusion_type": "error",
            "conclusion_title": "分析出错",
            "conclusion_text": f"分析出错: {str(e)}",
            "events": []
        }


def get_phase_sql_condition(phase: Optional[str]) -> str:
    """
    根据 phase 参数生成 DuckDB SQL 过滤条件
    - 'p3': ct_shop 为空或不含 'P4' / 'p4' (三期)
    - 'p4': ct_shop 包含 'P4' / 'p4' (四期)
    - 'all' 或 None: 不限制期别
    """
    if not phase or phase == "all":
        return ""
    if phase == "p3":
        return " AND (ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%')"
    if phase == "p4":
        return " AND (ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%')"
    return ""


# ── 健康检测与 ETL 重载 ──────────────────────────────────────────
@app.get("/")
def root():
    index_file = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "message": "轮胎质量分析看板 API 运行中"}


@app.post("/api/etl/reload")
@app.get("/api/etl/reload")
def reload_etl_data():
    """在线重载最新的 Cleaned Parquet 数据到 DuckDB 内存表"""
    try:
        success = reload_duckdb_data()
        if not success:
            return {"status": "error", "message": f"未找到数据文件: {DATA_PATH}"}
        
        row_res = qry("SELECT COUNT(*) as n FROM clean_yield")
        row_count = row_res[0]['n'] if row_res else 0
        return {
            "status": "success", 
            "message": "DuckDB 内存数据刷新成功", 
            "data_path": DATA_PATH,
            "row_count": row_count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/etl/status")
def get_etl_status():
    """查看数据源状态与最后修改时间"""
    try:
        current_path = get_cleaned_data_path()
        file_exists = os.path.exists(current_path)
        mtime_str = None
        size_bytes = 0
        if file_exists:
            mtime = os.path.getmtime(current_path)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_bytes = os.path.getsize(current_path)
            
        row_count = CACHED_ROW_COUNT if file_exists else 0
        
        return {
            "status": "success",
            "data": {
                "data_path": DATA_PATH,
                "exists": file_exists,
                "last_modified": mtime_str,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "loaded_rows": row_count
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 4.4. 全量规格型号列表 (支持全量规格选择) ─────────────────
@app.get("/api/articles/all")
def get_all_articles():
    try:
        rows = qry("SELECT DISTINCT article10 FROM clean_yield WHERE article10 IS NOT NULL AND article10 != '' ORDER BY 1")
        articles_list = [r['article10'] for r in rows]
        return {"status": "success", "data": sanitize_data(articles_list)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 4.5. 预警规格型号排行 (全局 CPK 统计) ──────────────────────
@app.get("/api/articles/warning-cpk")
def get_articles_warning_cpk(
    indicator: str = Query("rfpp"),       # "rfpp" | "rfh1" | "cony" | "weight"
    study_from: Optional[str] = Query(None),  # 仅作为分析目标日期使用
    study_to: Optional[str] = Query(None),
    only_declining: bool = Query(False),
    min_samples: int = Query(30),
    phase: Optional[str] = Query("all"),
    article10: Optional[str] = Query(None),
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    max_cpk: Optional[float] = Query(0.9),  # CPK 门槛上限过滤，默认只展示 CPK < max_cpk 的恶化规格
    shift: Optional[str] = Query("all")
):
    try:
        if hasattr(min_samples, "default"): min_samples = min_samples.default
        if hasattr(indicator, "default"): indicator = indicator.default
        if hasattr(study_from, "default"): study_from = study_from.default
        if hasattr(study_to, "default"): study_to = study_to.default
        if hasattr(phase, "default"): phase = phase.default
        if hasattr(time_col, "default"): time_col = time_col.default
        if hasattr(max_cpk, "default"): max_cpk = max_cpk.default
        if hasattr(shift, "default"): shift = shift.default

        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 30
        parsed_max_cpk = None
        if max_cpk is not None:
            try:
                val = float(max_cpk)
                if val > 0 and val < 99:
                    parsed_max_cpk = val
            except (ValueError, TypeError):
                parsed_max_cpk = 0.9
        else:
            parsed_max_cpk = 0.9

        # 确定分析目标日期（取 study_to，单日点击时 study_from == study_to）
        target_date = study_to or study_from
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"

        # 探测数据库中的最新有效生产日 (08:00~次日08:00)
        date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"
        max_db_res = qry(f"SELECT MAX({date_col}) AS max_d FROM clean_yield")
        max_db_date = str(max_db_res[0]['max_d']) if (max_db_res and max_db_res[0].get('max_d')) else None

        if not target_date:
            valid_d_res = qry(f"""
                SELECT {date_col} AS d
                FROM clean_yield
                WHERE {date_col} IS NOT NULL
                GROUP BY 1, article10
                HAVING COUNT(*) >= ?
                ORDER BY 1 DESC
                LIMIT 1
            """, [min_samples])
            if valid_d_res and valid_d_res[0].get('d'):
                target_date = str(valid_d_res[0]['d'])
            else:
                target_date = max_db_date

        # 判断当前查看的日期是否为数据库中的最新一天
        is_latest_date = bool(target_date and max_db_date and str(target_date) == str(max_db_date))

        if not isinstance(phase, str):
            phase = "all"
        if not isinstance(article10, str):
            article10 = None

        phase_cond = get_phase_sql_condition(phase)
        article_cond = " AND article10 = ?" if article10 else ""
        shift_cond = f" AND {build_production_time_where(time_col=time_col, shift=shift)}" if (shift and shift != 'all') else ""

        if indicator == "weight":
            # 胎重指标下的单日偏差贡献度/CPK排行
            sql_overall = f"""
                SELECT
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_actual,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) AS sum_target
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                  {shift_cond}
            """
            overall_rows = qry(sql_overall, [target_date])
            overall_actual = float(overall_rows[0]['sum_actual'] or 0.0) if overall_rows else 0.0
            overall_target = float(overall_rows[0]['sum_target'] or 0.0) if overall_rows else 0.0
            overall_diff = (overall_actual - overall_target) / overall_target * 100.0 if overall_target > 0 else 0.0

            sql_target = f"""
                SELECT
                    article10,
                    COUNT(*) AS sample_size,
                    COUNT(CASE WHEN ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' THEN 1 END) AS p3_count,
                    COUNT(CASE WHEN ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 END) AS p4_count,
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_actual,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) AS sum_target
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                  {article_cond}
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            params = [target_date]
            if article10:
                params.append(article10)
            params.append(min_samples if not article10 else 1)

            rows = qry(sql_target, params)
            if not rows:
                return {"status": "success", "data": []}
                
            total_n = sum(int(r['sample_size']) for r in rows)
            if total_n == 0:
                return {"status": "success", "data": []}
            
            results = []
            for r in rows:
                art = r['article10']
                n = int(r['sample_size'])
                p3_cnt = int(r.get('p3_count') or 0)
                p4_cnt = int(r.get('p4_count') or 0)
                tot_p = p3_cnt + p4_cnt
                if p4_cnt > 0 and p3_cnt == 0:
                    phase_label = "四期"
                elif p3_cnt > 0 and p4_cnt == 0:
                    phase_label = "三期"
                elif tot_p > 0:
                    p3_pct = int(round(p3_cnt / tot_p * 100))
                    p4_pct = int(round(p4_cnt / tot_p * 100))
                    phase_label = f"三期 & 四期 (3期 {p3_pct}% | 4期 {p4_pct}%)"
                else:
                    phase_label = "三期"

                sum_act = float(r['sum_actual'])
                sum_tar = float(r['sum_target'])
                spec_diff = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0
                contrib = (spec_diff - overall_diff) * (n / total_n) if total_n > 0 else 0.0
                
                results.append({
                    "article10": art,
                    "stable_score": round(contrib, 4), # 贡献度
                    "single_cpk": round(spec_diff, 4),   # 规格有符号偏差 %
                    "avg_cpk": round(overall_diff, 4),   # 全厂有符号偏差 %
                    "sample_size": n,
                    "p3_count": p3_cnt,
                    "p4_count": p4_cnt,
                    "phase_label": phase_label,
                })
                
            if is_latest_date:
                # 查看最新一天：在样本门槛过滤下，由最低到最高按照单规格 CPK (偏差率) 升序排列
                results.sort(key=lambda x: x['single_cpk'])
            else:
                # 查看历史记录：按负向贡献度绝对值倒序
                results.sort(key=lambda x: abs(x['stable_score']), reverse=True)

            top_results = results if article10 else results[:10]
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                spec_machine_groups = list(executor.map(
                    lambda it: get_spec_warning_machines_detailed(it, "weight", target_date, min_samples if not article10 else 1),
                    top_results
                ))

            level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
            processed_groups = []
            for g in spec_machine_groups:
                if not g:
                    continue
                # 规格内机台排序：预警颜色等级优先 (🔴 > 🟠 > 🟡) -> 负向贡献度排名优先 (Rank 1 > Rank 2 > Rank 3) -> 跌幅优先
                g.sort(key=lambda m: (
                    level_map.get(m.get("warning_level", "none"), 3),
                    m.get("rank", 99),
                    m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
                ))
                spec_max_level = g[0].get("warning_level", "none")
                stable_score = g[0].get("stable_score", 0)
                processed_groups.append({
                    "spec_max_level": spec_max_level,
                    "stable_score": stable_score,
                    "machines": g
                })

            # 规格两级排序：🔴 > 🟠 > 🟡，同级按负向贡献度绝对值从重到轻
            processed_groups.sort(key=lambda pg: (
                level_map.get(pg["spec_max_level"], 3),
                -abs(pg["stable_score"])
            ))

            final_rows = []
            for pg in processed_groups:
                machs = pg["machines"]
                span_count = len(machs)
                for idx, m in enumerate(machs):
                    m["row_span"] = span_count if idx == 0 else 0
                    final_rows.append(m)

            return {
                "status": "success",
                "is_latest_date": is_latest_date,
                "target_date": target_date,
                "data": sanitize_data(final_rows)
            }

        ind_col = "cony_first" if indicator == "cony" else ("rfppwc_first" if indicator == "rfpp" else "rfh1wc_first")
        
        # 1. 查询当天全厂所有规格数据，用于计算全厂加权系统 CPK 基准
        sql_all = f"""
            SELECT
                article10,
                COUNT(*) AS sample_size,
                COUNT(CASE WHEN ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' THEN 1 END) AS p3_count,
                COUNT(CASE WHEN ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 END) AS p4_count,
                AVG(TRY_CAST({ind_col} AS DOUBLE)) AS avg_v,
                STDDEV(TRY_CAST({ind_col} AS DOUBLE)) AS std_v,
                COALESCE(ANY_VALUE(standard_rfpp),
                         CASE ANY_VALUE("group")
                             WHEN 'GROUP 1'  THEN 10.5
                             WHEN 'GROUP 2A' THEN 11.5
                             WHEN 'GROUP 2B' THEN 12.5
                             WHEN 'GROUP 3'  THEN 12.5
                         END) * 10.0 AS usl_rfpp,
                COALESCE(ANY_VALUE(standard_rfh1),
                         CASE ANY_VALUE("group")
                             WHEN 'GROUP 1'  THEN 7.5
                             WHEN 'GROUP 2A' THEN 8.5
                             WHEN 'GROUP 2B' THEN 9.0
                             WHEN 'GROUP 3'  THEN 9.5
                         END) * 10.0 AS usl_rfh1
            FROM clean_yield
            WHERE {date_col} = ?::DATE
              AND {ind_col} IS NOT NULL
              {phase_cond}
            GROUP BY 1
            HAVING COUNT(*) >= 1
        """
        rows_all = qry(sql_all, [target_date])
        if not rows_all:
            return {"status": "success", "is_latest_date": is_latest_date, "data": []}

        valid_specs = []
        total_n = 0
        weighted_cpk_sum = 0.0

        for r in rows_all:
            art = r['article10']
            n = r['sample_size']
            p3_cnt = int(r.get('p3_count') or 0)
            p4_cnt = int(r.get('p4_count') or 0)
            tot_p = p3_cnt + p4_cnt
            if p4_cnt > 0 and p3_cnt == 0:
                phase_label = "四期"
            elif p3_cnt > 0 and p4_cnt == 0:
                phase_label = "三期"
            elif tot_p > 0:
                p3_pct = int(round(p3_cnt / tot_p * 100))
                p4_pct = int(round(p4_cnt / tot_p * 100))
                phase_label = f"三期 & 四期 (3期 {p3_pct}% | 4期 {p4_pct}%)"
            else:
                phase_label = "三期"

            avg_v = r['avg_v'] or 0.0
            std_v = r['std_v'] or 0.0
            
            if indicator == "cony":
                usl_v, lsl_v = get_spec_limits(art, "cony")
                val = calc_cpk(avg_v, std_v, usl_v, lsl_v)
            else:
                usl_v = r['usl_rfpp'] if indicator == "rfpp" else r['usl_rfh1']
                if std_v > 1e-6 and usl_v is not None:
                    val = calc_cpk(avg_v, std_v, usl_v, None)
                else:
                    val = 1.33
            
            if np.isnan(val) or np.isinf(val):
                continue
                
            valid_specs.append({
                "article10": art,
                "val": val,
                "n": n,
                "p3_count": p3_cnt,
                "p4_count": p4_cnt,
                "phase_label": phase_label
            })
            if n >= 5:
                weighted_cpk_sum += val * n
                total_n += n

        if total_n == 0 and valid_specs:
            total_n = sum(s['n'] for s in valid_specs)
            weighted_cpk_sum = sum(s['val'] * s['n'] for s in valid_specs)

        if total_n == 0:
            return {"status": "success", "is_latest_date": is_latest_date, "data": []}

        avg_cpk = weighted_cpk_sum / total_n

        # 如果指定了具体规格 article10
        if article10:
            target_spec = next((s for s in valid_specs if s['article10'] == article10), None)
            if not target_spec:
                return {"status": "success", "is_latest_date": is_latest_date, "data": []}
            
            neg_contrib = (avg_cpk - target_spec['val']) * target_spec['n']
            single_item = {
                "article10": target_spec['article10'],
                "stable_score": round(neg_contrib, 4),
                "single_cpk": round(target_spec['val'], 4),
                "avg_cpk": round(avg_cpk, 4),
                "sample_size": target_spec['n'],
                "p3_count": target_spec['p3_count'],
                "p4_count": target_spec['p4_count'],
                "phase_label": target_spec['phase_label'],
            }
            detailed_machines = get_spec_warning_machines_detailed(single_item, indicator, target_date, min_samples=1)
            level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
            detailed_machines.sort(key=lambda m: (
                level_map.get(m.get("warning_level", "none"), 3),
                m.get("rank", 99),
                m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
            ))
            span_count = len(detailed_machines)
            for idx, m in enumerate(detailed_machines):
                m["row_span"] = span_count if idx == 0 else 0
            return {
                "status": "success",
                "is_latest_date": is_latest_date,
                "target_date": target_date,
                "data": sanitize_data(detailed_machines)
            }

        # 未指定规格：全厂规格负向贡献/CPK 排行
        results = []
        for s in valid_specs:
            if s['n'] < min_samples:
                continue
            
            if not is_latest_date:
                # 历史日期：保持原逻辑，只展示高风险且有负向贡献的规格
                if parsed_max_cpk is not None and s['val'] >= parsed_max_cpk:
                    continue
                neg_contrib = (avg_cpk - s['val']) * s['n']
                if neg_contrib <= 0:
                    continue
            else:
                # 最新一天：计算负向贡献，保留符合样本门槛的所有规格以方便 CPK 从低到高展示
                neg_contrib = (avg_cpk - s['val']) * s['n']
            
            results.append({
                "article10": s['article10'],
                "stable_score": round(neg_contrib, 4),
                "single_cpk": round(s['val'], 4),
                "avg_cpk": round(avg_cpk, 4),
                "sample_size": s['n'],
                "p3_count": s['p3_count'],
                "p4_count": s['p4_count'],
                "phase_label": s['phase_label'],
            })

        if is_latest_date:
            # 查看最新一天：在样本门槛过滤下，由最低到最高按照 CPK 升序排行展示规格 (CPK 越低越靠前)
            results.sort(key=lambda x: x['single_cpk'])
        else:
            # 查看历史记录：按负向贡献度绝对值倒序
            results.sort(key=lambda x: abs(x['stable_score']), reverse=True)

        top_results = results[:10]

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            spec_machine_groups = list(executor.map(
                lambda it: get_spec_warning_machines_detailed(it, indicator, target_date, min_samples),
                top_results
            ))

        level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
        processed_groups = []
        for g in spec_machine_groups:
            if not g:
                continue
            # 规格内机台排序：预警颜色等级优先 (🔴 > 🟠 > 🟡) -> 负向贡献度排名优先 (Rank 1 > Rank 2 > Rank 3) -> 跌幅优先
            g.sort(key=lambda m: (
                level_map.get(m.get("warning_level", "none"), 3),
                m.get("rank", 99),
                m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
            ))
            spec_max_level = g[0].get("warning_level", "none")
            stable_score = g[0].get("stable_score", 0)
            processed_groups.append({
                "spec_max_level": spec_max_level,
                "stable_score": stable_score,
                "machines": g
            })

        # 规格两级排序：🔴 > 🟠 > 🟡，同级按负向贡献度绝对值从重到轻
        processed_groups.sort(key=lambda pg: (
            level_map.get(pg["spec_max_level"], 3),
            -abs(pg["stable_score"])
        ))

        final_rows = []
        for pg in processed_groups:
            machs = pg["machines"]
            span_count = len(machs)
            for idx, m in enumerate(machs):
                m["row_span"] = span_count if idx == 0 else 0
                final_rows.append(m)

        return {
            "status": "success",
            "is_latest_date": is_latest_date,
            "target_date": target_date,
            "data": sanitize_data(final_rows)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



@app.get("/api/articles/barcode-measurements")
def get_article_barcode_measurements(
    article10: str = Query(..., description="选定的规格型号"),
    target_date: Optional[str] = Query(None, description="分析日期"),
    indicator: str = Query("rfpp", description="指标类型：rfpp | rfh1 | cony | weight"),
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    phase: Optional[str] = Query("all"),
    shift: Optional[str] = Query("all")
):
    """
    获取指定规格在单日内全部单胎（Barcode）实际测量值的时序数据（Run Chart / I-Chart），按生产时序排列
    """
    try:
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"
            
        phase_cond = get_phase_sql_condition(phase)
        date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"
        shift_cond = f" AND {build_production_time_where(time_col=time_col, shift=shift)}" if (shift and shift != 'all') else ""
        
        if not target_date:
            res = qry(f"SELECT MAX({date_col}) AS max_d FROM clean_yield WHERE article10 = ?", [article10])
            if res and res[0]['max_d']:
                target_date = str(res[0]['max_d'])
            else:
                target_date = "2026-08-10"

        if indicator == "weight":
            sql = f"""
                SELECT 
                    barcode,
                    TRY_CAST(tire_weight_actual_first AS DOUBLE) AS actual_val,
                    TRY_CAST(tire_weight_target_first AS DOUBLE) AS target_val,
                    ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) AS val,
                    COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) AS prod_time,
                    gt_workcenter,
                    tu_first_workcenter,
                    "group"
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND article10 = ?
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                ORDER BY prod_time ASC, barcode ASC
            """
            rows = qry(sql, [target_date, article10])
            if not rows:
                return {
                    "status": "success",
                    "summary": {
                        "article10": article10,
                        "target_date": target_date,
                        "indicator": indicator,
                        "indicator_label": "胎重 (实际值 / 偏差率)",
                        "unit": "kg",
                        "total_tires": 0,
                        "mean_val": 0,
                        "std_val": 0,
                        "usl": None,
                        "lsl": None,
                        "out_of_spec_count": 0,
                        "out_of_spec_rate": "0.00%",
                        "cpk": None
                    },
                    "data": []
                }
            
            vals = [float(r['actual_val']) for r in rows if r.get('actual_val') is not None]
            diff_vals = [float(r['val']) for r in rows if r.get('val') is not None]
            target_val = float(rows[0]['target_val']) if rows[0].get('target_val') else None
            
            mean_act = float(np.mean(vals)) if vals else 0.0
            std_act = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            mean_diff = float(np.mean(diff_vals)) if diff_vals else 0.0
            std_diff = float(np.std(diff_vals, ddof=1)) if len(diff_vals) > 1 else 0.0
            
            usl_tol = 0.8
            lsl_tol = -0.8
            out_count = sum(1 for d in diff_vals if d > usl_tol or d < lsl_tol)
            out_rate = round(out_count / len(diff_vals) * 100, 2) if diff_vals else 0.0
            
            data_list = []
            for r in rows:
                v = float(r['actual_val'])
                d = float(r['val']) if r.get('val') is not None else 0.0
                is_out = bool(d > usl_tol or d < lsl_tol)
                t_str = str(r['prod_time']) if r.get('prod_time') else ""
                data_list.append({
                    "barcode": str(r['barcode']),
                    "value": round(v, 3),
                    "diff_pct": round(d, 2),
                    "target_val": round(float(r['target_val']), 3) if r.get('target_val') else None,
                    "is_out_of_spec": is_out,
                    "prod_time": t_str,
                    "gt_workcenter": r.get('gt_workcenter') or "未知",
                    "tu_workcenter": r.get('tu_first_workcenter') or "未知"
                })
                
            return {
                "status": "success",
                "summary": {
                    "article10": article10,
                    "target_date": target_date,
                    "indicator": indicator,
                    "indicator_label": "胎重 (实际值 / 偏差率)",
                    "unit": "kg",
                    "total_tires": len(data_list),
                    "mean_val": round(mean_act, 3),
                    "std_val": round(std_act, 3),
                    "target_val": round(target_val, 3) if target_val else None,
                    "mean_diff_pct": round(mean_diff, 2),
                    "std_diff_pct": round(std_diff, 2),
                    "usl": round(target_val * (1 + usl_tol/100.0), 3) if target_val else None,
                    "lsl": round(target_val * (1 + lsl_tol/100.0), 3) if target_val else None,
                    "max_val": round(float(np.max(vals)), 3) if vals else 0.0,
                    "min_val": round(float(np.min(vals)), 3) if vals else 0.0,
                    "out_of_spec_count": out_count,
                    "out_of_spec_rate": f"{out_rate}%",
                    "cpk": None
                },
                "data": sanitize_data(data_list)
            }

        # RFPP / RFH1 / CONY 指标
        ind_col = "cony_first" if indicator == "cony" else ("rfppwc_first" if indicator == "rfpp" else "rfh1wc_first")
        ind_label = "CONY 锥度" if indicator == "cony" else ("RFPP 径向力峰峰值" if indicator == "rfpp" else "RFH1 径向力一次谐波")
        unit = "N"

        sql = f"""
            SELECT 
                barcode,
                TRY_CAST({ind_col} AS DOUBLE) AS val,
                COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) AS prod_time,
                gt_workcenter,
                tu_first_workcenter,
                "group",
                standard_rfpp,
                standard_rfh1,
                COALESCE(TRY_CAST(standard_rfpp AS DOUBLE), 
                         CASE "group" 
                             WHEN 'GROUP 1'  THEN 10.5 
                             WHEN 'GROUP 2A' THEN 11.5 
                             WHEN 'GROUP 2B' THEN 12.5 
                             WHEN 'GROUP 3'  THEN 12.5 
                         END) * 10.0 AS usl_rfpp,
                COALESCE(TRY_CAST(standard_rfh1 AS DOUBLE), 
                         CASE "group" 
                             WHEN 'GROUP 1'  THEN 7.5 
                             WHEN 'GROUP 2A' THEN 8.5 
                             WHEN 'GROUP 2B' THEN 9.0 
                             WHEN 'GROUP 3'  THEN 9.5 
                         END) * 10.0 AS usl_rfh1
            FROM clean_yield
            WHERE {date_col} = ?::DATE
              AND article10 = ?
              AND {ind_col} IS NOT NULL
              {phase_cond}
            ORDER BY prod_time ASC, barcode ASC
        """
        rows = qry(sql, [target_date, article10])
        if not rows:
            return {
                "status": "success",
                "summary": {
                    "article10": article10,
                    "target_date": target_date,
                    "indicator": indicator,
                    "indicator_label": ind_label,
                    "unit": unit,
                    "total_tires": 0,
                    "mean_val": 0,
                    "std_val": 0,
                    "usl": None,
                    "lsl": None,
                    "out_of_spec_count": 0,
                    "out_of_spec_rate": "0.00%",
                    "cpk": None
                },
                "data": []
            }

        vals = [float(r['val']) for r in rows if r.get('val') is not None]
        mean_v = float(np.mean(vals)) if vals else 0.0
        std_v = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        
        if indicator == "cony":
            usl_v, lsl_v = get_spec_limits(article10, "cony")
            cpk_v = calc_cpk(mean_v, std_v, usl_v, lsl_v)
            out_count = sum(1 for v in vals if (usl_v is not None and v > usl_v) or (lsl_v is not None and v < lsl_v))
        else:
            usl_v = float(rows[0]['usl_rfpp']) if indicator == "rfpp" and rows[0].get('usl_rfpp') is not None else (
                    float(rows[0]['usl_rfh1']) if indicator == "rfh1" and rows[0].get('usl_rfh1') is not None else 105.0)
            lsl_v = None
            cpk_v = (usl_v - mean_v) / (3.0 * std_v) if std_v > 1e-6 else 1.33
            out_count = sum(1 for v in vals if v > usl_v)

        out_rate = round(out_count / len(vals) * 100, 2) if vals else 0.0
        
        data_list = []
        for r in rows:
            v = float(r['val'])
            is_out = bool((usl_v is not None and v > usl_v) or (lsl_v is not None and v < lsl_v))
            t_str = str(r['prod_time']) if r.get('prod_time') else ""
            data_list.append({
                "barcode": str(r['barcode']),
                "value": round(v, 2),
                "is_out_of_spec": is_out,
                "prod_time": t_str,
                "gt_workcenter": r.get('gt_workcenter') or "未知",
                "tu_workcenter": r.get('tu_first_workcenter') or "未知"
            })

        return {
            "status": "success",
            "summary": {
                "article10": article10,
                "target_date": target_date,
                "indicator": indicator,
                "indicator_label": ind_label,
                "unit": unit,
                "total_tires": len(data_list),
                "mean_val": round(mean_v, 2),
                "std_val": round(std_v, 2),
                "usl": round(usl_v, 2) if usl_v is not None else None,
                "lsl": round(lsl_v, 2) if lsl_v is not None else None,
                "max_val": round(float(np.max(vals)), 2) if vals else 0.0,
                "min_val": round(float(np.min(vals)), 2) if vals else 0.0,
                "out_of_spec_count": out_count,
                "out_of_spec_rate": f"{out_rate}%",
                "cpk": round(float(cpk_v), 3) if cpk_v is not None and not (np.isnan(cpk_v) or np.isinf(cpk_v)) else None
            },
            "data": sanitize_data(data_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/api/machines/cpk")
def get_machines_cpk(
    target_date: str = Query(...),
    article10: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
    tolerance: float = Query(0.8),
):
    try:
        if indicator == "cony":
            indicator_col = "cony_first"
        else:
            indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        date_col = "tu_first_shift_date"

        if not target_date or not isinstance(target_date, str) or 'annotation=' in str(target_date):
            res = qry("SELECT MAX(tu_first_shift_date)::DATE AS max_d FROM clean_yield")[0]
            target_date = str(res['max_d'])
        else:
            target_date = str(target_date)

        if not end_date or not isinstance(end_date, str) or 'annotation=' in str(end_date):
            end_date = target_date
        else:
            end_date = str(end_date)

        if not start_date or not isinstance(start_date, str) or 'annotation=' in str(start_date):
            dt_obj = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (dt_obj - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            start_date = str(start_date)

        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 30

        col_sql = """
            SELECT column_name
            FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
            WHERE column_name LIKE '%workcenter%'
              AND column_name != 'css_workcenter'
        """
        wc_cols = [r["column_name"] for r in qry(col_sql)]

        # 规格 USL/LSL 基准
        global_usl, global_lsl = get_spec_limits(article10, indicator)

        wc_name_map = {
            "tread_workcenter": "胎面 (Tread)",
            "bead_workcenter": "胎圈 (Bead)",
            "inner_liner_workcenter": "内衬 (Inner Liner)",
            "sidewall_workcenter": "胎侧 (Sidewall)",
            "first_breaker_workcenter": "带束层1 (Breaker 1)",
            "second_breaker_workcenter": "带束层2 (Breaker 2)",
            "first_ply_workcenter": "帘布层 (Ply 1)",
            "wound_cap_ply1_workcenter": "冠带层1 (Wound Cap 1)",
            "wound_cap_ply2_workcenter": "冠带层2 (Wound Cap 2)",
            "ccs_workcenter": "胎胚成型 (CCS)",
            "gt_workcenter": "生胎成型 (GT)",
            "ct_workcenter": "硫化 (CT)",
            "tu_first_workcenter": "终检-均匀性 (TU)",
            "tg_first_workcenter": "终检-几何形 (TG)",
            "tb_first_workcenter": "终检-动平衡 (TB)",
        }

        grouped = {}

        for col in wc_cols:
            wc_label = wc_name_map.get(col, col)
            
            if indicator == "weight":
                active_sql = f"""
                    SELECT 
                        CAST({col} AS VARCHAR) as machine,
                        COUNT(*) as spec_n,
                        AVG(TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) as spec_avg_abs,
                        SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as sum_act,
                        SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) as sum_tar,
                        STDDEV(((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)) as spec_std
                    FROM clean_yield
                    WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                      AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                      AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                    GROUP BY 1
                    HAVING COUNT(*) >= ?
                """
                m_rows = qry(active_sql, [article10, target_date, min_samples])
                if not m_rows:
                    continue
                    
                grouped[wc_label] = []
                for r in m_rows:
                    m_code = str(r['machine'])
                    spec_n = int(r['spec_n'])
                    spec_avg_abs = float(r['spec_avg_abs']) if r['spec_avg_abs'] is not None else 0.0
                    spec_std = float(r['spec_std']) if r['spec_std'] is not None else 0.0
                    
                    sum_act = float(r['sum_act'])
                    sum_tar = float(r['sum_tar'])
                    spec_avg_pct = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0
                    
                    spec_is_warning = 1 if abs(spec_avg_pct) > tolerance else 0
                    
                    multi_sql = f"""
                        SELECT 
                            COUNT(*) as multi_n,
                            AVG(TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) as multi_avg_abs,
                            SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as sum_act,
                            SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) as sum_tar,
                            STDDEV(((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)) as multi_std
                        FROM clean_yield
                        WHERE {col} = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                          AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                          AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                    """
                    multi_res = qry(multi_sql, [m_code, target_date])[0]
                    multi_n = int(multi_res['multi_n']) if multi_res['multi_n'] else spec_n
                    multi_avg_abs = float(multi_res['multi_avg_abs']) if multi_res['multi_avg_abs'] is not None else spec_avg_abs
                    multi_std = float(multi_res['multi_std']) if multi_res['multi_std'] is not None else spec_std
                    
                    m_sum_act = float(multi_res['sum_act']) if multi_res['sum_act'] is not None else sum_act
                    m_sum_tar = float(multi_res['sum_tar']) if multi_res['sum_tar'] is not None else sum_tar
                    multi_avg_pct = (m_sum_act - m_sum_tar) / m_sum_tar * 100.0 if m_sum_tar > 0 else spec_avg_pct
                    
                    multi_is_warning = 1 if abs(multi_avg_pct) > tolerance else 0
                    
                    grouped[wc_label].append({
                        "workcenter_col": col,
                        "machine": m_code,
                        "spec_n": spec_n,
                        "spec_avg": round(spec_avg_abs, 2),  # 物理均值差值 kg
                        "spec_std": round(spec_std, 2),      # 百分比偏差标准差
                        "spec_cpk": spec_avg_pct,            # 有符号百分比偏差 (%)
                        "spec_is_warning": spec_is_warning,
                        "spec_rule_a": 0,
                        "spec_rule_b": 0,
                        "spec_rule_a_count": 0,
                        "spec_warning_threshold": round(tolerance, 2),
                        
                        "multi_n": multi_n,
                        "multi_avg": round(multi_avg_abs, 2), # 多规格物理均值差值 kg
                        "multi_std": round(multi_std, 2),
                        "multi_cpk": multi_avg_pct,           # 有符号百分比偏差 (%)
                        "multi_is_warning": multi_is_warning,
                        "multi_rule_a": 0,
                        "multi_rule_b": 0,
                        "multi_rule_a_count": 0,
                        "multi_warning_threshold": round(tolerance, 2),
                        "is_warning": spec_is_warning or multi_is_warning
                    })
                continue

            col_name_map = wc_name_map.get(col, col)

            if indicator == "cony":
                active_sql = f"""
                    SELECT 
                        CAST({col} AS VARCHAR) as machine,
                        COUNT(*) as spec_n,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as spec_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as spec_std
                    FROM clean_yield
                    WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                    GROUP BY 1
                    HAVING COUNT(*) >= ?
                """
                m_rows = qry(active_sql, [article10, target_date, min_samples])
                if not m_rows:
                    continue

                grouped[wc_label] = []
                for r in m_rows:
                    m_code = str(r['machine'])
                    spec_n = int(r['spec_n'])
                    spec_avg = float(r['spec_avg']) if r['spec_avg'] is not None else 0.0
                    spec_std = float(r['spec_std']) if r['spec_std'] is not None else 0.0
                    spec_cpk = round(calc_cpk(spec_avg, spec_std, global_usl, global_lsl), 2)

                    multi_today_sql = f"""
                        SELECT 
                            COUNT(*) as multi_n,
                            AVG(TRY_CAST({indicator_col} AS DOUBLE)) as multi_avg,
                            STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as multi_std
                        FROM clean_yield
                        WHERE {col} = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                    """
                    multi_t_res = qry(multi_today_sql, [m_code, target_date])
                    if multi_t_res and multi_t_res[0]['multi_n']:
                        multi_n = int(multi_t_res[0]['multi_n'])
                        multi_avg = float(multi_t_res[0]['multi_avg']) if multi_t_res[0]['multi_avg'] is not None else spec_avg
                        multi_std = float(multi_t_res[0]['multi_std']) if multi_t_res[0]['multi_std'] is not None else spec_std
                    else:
                        multi_n, multi_avg, multi_std = spec_n, spec_avg, spec_std

                    multi_cpk = round(calc_cpk(multi_avg, multi_std, global_usl, global_lsl), 2)

                    grouped[wc_label].append({
                        "workcenter_col": col,
                        "machine": m_code,
                        "spec_n": spec_n,
                        "spec_avg": round(spec_avg, 2),
                        "spec_std": round(spec_std, 2),
                        "spec_cpk": spec_cpk,
                        "spec_is_warning": 0,
                        "spec_rule_a": 0,
                        "spec_rule_b": 0,
                        "spec_rule_a_count": 0,
                        "spec_warning_threshold": round(global_usl, 2),
                        
                        "multi_n": multi_n,
                        "multi_avg": round(multi_avg, 2),
                        "multi_std": round(multi_std, 2),
                        "multi_cpk": multi_cpk,
                        "multi_is_warning": 0,
                        "multi_rule_a": 0,
                        "multi_rule_b": 0,
                        "multi_rule_a_count": 0,
                        "multi_warning_threshold": round(global_usl, 2),
                        "is_warning": 0
                    })
                continue

            # 1. 查当天的活跃机台 (按选中单规格)
            active_sql = f"""
                SELECT 
                    CAST({col} AS VARCHAR) as machine,
                    COUNT(*) as spec_n,
                    AVG(TRY_CAST({indicator_col} AS DOUBLE)) as spec_avg,
                    STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as spec_std
                FROM clean_yield
                WHERE {col} IS NOT NULL AND article10 = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            m_rows = qry(active_sql, [article10, target_date, min_samples])
            if not m_rows:
                continue

            grouped[wc_label] = []

            for r in m_rows:
                m_code = str(r['machine'])
                spec_n = int(r['spec_n'])
                spec_avg = float(r['spec_avg']) if r['spec_avg'] is not None else 0.0
                spec_std = float(r['spec_std']) if r['spec_std'] is not None else 0.0

                if spec_std > 0:
                    spec_cpk = round(calc_cpk(spec_avg, spec_std, global_usl, global_lsl), 2)
                else:
                    spec_cpk = 1.33

                # ── 单规格 CPK 预警判断 (基于 CPK 序列与 CPK 预警线对齐) ──
                spec_hist_sql = f"""
                    SELECT 
                        {date_col}::DATE as dt,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as day_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as day_std
                    FROM clean_yield
                    WHERE {col} = ? AND article10 = ? AND {indicator_col} IS NOT NULL AND {date_col} IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 ASC
                """
                s_hist_rows = qry(spec_hist_sql, [m_code, article10])
                s_cpk_series = []
                for h in s_hist_rows:
                    m_v = float(h['day_avg']) if h['day_avg'] is not None else 0.0
                    s_v = float(h['day_std']) if h['day_std'] is not None else 0.0
                    c_v = round(calc_cpk(m_v, s_v, global_usl, global_lsl), 2)
                    s_cpk_series.append((str(h['dt']), c_v))

                spec_rule_a = 0
                spec_rule_b = 0
                spec_rule_a_count = 0
                spec_threshold = 0.0

                if s_cpk_series:
                    s_cpk_vals = [c[1] for c in s_cpk_series]
                    s_mean = float(np.mean(s_cpk_vals))
                    s_std = float(np.std(s_cpk_vals))
                    spec_threshold = round(max(0.0, s_mean - 1.0 * s_std), 2)
                    
                    # 截至选中日期的历史点
                    s_up_to_target = [c for c in s_cpk_series if c[0] <= target_date]
                    
                    # 筛选过去 5 天内的点 (基于 tu_first_shift_date 日期判定)
                    try:
                        target_dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
                        start_limit_dt = target_dt_obj - timedelta(days=5)
                        s_past_5_days = []
                        for dt_str, cpk_val in s_up_to_target:
                            try:
                                d_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                                if start_limit_dt <= d_obj <= target_dt_obj:
                                    s_past_5_days.append(cpk_val)
                            except ValueError:
                                pass
                    except Exception:
                        s_past_5_days = [c[1] for c in s_up_to_target]
                        
                    spec_rule_a_count = sum(1 for val in s_past_5_days if val <= spec_threshold)
                    if spec_rule_a_count >= 3:
                        spec_rule_a = 1

                    # 连续 3 天下降
                    if len(s_up_to_target) >= 4:
                        recent_3 = [c[1] for c in s_up_to_target[-4:]]
                        diffs = [recent_3[i] - recent_3[i-1] for i in range(1, 4)]
                        if all(d < 0 for d in diffs):
                            spec_rule_b = 1

                spec_is_warning = 1 if (spec_rule_a == 1 or spec_rule_b == 1) else 0


                # ── 多规格 (全规格产量加权) CPK 预警判断 ──
                multi_today_sql = f"""
                    SELECT 
                        COUNT(*) as multi_n,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as multi_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as multi_std
                    FROM clean_yield
                    WHERE {col} = ? AND {date_col}::DATE = ?::DATE AND {date_col} IS NOT NULL
                """
                multi_t_res = qry(multi_today_sql, [m_code, target_date])
                if multi_t_res and multi_t_res[0]['multi_n']:
                    multi_n = int(multi_t_res[0]['multi_n'])
                    multi_avg = float(multi_t_res[0]['multi_avg']) if multi_t_res[0]['multi_avg'] is not None else 0.0
                    multi_std = float(multi_t_res[0]['multi_std']) if multi_t_res[0]['multi_std'] is not None else 0.0
                else:
                    multi_n, multi_avg, multi_std = spec_n, spec_avg, spec_std

                if multi_std > 0:
                    multi_cpk = round(calc_cpk(multi_avg, multi_std, global_usl, global_lsl), 2)
                else:
                    multi_cpk = 1.33

                multi_hist_sql = f"""
                    SELECT 
                        {date_col}::DATE as dt,
                        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as day_avg,
                        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as day_std
                    FROM clean_yield
                    WHERE {col} = ? AND {indicator_col} IS NOT NULL AND {date_col} IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 ASC
                """
                m_hist_rows = qry(multi_hist_sql, [m_code])
                m_cpk_series = []
                for h in m_hist_rows:
                    m_v = float(h['day_avg']) if h['day_avg'] is not None else 0.0
                    s_v = float(h['day_std']) if h['day_std'] is not None else 0.0
                    c_v = round(calc_cpk(m_v, s_v, global_usl, global_lsl), 2)
                    m_cpk_series.append((str(h['dt']), c_v))

                multi_rule_a = 0
                multi_rule_b = 0
                multi_rule_a_count = 0
                multi_threshold = 0.0

                if m_cpk_series:
                    m_cpk_vals = [c[1] for c in m_cpk_series]
                    m_mean = float(np.mean(m_cpk_vals))
                    m_std = float(np.std(m_cpk_vals))
                    multi_threshold = round(max(0.0, m_mean - 1.0 * m_std), 2)

                    m_up_to_target = [c for c in m_cpk_series if c[0] <= target_date]
                    
                    # 筛选过去 5 天内的点 (基于 tu_first_shift_date 日期判定)
                    try:
                        target_dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
                        start_limit_dt = target_dt_obj - timedelta(days=5)
                        m_past_5_days = []
                        for dt_str, cpk_val in m_up_to_target:
                            try:
                                d_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                                if start_limit_dt <= d_obj <= target_dt_obj:
                                    m_past_5_days.append(cpk_val)
                            except ValueError:
                                pass
                    except Exception:
                        m_past_5_days = [c[1] for c in m_up_to_target]

                    multi_rule_a_count = sum(1 for val in m_past_5_days if val <= multi_threshold)
                    if multi_rule_a_count >= 3:
                        multi_rule_a = 1

                    if len(m_up_to_target) >= 4:
                        m_recent_3 = [c[1] for c in m_up_to_target[-4:]]
                        mdiffs = [m_recent_3[i] - m_recent_3[i-1] for i in range(1, 4)]
                        if all(d < 0 for d in mdiffs):
                            multi_rule_b = 1

                multi_is_warning = 1 if (multi_rule_a == 1 or multi_rule_b == 1) else 0

                grouped[wc_label].append({
                    "workcenter_col": col,
                    "machine": m_code,
                    
                    # 单规格
                    "spec_n": spec_n,
                    "spec_avg": round(spec_avg, 2),
                    "spec_std": round(spec_std, 2),
                    "spec_cpk": spec_cpk,
                    "spec_is_warning": spec_is_warning,
                    "spec_rule_a": spec_rule_a,
                    "spec_rule_b": spec_rule_b,
                    "spec_rule_a_count": spec_rule_a_count,
                    "spec_warning_threshold": spec_threshold,

                    # 多规格 (全规格产量加权)
                    "multi_n": multi_n,
                    "multi_avg": round(multi_avg, 2),
                    "multi_std": round(multi_std, 2),
                    "multi_cpk": multi_cpk,
                    "multi_is_warning": multi_is_warning,
                    "multi_rule_a": multi_rule_a,
                    "multi_rule_b": multi_rule_b,
                    "multi_rule_a_count": multi_rule_a_count,
                    "multi_warning_threshold": multi_threshold,

                    "is_warning": spec_is_warning or multi_is_warning
                })

        # 按是否预警降序，预警机台最靠前
        for wc_label in grouped:
            grouped[wc_label].sort(key=lambda x: (x.get("multi_is_warning", 0), x.get("spec_is_warning", 0)), reverse=True)

        return {"status": "success", "data": sanitize_data(grouped)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/api/machines/cpk/trend")
def get_machine_cpk_trend(
    machine: str = Query(...),
    workcenter_col: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    article10: Optional[str] = Query(None),
    mode: Optional[str] = Query(None), # "single" | "multi"
    tolerance: float = Query(0.8)
):
    try:
        normalized_col = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
        date_col = "tu_first_shift_date"

        if indicator == "weight":
            where_parts = [f"{normalized_col} = ?", f"{date_col} IS NOT NULL"]
            params = [machine]
            if (mode == "single" or mode == "spec_3sigma") or (article10 and mode != "multi" and mode != "all_3sigma"):
                where_parts.append("article10 = ?")
                params.append(article10)
                
            where_clause = "WHERE " + " AND ".join(where_parts) + """
              AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
              AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
            """
            sql = f"""
                SELECT 
                    {date_col}::DATE AS time_period,
                    COUNT(*) AS sample_size,
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_act,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) as sum_tar,
                    AVG(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as avg_actual,
                    STDDEV(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as std_actual
                FROM clean_yield
                {where_clause}
                GROUP BY 1
                HAVING COUNT(*) >= 1
                ORDER BY 1
            """
            rows = qry(sql, params)
            trend_data = []
            for r in rows:
                sum_act = float(r['sum_act'])
                sum_tar = float(r['sum_tar'])
                avg_actual = float(r['avg_actual']) if r['avg_actual'] is not None else 0.0
                std_actual = float(r['std_actual']) if r['std_actual'] is not None else 0.0
                avg_diff_pct = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0
                
                trend_data.append({
                    "date": str(r['time_period']),
                    "sample_size": int(r['sample_size']),
                    "mean_val": round(avg_actual, 3),   # 实际胎重均值 (kg)
                    "std_val": round(std_actual, 4),    # 实际胎重标准差 (kg)
                    "cpk_val": round(avg_diff_pct, 3)   # 偏差率 % (diff)
                })
                
            return {
                "status": "success",
                "mode": mode or ("single" if article10 else "multi"),
                "data": sanitize_data(trend_data),
                "control_limits": {
                    "cpk_mean": 0.0,
                    "cpk_std": 0.0,
                    "warning_threshold": round(tolerance, 2)
                }
            }

        if indicator == "cony":
            indicator_col = "cony_first"
        else:
            indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        normalized_col = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
        date_col = "tu_first_shift_date"

        # 计算规格 USL/LSL 基准
        if article10 and (mode == "single" or mode == "spec_3sigma" or mode != "multi" and mode != "all_3sigma"):
            global_usl, global_lsl = get_spec_limits(article10, indicator)
        else:
            global_usl, global_lsl = get_spec_limits("", indicator)

        where_parts = [f"{normalized_col} = ?", f"{indicator_col} IS NOT NULL", f"{date_col} IS NOT NULL"]
        params = [machine]

        # 单规格模式
        if (mode == "single" or mode == "spec_3sigma") or (article10 and mode != "multi" and mode != "all_3sigma"):
            where_parts.append("article10 = ?")
            params.append(article10)

        where_clause = "WHERE " + " AND ".join(where_parts)

        sql = f"""
            SELECT 
                {date_col}::DATE AS time_period,
                COUNT(*) AS sample_size,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS mean_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS std_val
            FROM clean_yield
            {where_clause}
            GROUP BY 1
            HAVING COUNT(*) >= 1
            ORDER BY 1
        """
        rows = qry(sql, params)
        trend_data = []
        cpk_list = []

        for r in rows:
            m_val = float(r['mean_val']) if r['mean_val'] is not None else 0.0
            s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
            
            cpk_val = round(calc_cpk(m_val, s_val, global_usl, global_lsl), 2)

            cpk_list.append(cpk_val)

            trend_data.append({
                "date": str(r['time_period']),
                "sample_size": int(r['sample_size']),
                "mean_val": round(m_val, 2),
                "std_val": round(s_val, 2),
                "cpk_val": cpk_val
            })

        # 计算 CPK 控制限与预警基准线 (Mean - 1*std)
        cpk_mean = float(np.mean(cpk_list)) if cpk_list else 1.33
        cpk_std = float(np.std(cpk_list)) if len(cpk_list) > 1 else 0.0
        warning_threshold = round(max(0.0, cpk_mean - 1.0 * cpk_std), 2)

        return {
            "status": "success",
            "mode": mode or ("single" if article10 else "multi"),
            "data": sanitize_data(trend_data),
            "control_limits": {
                "cpk_mean": round(cpk_mean, 2),
                "cpk_std": round(cpk_std, 2),
                "warning_threshold": warning_threshold
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



@app.get("/api/machines/combination-tree")
def get_machine_combination_tree(
    spec: str = Query(...),
    start_wc: Optional[str] = Query(None),
    end_wc: Optional[str] = Query(None),
    indicator: str = Query("rfpp"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    target_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
):
    try:
        if not isinstance(indicator, str):
            indicator = "rfpp"
        if not isinstance(spec, str):
            spec = ""
        if not isinstance(start_date, str):
            start_date = None
        if not isinstance(end_date, str):
            end_date = None
        if not isinstance(target_date, str):
            target_date = None
        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 10
        if start_date in ("null", "None", ""):
            start_date = None
        if end_date in ("null", "None", ""):
            end_date = None
        if target_date in ("null", "None", ""):
            target_date = None

        if indicator == "cony":
            indicator_col = "cony_first"
        else:
            indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"

        # 计算规格 USL/LSL 基准 (确保与看板全局统一)
        global_usl, global_lsl = get_spec_limits(spec, indicator)

        where_parts = ["article10 = ?"]
        params = [spec]

        if start_date and end_date:
            where_parts.append("tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE")
            params.extend([start_date, end_date])
        elif target_date:
            where_parts.append("tu_first_shift_date::DATE = ?::DATE")
            params.append(target_date)

        # 聚合核心工段组合 (所有指标均取 GT/CT/TU，不考虑终检 TB 机台)
        tb_select = "NULL as tb,"
        tb_not_null = ""
        group_cols = "1, 2, 3"

        sql = f"""
            SELECT 
                CAST(gt_workcenter AS VARCHAR) as gt,
                CAST(ct_workcenter AS VARCHAR) as ct,
                CAST(tu_first_workcenter AS VARCHAR) as tu,
                {tb_select}
                COUNT(*) as lot_cnt,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) as avg_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as std_val
            FROM clean_yield
            WHERE {" AND ".join(where_parts)}
              AND gt_workcenter IS NOT NULL
              AND ct_workcenter IS NOT NULL
              AND tu_first_workcenter IS NOT NULL
              {tb_not_null}
            GROUP BY {group_cols}
            HAVING COUNT(*) >= 1
            ORDER BY lot_cnt DESC
        """
        rows = qry(sql, params)

        path_list = []
        for r in rows:
            path_list.append({
                "gt": r['gt'],
                "ct": r['ct'],
                "tu": r['tu'],
                "tb": r['tb'],
                "lot_cnt": int(r['lot_cnt']),
                "avg_val": float(r['avg_val']) if r['avg_val'] is not None else 0.0,
                "std_val": float(r['std_val']) if r['std_val'] is not None else 0.0
            })

        return {
            "status": "success",
            "usl": global_usl,
            "lsl": global_lsl,
            "paths": path_list
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



def aggregate_node_stats_py(rows, usl, indicator="rfpp", lsl=None):
    import math
    if not rows:
        return {"lot_cnt": 0, "avg": 0.0, "std": 0.0, "cpk": 1.33}
    if len(rows) == 1:
        return {
            "lot_cnt": rows[0]["lot_cnt"],
            "avg": rows[0]["avg_val"],
            "std": rows[0]["std_val"],
            "cpk": rows[0]["cpk"]
        }
    
    total_n = sum(r["lot_cnt"] for r in rows)
    if total_n <= 0:
        return {"lot_cnt": 0, "avg": 0.0, "std": 0.0, "cpk": 1.33}
        
    combined_mean = sum(r["lot_cnt"] * r["avg_val"] for r in rows) / total_n
    
    combined_var = sum(
        r["lot_cnt"] * (r["std_val"] ** 2 + (r["avg_val"] - combined_mean) ** 2)
        for r in rows
    ) / total_n
    
    combined_std = math.sqrt(combined_var)
    if indicator == "weight":
        cpk = combined_mean
    else:
        cpk = calc_cpk(combined_mean, combined_std, usl, lsl)
    
    return {
        "lot_cnt": total_n,
        "avg": combined_mean,
        "std": combined_std,
        "cpk": cpk
    }


def get_top_warning_machines(
    n: int = 2,
    article10: str = "",
    indicator: str = "rfpp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_date: Optional[str] = None,
    min_samples: int = 10,
    include_tu: bool = True,
) -> list:
    try:
        if not isinstance(start_date, str) or start_date in ("null", "None", ""):
            start_date = None
        if not isinstance(end_date, str) or end_date in ("null", "None", ""):
            end_date = None
        if not isinstance(target_date, str) or target_date in ("null", "None", ""):
            target_date = None
        if not isinstance(indicator, str):
            indicator = "rfpp"

        if indicator == "weight":
            indicator_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
            avg_col = f"AVG(ABS(TRY_CAST({indicator_col} AS DOUBLE)))"
        elif indicator == "cony":
            indicator_col = "cony_first"
            avg_col = f"AVG(TRY_CAST({indicator_col} AS DOUBLE))"
        else:
            indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            avg_col = f"AVG(TRY_CAST({indicator_col} AS DOUBLE))"
            
        global_usl, global_lsl = get_spec_limits(article10, indicator)

        where_parts = ["article10 = ?"]
        params = [article10]

        if start_date and end_date:
            where_parts.append("tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE")
            params.extend([start_date, end_date])
        elif target_date:
            where_parts.append("tu_first_shift_date::DATE = ?::DATE")
            params.append(target_date)

        if indicator == "weight":
            where_parts.append("tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0")
        else:
            where_parts.append(f"{indicator_col} IS NOT NULL")

        # 预警机台评估工序 (根据 include_tu 动态判定是否包含 TU)
        cols = ["gt_workcenter", "ct_workcenter", "tu_first_workcenter"] if include_tu else ["gt_workcenter", "ct_workcenter"]
        tu_select = "CAST(tu_first_workcenter AS VARCHAR) as tu," if include_tu else "NULL as tu,"
        tb_select = "NULL as tb,"
        tb_not_null = ""
        group_cols = "1, 2, 3" if include_tu else "1, 2"

        sql = f"""
            SELECT 
                CAST(gt_workcenter AS VARCHAR) as gt,
                CAST(ct_workcenter AS VARCHAR) as ct,
                {tu_select}
                {tb_select}
                COUNT(*) as lot_cnt,
                {avg_col} as avg_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as std_val
            FROM clean_yield
            WHERE {" AND ".join(where_parts)}
              AND gt_workcenter IS NOT NULL
              AND ct_workcenter IS NOT NULL
              {tb_not_null}
            GROUP BY {group_cols}
            HAVING COUNT(*) >= 1
        """
        rows = qry(sql, params)
        if not rows:
            return []

        # 映射数据并计算 cpk
        data = []
        for r in rows:
            lot_cnt = int(r['lot_cnt'])
            avg_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
            std_val = float(r['std_val']) if r['std_val'] is not None else 0.0
            
            if indicator == "weight":
                cpk = avg_val
            else:
                cpk = calc_cpk(avg_val, std_val, global_usl, global_lsl)
            
            item = {
                "lot_cnt": lot_cnt,
                "cpk": cpk,
                "avg_val": avg_val,
                "std_val": std_val,
                "gt_workcenter": r['gt'],
                "ct_workcenter": r['ct'],
                "tu_first_workcenter": r['tu'],
            }

            data.append(item)

        # 1. 全局加权 CPK (改用合并方差)
        global_avg_cpk = aggregate_node_stats_py(data, global_usl, indicator, lsl=global_lsl)["cpk"]

        # 计算全局总产量 (作为分量占比的分母)
        total_tires = sum(p['lot_cnt'] for p in data)
        if total_tires <= 0:
            return []

        # 2. 查找活跃层级中的唯一机台及对应的工段列
        machines = {}
        for p in data:
            for col in cols:
                m_val = p.get(col)
                if m_val:
                    machines[m_val] = col

        # 3. 计算机台贡献分析 (改用合并方差)
        raw_machine_list = []
        for mach, mach_col in machines.items():
            mach_tires = 0
            matching_rows = []
            partner_groups = {}

            for p in data:
                matched_cols = [col for col in cols if p.get(col) == mach]
                if matched_cols:
                    mach_tires += p['lot_cnt']
                    matching_rows.append(p)

                    for m_col in matched_cols:
                        partner_parts = [('*' if c == m_col else (p.get(c) or '*')) for c in cols]
                        partner_key = "_".join(partner_parts)

                        if partner_key not in partner_groups:
                            partner_groups[partner_key] = {
                                "mCol": m_col,
                                "partnerParts": partner_parts,
                                "machTires": 0
                            }
                        partner_groups[partner_key]["machTires"] += p['lot_cnt']

            # 用合并方差公式计算该机台总体的综合 CPK
            mach_avg_cpk = aggregate_node_stats_py(matching_rows, global_usl, indicator, lsl=global_lsl)["cpk"] if matching_rows else 0.0

            controlled_baseline_numerator = 0.0
            controlled_baseline_denominator = 0.0

            for group in partner_groups.values():
                m_col = group["mCol"]
                partner_parts = group["partnerParts"]
                group_mach_tires = group["machTires"]

                other_rows = []

                for p in data:
                    if p.get(m_col) != mach:
                        is_match = True
                        for idx, c in enumerate(cols):
                            if c == m_col:
                                continue
                            if p.get(c) != partner_parts[idx]:
                                is_match = False
                                break
                        if is_match:
                            other_rows.append(p)

                # 用合并方差公式计算该替代路径下的联合对照基准 CPK (若缺失则默认回退全局均值)
                partner_baseline = aggregate_node_stats_py(other_rows, global_usl, indicator, lsl=global_lsl)["cpk"] if other_rows else global_avg_cpk
                controlled_baseline_numerator += partner_baseline * group_mach_tires
                controlled_baseline_denominator += group_mach_tires

            controlled_baseline = (
                controlled_baseline_numerator / controlled_baseline_denominator
                if controlled_baseline_denominator > 0
                else global_avg_cpk
            )

            contribution = mach_avg_cpk - controlled_baseline
            volume = mach_tires / total_tires
            sqrt_tires = math.sqrt(mach_tires)

            if mach_tires >= min_samples:
                raw_machine_list.append({
                    "machine": mach,
                    "workcenter_col": mach_col,
                    "contribution": contribution,
                    "volume": volume,
                    "mach_tires": mach_tires,
                    "sqrt_tires": sqrt_tires
                })

        total_sqrt_tires = sum(m["sqrt_tires"] for m in raw_machine_list)
        machine_list = []
        for m in raw_machine_list:
            sqrt_volume_share = (m["sqrt_tires"] / total_sqrt_tires) if total_sqrt_tires > 0 else 0.0
            impact_score = m["contribution"] * sqrt_volume_share
            machine_list.append({
                "machine": m["machine"],
                "workcenter_col": m["workcenter_col"],
                "contribution": m["contribution"],
                "volume": m["volume"],
                "sqrt_volume_share": sqrt_volume_share,
                "impact_score": impact_score,
                "mach_tires": m["mach_tires"]
            })

        # 按 impact_score 排序得出前 N 预警机台
        if indicator == "weight":
            # 按 impact_score 降序（最大正的排最前，代表独立拉大偏离最多）
            machine_list.sort(key=lambda x: x["impact_score"], reverse=True)
            filtered = [x for x in machine_list if x["impact_score"] > 0]
        else:
            # 按 impact_score 升序（最负的最靠前）
            machine_list.sort(key=lambda x: x["impact_score"])
            filtered = [x for x in machine_list if x["impact_score"] < 0]
            
        if not filtered:
            filtered = machine_list
            
        # 特别优化规则（仅对 TU 终检工段生效）：
        # 若 Top 1 机台是 TU 机台，且该 TU 机台在 TU 工段总产量中的占比 > 90%，
        # 则说明全场 90% 以上的轮胎都由它测量，缺乏对照基准，取消其 Top 1 高亮，顺延至第 2 名机台。
        if filtered:
            top1 = filtered[0]
            is_tu_top1 = (top1.get("workcenter_col") == "tu_first_workcenter") or str(top1.get("machine")).startswith("TU")
            if is_tu_top1:
                tu_total_tires = sum(
                    m["mach_tires"] for m in raw_machine_list
                    if m.get("workcenter_col") == "tu_first_workcenter" or str(m.get("machine")).startswith("TU")
                )
                if tu_total_tires > 0:
                    tu_share = top1["mach_tires"] / tu_total_tires
                    if tu_share >= 0.80 and len(filtered) > 1:
                        overpass_tu = filtered.pop(0)
                        filtered.append(overpass_tu)

        result = []
        for idx, item in enumerate(filtered[:n]):
            result.append({
                "rank": idx + 1,
                "machine": item["machine"],
                "workcenter_col": item["workcenter_col"],
                "impact_score": round(item["impact_score"], 4)
            })
        return result
    except Exception as e:
        print(f"Error in get_top_warning_machines: {e}")
        return []


def calculate_critical_machine(
    article10: str,
    indicator: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_date: Optional[str] = None,
    min_samples: int = 10,
) -> Optional[str]:
    top_list = get_top_warning_machines(
        n=1,
        article10=article10,
        indicator=indicator,
        start_date=start_date,
        end_date=end_date,
        target_date=target_date,
        min_samples=min_samples
    )
    if top_list:
        return top_list[0]["machine"]
    return None


def get_spec_warning_machines_detailed(item: dict, indicator: str, target_date: str, min_samples: int = 10) -> list:
    article10 = item.get("article10")
    if not article10 or not target_date:
        fallback_item = {
            **item,
            "warning_machine": "无",
            "warning_level": "none",
            "primary_dot": "",
            "cpk_pct_change": None,
            "action_text": "-",
            "action_type": "info",
            "action_tooltip": "",
            "can_click_recommend": False,
            "recommend_stage": "gt",
            "status_badges": []
        }
        return [fallback_item]

    try:
        top_list = get_top_warning_machines(
            n=3,
            article10=article10,
            indicator=indicator,
            target_date=target_date,
            min_samples=min_samples,
            include_tu=True
        )
        if not top_list and min_samples > 1:
            top_list = get_top_warning_machines(
                n=3,
                article10=article10,
                indicator=indicator,
                target_date=target_date,
                min_samples=1,
                include_tu=True
            )

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        d_start = (target_dt - timedelta(days=3)).strftime("%Y-%m-%d")

        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
            usl, lsl = None, None
        elif indicator == "cony":
            ind_col = "cony_first"
            usl, lsl = get_spec_limits(article10, indicator)
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            usl, lsl = get_spec_limits(article10, indicator)

        best_tu, best_tu_val = get_best_tu_machine_for_spec(article10, indicator, min_samples=1)

        valid_machines = []
        seen_machines = set()

        for m_item in top_list:
            mach = m_item["machine"]
            wc_col = m_item.get("workcenter_col") or ""
            seen_machines.add(mach)

            # 4 天历史数据查询
            hist_sql = f"""
                SELECT 
                    CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) as d,
                    COUNT(*) as cnt,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v
                FROM clean_yield
                WHERE article10 = ?
                  AND (gt_workcenter = ? OR ct_workcenter = ? OR tu_first_workcenter = ?)
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1
                ORDER BY 1
            """
            rows = qry(hist_sql, [article10, mach, mach, mach, d_start, target_date])

            t0_cpk = None
            prev_cpks = []
            for r in rows:
                d_str = str(r['d'])
                avg_v = float(r['avg_v'] or 0)
                std_v = float(r['std_v'] or 0)
                cpk_val = avg_v if indicator == "weight" else calc_cpk(avg_v, std_v, usl, lsl)
                if d_str == target_date:
                    t0_cpk = cpk_val
                else:
                    if cpk_val is not None:
                        prev_cpks.append(cpk_val)

            mu_3d = sum(prev_cpks) / len(prev_cpks) if prev_cpks else None
            is_new_online = bool(t0_cpk is not None and not prev_cpks)
            cpk_pct_change = None
            if t0_cpk is not None and mu_3d is not None and mu_3d > 0:
                cpk_pct_change = round(((t0_cpk - mu_3d) / mu_3d) * 100, 1)

            # 过滤逻辑：自动过滤当班 CPK 提升（> 0）的机台，仅保留恶化或新机台
            if cpk_pct_change is not None and cpk_pct_change > 0:
                continue

            # 多天在榜统计
            days_on_board = 1
            days_rank1 = 1 if m_item.get("rank") == 1 else 0
            for day_offset in (1, 2):
                prev_d = (target_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                prev_top = get_top_warning_machines(n=3, article10=article10, indicator=indicator, target_date=prev_d, min_samples=1, include_tu=True)
                for idx, pm in enumerate(prev_top):
                    if pm["machine"] == mach:
                        days_on_board += 1
                        if idx == 0:
                            days_rank1 += 1
                        break

            # CGRS 调参恶化因果判定 (仅成型与硫化工段设备)
            has_degraded_tuning = False
            degraded_tooltip = ""
            if indicator != "weight" and not mach.startswith("TU"):
                try:
                    cgrs_comp = calculate_cgrs_cpk_comparison(
                        workcenter=mach,
                        article10=article10,
                        target_date=target_date,
                        indicator=indicator,
                        limit_n=20
                    )
                    if cgrs_comp and cgrs_comp.get("has_cgrs"):
                        ev_list = cgrs_comp.get("events_summary") or []
                        # 查找是否存在改后导致质量恶化 (cpk_diff < 0) 的有效调参事件
                        degraded_ev = next((ev for ev in ev_list if ev.get("cpk_diff") is not None and ev.get("cpk_diff") < 0), None)
                        if degraded_ev:
                            has_degraded_tuning = True
                            diff_val = degraded_ev.get('cpk_diff', 0.0)
                            yoy_val = degraded_ev.get('yoy_pct', 0.0)
                            degraded_tooltip = f"调参后恶化：CPK 变化 {diff_val:+.3f} ({yoy_val:+.1f}%)"
                except Exception as err:
                    print(f"[Warning] calculate_cgrs_cpk_comparison failed for {mach}: {err}")

            is_dominant_top1 = days_rank1 >= 2
            is_red = has_degraded_tuning or is_dominant_top1
            is_drop_35 = cpk_pct_change is not None and cpk_pct_change <= -35
            is_cont_top23 = days_on_board >= 3 and days_rank1 < 2
            is_orange = (not is_red) and (is_drop_35 or is_cont_top23)
            is_yellow = (not is_red and not is_orange)

            status_badges = []
            if is_red:
                warning_level = "red"
                primary_dot = "🔴"
                if has_degraded_tuning:
                    status_badges.append({"color": "red", "text": "🔴 调参恶化", "tooltip": degraded_tooltip or "检测到 CGRS 调参后 CPK 下降"})
                if is_dominant_top1:
                    status_badges.append({"color": "red", "text": "🔴 持续霸榜(#1)", "tooltip": f"在近 3 天中有 {days_rank1} 天位列负贡献榜第 1 名"})
            elif is_orange:
                warning_level = "orange"
                primary_dot = "🟠"
                if is_drop_35:
                    status_badges.append({"color": "orange", "text": "🟠 骤降超35%", "tooltip": f"当班 CPK 相比前 3 天均值降幅达 {abs(cpk_pct_change)}%"})
                if is_cont_top23:
                    status_badges.append({"color": "orange", "text": "🟠 持续在榜", "tooltip": "近 3 天均进入负贡献榜"})
                if not status_badges:
                    status_badges.append({"color": "orange", "text": "🟠 持续在榜", "tooltip": f"近 3 天有 {days_on_board} 天在榜"})
            else:
                warning_level = "yellow"
                primary_dot = "🟡"
                if is_new_online:
                    status_badges.append({"color": "yellow", "text": "🟡 新上线", "tooltip": "该机台在观察日前 3 天无生产记录，今日新换型上线排产，处于试产磨合阶段"})
                elif days_on_board >= 2:
                    status_badges.append({"color": "yellow", "text": "🟡 持续在榜", "tooltip": f"该机台近 3 天有 {days_on_board} 天进入负向贡献监控榜（CPK 偏低拉低质量）"})
                else:
                    status_badges.append({"color": "yellow", "text": "🟡 负贡献在榜", "tooltip": "当日单机 CPK 偏低，对该规格产生负向拉低贡献，位列拉低监控榜"})

            is_tu = wc_col == "tu_first_workcenter" or mach.startswith("TU")
            is_ct = wc_col == "ct_workcenter" or mach.startswith("CU") or mach.startswith("CT")
            stage = "ct" if is_ct else "gt"

            if is_tu:
                if best_tu:
                    action_text = f"推荐机台: {best_tu}"
                    action_type = "success"
                    action_tooltip = f"该规格全量最佳路径中的标杆终检机台为 {best_tu}。建议优先导流至该机台进行终检质量把关"
                else:
                    action_text = "-"
                    action_type = "info"
                    action_tooltip = "终检 TU 设备暂无标杆机台推荐"
                can_click_recommend = False
            else:
                action_text = "查看推荐参数"
                action_type = "primary"
                action_tooltip = "点击调取并深度分析该机台/工段历史最优工艺参数组合"
                can_click_recommend = True

            valid_machines.append({
                **item,
                "warning_machine": mach,
                "warning_level": warning_level,
                "primary_dot": primary_dot,
                "cpk_pct_change": cpk_pct_change,
                "is_new_online": is_new_online,
                "rank": m_item.get("rank", 99),
                "impact_score": m_item.get("impact_score", 0.0),
                "action_text": action_text,
                "action_type": action_type,
                "action_tooltip": action_tooltip,
                "can_click_recommend": can_click_recommend,
                "recommend_stage": stage,
                "status_badges": status_badges,
                "is_gt_special": False
            })

        # 检查成型机 (GT) 专项预警
        spec_prefix8 = article10[:8] if len(article10) >= 8 else article10
        gt_sql = f"""
            SELECT DISTINCT gt_workcenter
            FROM clean_yield
            WHERE TRY_CAST(article10 AS VARCHAR) LIKE '%{spec_prefix8}%'
              AND gt_workcenter IS NOT NULL
              AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) = ?::DATE
        """
        gt_candidates = qry(gt_sql, [target_date])
        for g_row in gt_candidates:
            g_mach = g_row.get("gt_workcenter")
            if not g_mach or g_mach in seen_machines:
                continue

            hist_sql = f"""
                SELECT 
                    CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) as d,
                    COUNT(*) as cnt,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v
                FROM clean_yield
                WHERE article10 = ?
                  AND gt_workcenter = ?
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1
                ORDER BY 1
            """
            g_rows = qry(hist_sql, [article10, g_mach, d_start, target_date])
            g_t0_cpk = None
            g_prev_cpks = []
            for r in g_rows:
                d_str = str(r['d'])
                avg_v = float(r['avg_v'] or 0)
                std_v = float(r['std_v'] or 0)
                c_val = avg_v if indicator == "weight" else calc_cpk(avg_v, std_v, usl, lsl)
                if d_str == target_date:
                    g_t0_cpk = c_val
                else:
                    if c_val is not None:
                        g_prev_cpks.append(c_val)

            g_mu_3d = sum(g_prev_cpks) / len(g_prev_cpks) if g_prev_cpks else None
            g_pct_chg = None
            if g_t0_cpk is not None and g_mu_3d is not None and g_mu_3d > 0:
                g_pct_chg = round(((g_t0_cpk - g_mu_3d) / g_mu_3d) * 100, 1)

            # 成型机 CPK 骤降专项预警门槛: <= -30%
            if g_pct_chg is not None and g_pct_chg <= -30:
                is_drop_35 = g_pct_chg <= -35
                w_level = "orange" if is_drop_35 else "yellow"
                p_dot = "🟠" if is_drop_35 else "🟡"

                valid_machines.append({
                    **item,
                    "warning_machine": g_mach,
                    "warning_level": w_level,
                    "primary_dot": p_dot,
                    "cpk_pct_change": g_pct_chg,
                    "rank": 99,
                    "impact_score": 0.0,
                    "action_text": "查看推荐参数",
                    "action_type": "primary",
                    "action_tooltip": "成型机专项预警：点击调取并深度分析该机台历史最优工艺参数",
                    "can_click_recommend": True,
                    "recommend_stage": "gt",
                    "status_badges": [{
                        "color": w_level,
                        "text": "🟠 成型骤降(>35%)" if is_drop_35 else "🟡 成型专项(>30%)",
                        "tooltip": f"成型机专项预警：当班 CPK 降幅达 {abs(g_pct_chg)}%"
                    }],
                    "is_gt_special": True
                })

        if not valid_machines:
            # 兜底：若均无恶化，保留 Top 1 作为信息行
            fallback_m = top_list[0]["machine"] if top_list else "无"
            fallback_wc = top_list[0].get("workcenter_col") if top_list else ""
            fallback_is_tu = fallback_wc == "tu_first_workcenter" or fallback_m.startswith("TU")
            fallback_stage = "tu" if fallback_is_tu else ("ct" if fallback_m.startswith("CU") or fallback_m.startswith("CT") else "gt")
            fallback_act = f"推荐机台: {best_tu}" if (fallback_is_tu and best_tu) else ("查看推荐参数" if not fallback_is_tu else "-")
            valid_machines.append({
                **item,
                "warning_machine": fallback_m,
                "warning_level": "yellow",
                "primary_dot": "🟡",
                "cpk_pct_change": None,
                "action_text": fallback_act,
                "action_type": "success" if (fallback_is_tu and best_tu) else "primary",
                "action_tooltip": "质量稳定",
                "can_click_recommend": not fallback_is_tu,
                "recommend_stage": fallback_stage,
                "status_badges": [{"color": "yellow", "text": "🟡 质量在榜", "tooltip": "当日入榜机台"}],
                "is_gt_special": False
            })

        return valid_machines
    except Exception as e:
        print(f"Error getting detailed machines for {article10}: {e}")
        fallback_item = {
            **item,
            "warning_machine": "无",
            "warning_level": "none",
            "primary_dot": "",
            "cpk_pct_change": None,
            "action_text": "-",
            "action_type": "info",
            "action_tooltip": "",
            "can_click_recommend": False,
            "recommend_stage": "gt",
            "status_badges": []
        }
        return [fallback_item]


@app.get("/api/machines/process-sankey")
def get_machine_process_sankey(
    article10: str = Query(...),
    indicator: str = Query("rfpp"),
    target_date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
    tolerance: float = Query(0.8)
):
    try:
        if not isinstance(start_date, str) or start_date in ("null", "None", ""):
            start_date = None
        if not isinstance(end_date, str) or end_date in ("null", "None", ""):
            end_date = None
        if not isinstance(target_date, str) or target_date in ("null", "None", ""):
            target_date = None
        if not isinstance(indicator, str):
            indicator = "rfpp"
        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 10
        try:
            tolerance = float(tolerance)
        except Exception:
            tolerance = 0.8

        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        
        warning_machines = {}
        machine_cpk_lookup_details = {}
        if target_date:
            cpk_res = get_machines_cpk(
                target_date=target_date,
                article10=article10,
                indicator=indicator,
                start_date=start_date,
                end_date=end_date,
                min_samples=1,
                tolerance=tolerance
            )
            if cpk_res.get("status") == "success":
                cpk_data = cpk_res.get("data", {})
                for wc_label, m_list in cpk_data.items():
                    for m_info in m_list:
                        m_name = str(m_info.get("machine"))
                        col_name = str(m_info.get("workcenter_col"))
                        machine_cpk_lookup_details[(col_name, m_name)] = m_info

        # 基于方案一（全局机台贡献分析）计算决策树中最核心负面影响机台并标红
        top_warn_list = get_top_warning_machines(
            n=10,
            article10=article10,
            indicator=indicator,
            start_date=start_date,
            end_date=end_date,
            target_date=target_date,
            min_samples=min_samples
        )
        if top_warn_list:
            warning_machines[top_warn_list[0]["machine"]] = 1.0

        where_parts = ["article10 = ?"]
        params = [article10]
        if target_date:
            where_parts.append("tu_first_shift_date::DATE = ?::DATE")
            params.append(target_date)
        elif start_date and end_date:
            where_parts.append("tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE")
            params.extend([start_date, end_date])

        where_clause = "WHERE " + " AND ".join(where_parts)
        if indicator == "weight":
            where_clause += " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"
        else:
            where_clause += f" AND {ind_col} IS NOT NULL"

        # 直接根据 where_clause 查出当前日期+规格下各工段所有机台的精确 avg / std / cpk
        machine_stats_map = {}
        global_usl, global_lsl = get_spec_limits(article10, indicator)
        
        sankey_prefix_to_col = {
            "胎面": "tread_workcenter",
            "胎圈": "bead_workcenter",
            "内衬": "inner_liner_workcenter",
            "胎侧": "sidewall_workcenter",
            "带束层1": "first_breaker_workcenter",
            "带束层2": "second_breaker_workcenter",
            "帘布层1": "first_ply_workcenter",
            "冠带层1": "wound_cap_ply1_workcenter",
            "冠带层2": "wound_cap_ply2_workcenter",
            "生胎成型GT": "gt_workcenter",
            "硫化CT": "ct_workcenter",
            "终检TU": "tu_first_workcenter",
            "动平衡TB": "tb_first_workcenter"
        }
        
        for wc_col in set(sankey_prefix_to_col.values()):
            m_sql = f"""
                SELECT 
                    CAST({wc_col} AS VARCHAR) as m_code,
                    COUNT(*) as sample_n,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v
                FROM clean_yield
                {where_clause} AND {wc_col} IS NOT NULL
                GROUP BY 1
            """
            m_rows = qry(m_sql, params)
            for mr in m_rows:
                m_c = str(mr['m_code'])
                av = float(mr['avg_v']) if mr['avg_v'] is not None else 0.0
                sv = float(mr['std_v']) if mr['std_v'] is not None else 0.0
                if indicator == "weight":
                    cpk_v = av
                else:
                    cpk_v = calc_cpk(av, sv, global_usl, global_lsl)
                machine_stats_map[(wc_col, m_c)] = {
                    "spec_cpk": cpk_v,
                    "spec_std": sv,
                    "spec_avg": av
                }

        if indicator == "weight":
            tu_sql = f"""
                SELECT 
                    CAST(tu_first_workcenter AS VARCHAR) as tu_machine,
                    AVG(ABS(TRY_CAST({ind_col} AS DOUBLE))) as val_3sigma,
                    COUNT(*) as sample_n
                FROM clean_yield
                {where_clause} AND tu_first_workcenter IS NOT NULL
                GROUP BY 1
                ORDER BY val_3sigma DESC
            """
        else:
            tu_sql = f"""
                SELECT 
                    CAST(tu_first_workcenter AS VARCHAR) as tu_machine,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({ind_col} AS DOUBLE)), 0.0) as val_3sigma,
                    COUNT(*) as sample_n
                FROM clean_yield
                {where_clause} AND tu_first_workcenter IS NOT NULL
                GROUP BY 1
                ORDER BY val_3sigma DESC
            """
        tu_rows = qry(tu_sql, params)
        highest_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
        highest_tu_value = tu_rows[0]['val_3sigma'] if tu_rows else 0.0

        nodes_set = set()
        links = []

        # 顺序流转 5 列结构 (1: 热准备 -> 2: 裁断 -> 3: 成型GT -> 4: 硫化CT -> 5: 终检TU/TB)
        pairs = [
            ("tread_workcenter", "胎面", "first_breaker_workcenter", "带束层1"),
            ("tread_workcenter", "胎面", "second_breaker_workcenter", "带束层2"),
            ("inner_liner_workcenter", "内衬", "first_ply_workcenter", "帘布层1"),
            ("sidewall_workcenter", "胎侧", "wound_cap_ply1_workcenter", "冠带层1"),
            ("bead_workcenter", "胎圈", "wound_cap_ply2_workcenter", "冠带层2"),
            ("first_breaker_workcenter", "带束层1", "gt_workcenter", "生胎成型GT"),
            ("second_breaker_workcenter", "带束层2", "gt_workcenter", "生胎成型GT"),
            ("first_ply_workcenter", "帘布层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply1_workcenter", "冠带层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply2_workcenter", "冠带层2", "gt_workcenter", "生胎成型GT"),
            ("gt_workcenter", "生胎成型GT", "ct_workcenter", "硫化CT"),
            ("ct_workcenter", "硫化CT", "tu_first_workcenter", "终检TU"),
            ("tu_first_workcenter", "终检TU", "tb_first_workcenter", "动平衡TB")
        ]

        for src_col, src_prefix, dst_col, dst_prefix in pairs:
            if indicator == "weight":
                sql = f"""
                    SELECT 
                        CAST({src_col} AS VARCHAR) as src,
                        CAST({dst_col} AS VARCHAR) as dst,
                        COUNT(*) as flow_val,
                        AVG(TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) as avg_diff_abs,
                        SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as sum_act,
                        SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) as sum_tar,
                        STDDEV(((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)) as std_val
                    FROM clean_yield
                    {where_clause} AND {src_col} IS NOT NULL AND {dst_col} IS NOT NULL
                    GROUP BY 1, 2
                    HAVING COUNT(*) >= ?
                """
            else:
                sql = f"""
                    SELECT 
                        CAST({src_col} AS VARCHAR) as src,
                        CAST({dst_col} AS VARCHAR) as dst,
                        COUNT(*) as flow_val,
                        AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val,
                        STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_val
                    FROM clean_yield
                    {where_clause} AND {src_col} IS NOT NULL AND {dst_col} IS NOT NULL
                    GROUP BY 1, 2
                    HAVING COUNT(*) >= ?
                """
            l_rows = qry(sql, params + [min_samples])
            for r in l_rows:
                src_name = f"{src_prefix}_{r['src']}"
                dst_name = f"{dst_prefix}_{r['dst']}"
                nodes_set.add(src_name)
                nodes_set.add(dst_name)

                is_hl = False

                if indicator == "weight":
                    avg_diff_abs = float(r['avg_diff_abs']) if r['avg_diff_abs'] is not None else 0.0
                    sum_act = float(r['sum_act']) if r['sum_act'] is not None else 0.0
                    sum_tar = float(r['sum_tar']) if r['sum_tar'] is not None else 0.0
                    avg_diff_pct = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0

                    links.append({
                        "source": src_name,
                        "target": dst_name,
                        "value": int(r['flow_val']),
                        "avg_3sigma": round(avg_diff_pct, 2),
                        "avg_diff_abs": round(avg_diff_abs, 2),
                        "is_highlighted": is_hl
                    })
                else:
                    m_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
                    s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
                    v_3sigma = m_val + 3.0 * s_val

                    links.append({
                        "source": src_name,
                        "target": dst_name,
                        "value": int(r['flow_val']),
                        "avg_3sigma": round(v_3sigma, 2),
                        "is_highlighted": is_hl
                    })

        depth_map = {
            "胎面": 0,
            "胎圈": 0,
            "内衬": 0,
            "胎侧": 0,
            "带束层1": 1,
            "带束层2": 1,
            "帘布层1": 1,
            "冠带层1": 1,
            "冠带层2": 1,
            "生胎成型GT": 2,
            "硫化CT": 3,
            "终检TU": 4,
            "动平衡TB": 4
        }

        nodes = []
        for n in sorted(list(nodes_set)):
            prefix = n.split("_")[0]
            m_code = n.split("_")[-1]
            d_val = depth_map.get(prefix, 0)
            is_hl = False
            is_max_tu = (n == f"终检TU_{highest_tu_machine}") if highest_tu_machine else False
            is_warn = (m_code in warning_machines) and (prefix != "动平衡TB")
            w_score = warning_machines.get(m_code, 0.0)

            col_name = sankey_prefix_to_col.get(prefix)
            
            cgrs_comp = None
            if prefix in ("生胎成型GT", "硫化CT") or col_name in ("gt_workcenter", "ct_workcenter"):
                cgrs_comp = calculate_cgrs_cpk_comparison(
                    workcenter=m_code,
                    article10=article10,
                    target_date=target_date,
                    indicator=indicator,
                    limit_n=20
                )

            if indicator == "weight":
                spec_cpk = None
                spec_ratio = None
                spec_avg = None
                spec_std = None
                if col_name and (col_name, m_code) in machine_cpk_lookup_details:
                    info = machine_cpk_lookup_details[(col_name, m_code)]
                    spec_cpk = abs(info.get("spec_cpk", 0.0))
                    spec_ratio = info.get("spec_cpk", 0.0)
                    spec_avg = info.get("spec_avg", 0.0)
                    spec_std = info.get("spec_std", 0.0)
                elif col_name and (col_name, m_code) in machine_stats_map:
                    info = machine_stats_map[(col_name, m_code)]
                    spec_cpk = abs(info.get("spec_cpk", 0.0))
                    spec_ratio = info.get("spec_cpk", 0.0)
                    spec_avg = info.get("spec_avg", 0.0)
                    spec_std = info.get("spec_std", 0.0)

                nodes.append({
                    "name": n,
                    "machine_code": m_code,
                    "depth": d_val,
                    "is_highlighted": is_hl,
                    "is_max_tu": is_max_tu,
                    "is_warning_machine": is_warn,
                    "warning_score": round(w_score, 2),
                    "spec_cpk": round(spec_cpk, 2) if spec_cpk is not None else None,
                    "spec_ratio": round(spec_ratio, 2) if spec_ratio is not None else None,
                    "spec_avg": round(spec_avg, 3) if spec_avg is not None else None,
                    "spec_std": round(spec_std, 2) if spec_std is not None else None,
                    "cgrs_comparison": sanitize_data(cgrs_comp)
                })
            else:
                m_info = machine_cpk_lookup_details.get((col_name, m_code), {}) if col_name else {}
                spec_cpk = m_info.get("spec_cpk")
                spec_std = m_info.get("spec_std")
                spec_avg = m_info.get("spec_avg")
                if col_name and (col_name, m_code) in machine_stats_map:
                    fallback_st = machine_stats_map[(col_name, m_code)]
                    if spec_cpk is None:
                        spec_cpk = fallback_st.get("spec_cpk")
                    if spec_std is None:
                        spec_std = fallback_st.get("spec_std")
                    if spec_avg is None:
                        spec_avg = fallback_st.get("spec_avg")

                nodes.append({
                    "name": n,
                    "machine_code": m_code,
                    "depth": d_val,
                    "is_highlighted": is_hl,
                    "is_max_tu": is_max_tu,
                    "is_warning_machine": is_warn,
                    "warning_score": round(w_score, 2),
                    "spec_cpk": round(spec_cpk, 2) if spec_cpk is not None else None,
                    "spec_std": round(spec_std, 2) if spec_std is not None else None,
                    "spec_avg": round(spec_avg, 2) if spec_avg is not None else None,
                    "cgrs_comparison": sanitize_data(cgrs_comp)
                })

        # 统计原始排产数并得出具体为空的提示原因
        raw_count_sql = "SELECT COUNT(*) AS total_raw FROM clean_yield WHERE article10 = ?"
        raw_params = [article10]
        if target_date:
            raw_count_sql += " AND tu_first_shift_date::DATE = ?::DATE"
            raw_params.append(target_date)
        elif start_date and end_date:
            raw_count_sql += " AND tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE"
            raw_params.extend([start_date, end_date])
        if indicator == "weight":
            raw_count_sql += " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"
        else:
            raw_count_sql += f" AND {ind_col} IS NOT NULL"
        raw_res = qry(raw_count_sql, raw_params)
        total_raw_count = raw_res[0]["total_raw"] if raw_res else 0

        reason = "ok"
        empty_message = ""
        if total_raw_count == 0:
            reason = "no_production"
            date_str = f"在 {target_date}" if target_date else ""
            empty_message = f"规格 {article10} {date_str} 当日未生产排产"
        elif len(nodes) == 0:
            reason = "threshold_filtered"
            empty_message = f"规格 {article10} 当日产量较少（已排产 {total_raw_count} 条，低于样本门槛 {min_samples}），已被筛选，建议调小样本门槛"

        return {
            "status": "success",
            "data": {
                "highest_tu_machine": highest_tu_machine,
                "highest_tu_value": round(highest_tu_value, 2),
                "nodes": nodes,
                "links": links,
                "total_raw_count": total_raw_count,
                "top_warning_machines": top_warn_list,
                "reason": reason,
                "empty_message": empty_message
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


def get_best_tu_machine_for_spec(article10: str, indicator: str = "rfpp", min_samples: int = 10):
    """
    计算该规格在全量数据集下的最佳 TU (终检) 机台及指标表现 (复用全量最佳路径核心算法)
    """
    try:
        where_clause = "WHERE article10 = ?"
        params = [article10]

        if indicator == "weight":
            where_clause += " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"
            tu_sql = f"""
                SELECT 
                    CAST(tu_first_workcenter AS VARCHAR) as tu_machine,
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) as sum_act,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) as sum_tar,
                    COUNT(*) as sample_n
                FROM clean_yield
                {where_clause} AND tu_first_workcenter IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            tu_rows = qry(tu_sql, params + [min_samples])
            if not tu_rows and min_samples > 1:
                tu_rows = qry(tu_sql, params + [1])
            for r in tu_rows:
                s_act = float(r['sum_act'])
                s_tar = float(r['sum_tar'])
                r['dev'] = abs((s_act - s_tar) / s_tar * 100.0) if s_tar > 0 else 999.0
            tu_rows.sort(key=lambda x: x['dev'])
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['dev'] if tu_rows else 0.0
        elif indicator == "cony":
            ind_col = "cony_first"
            tu_sql = f"""
                SELECT 
                    CAST(tu_first_workcenter AS VARCHAR) as tu_machine,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v,
                    COUNT(*) as sample_n
                FROM clean_yield
                {where_clause} AND tu_first_workcenter IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= ?
                ORDER BY std_v ASC
            """
            tu_rows = qry(tu_sql, params + [min_samples])
            if not tu_rows and min_samples > 1:
                tu_rows = qry(tu_sql, params + [1])
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['std_v'] if tu_rows else 0.0
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            global_usl = get_spec_usl(article10, indicator)
            tu_sql = f"""
                SELECT 
                    CAST(tu_first_workcenter AS VARCHAR) as tu_machine,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v,
                    COUNT(*) as sample_n
                FROM clean_yield
                {where_clause} AND tu_first_workcenter IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            tu_rows = qry(tu_sql, params + [min_samples])
            if not tu_rows and min_samples > 1:
                tu_rows = qry(tu_sql, params + [1])
            for r in tu_rows:
                avg_v = r['avg_v'] or 0.0
                std_v = r['std_v'] or 0.0
                cpk = calc_cpk(avg_v, std_v, global_usl)
                r['cpk'] = cpk
            tu_rows.sort(key=lambda x: x['cpk'], reverse=True)
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['cpk'] if tu_rows else 0.0

        return best_tu_machine, round(best_tu_value, 2) if best_tu_value is not None else None
    except Exception as e:
        print(f"Error computing best tu machine for {article10}: {e}")
        return None, None


@app.get("/api/machines/best-process-sankey")
def get_machine_best_process_sankey(
    article10: str = Query(...),
    indicator: str = Query("rfpp"),
    min_samples: int = Query(10),
):
    try:
        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        where_clause = "WHERE article10 = ?"
        params = [article10]

        global_usl = get_spec_usl(article10, indicator)

        best_tu_machine, best_tu_value = get_best_tu_machine_for_spec(article10, indicator, min_samples)
        if best_tu_value is None:
            best_tu_value = 0.0

        best_nodes = set()
        best_links = set()

        if best_tu_machine:
            path_sql = f"""
                SELECT 
                    CAST(tread_workcenter AS VARCHAR) as tread,
                    CAST(bead_workcenter AS VARCHAR) as bead,
                    CAST(inner_liner_workcenter AS VARCHAR) as inner_liner,
                    CAST(sidewall_workcenter AS VARCHAR) as sidewall,
                    CAST(first_breaker_workcenter AS VARCHAR) as breaker1,
                    CAST(second_breaker_workcenter AS VARCHAR) as breaker2,
                    CAST(first_ply_workcenter AS VARCHAR) as ply1,
                    CAST(wound_cap_ply1_workcenter AS VARCHAR) as cap1,
                    CAST(wound_cap_ply2_workcenter AS VARCHAR) as cap2,
                    CAST(gt_workcenter AS VARCHAR) as gt,
                    CAST(ct_workcenter AS VARCHAR) as ct,
                    CAST(tu_first_workcenter AS VARCHAR) as tu,
                    CAST(tb_first_workcenter AS VARCHAR) as tb,
                    COUNT(*) as flow_cnt,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_val
                FROM clean_yield
                {where_clause} AND tu_first_workcenter = ?
                GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13
            """
            candidate_paths = qry(path_sql, params + [best_tu_machine])
            
            # 使用对数平滑综合评分 Score = Quality * ln(N + 1) 遴选最佳全流程路线
            for r in candidate_paths:
                flow_cnt = int(r['flow_cnt'])
                avg_v = float(r['avg_val']) if r['avg_val'] is not None else 0.0
                std_v = float(r['std_val']) if r['std_val'] is not None else 0.0
                
                log_v = math.log(flow_cnt + 1)
                
                if indicator == "weight":
                    dev_pct = abs(avg_v)
                    q_score = 100.0 / (dev_pct + 0.1)
                elif indicator == "cony":
                    q_score = 100.0 / (std_v + 0.01)
                else:
                    cpk_val = calc_cpk(avg_v, std_v, global_usl)
                    q_score = cpk_val
                
                r['smooth_score'] = q_score * log_v

            candidate_paths.sort(key=lambda x: x['smooth_score'], reverse=True)
            top_path_rows = candidate_paths[:1]
            if top_path_rows:
                tp = top_path_rows[0]
                node_map_path = {
                    "胎面": f"胎面_{tp['tread']}" if tp['tread'] else None,
                    "胎圈": f"胎圈_{tp['bead']}" if tp['bead'] else None,
                    "内衬": f"内衬_{tp['inner_liner']}" if tp['inner_liner'] else None,
                    "胎侧": f"胎侧_{tp['sidewall']}" if tp['sidewall'] else None,
                    "带束层1": f"带束层1_{tp['breaker1']}" if tp['breaker1'] else None,
                    "带束层2": f"带束层2_{tp['breaker2']}" if tp['breaker2'] else None,
                    "帘布层1": f"帘布层1_{tp['ply1']}" if tp['ply1'] else None,
                    "冠带层1": f"冠带层1_{tp['cap1']}" if tp['cap1'] else None,
                    "冠带层2": f"冠带层2_{tp['cap2']}" if tp['cap2'] else None,
                    "生胎成型GT": f"生胎成型GT_{tp['gt']}" if tp['gt'] else None,
                    "硫化CT": f"硫化CT_{tp['ct']}" if tp['ct'] else None,
                    "终检TU": f"终检TU_{tp['tu']}" if tp['tu'] else None,
                    "动平衡TB": f"动平衡TB_{tp['tb']}" if tp['tb'] else None
                }
                for n in node_map_path.values():
                    if n:
                        best_nodes.add(n)

                prep_cut_links = [
                    ("胎面", "带束层1"),
                    ("胎面", "带束层2"),
                    ("内衬", "帘布层1"),
                    ("胎侧", "冠带层1"),
                    ("胎圈", "冠带层2")
                ]
                for p_k, c_k in prep_cut_links:
                    if node_map_path[p_k] and node_map_path[c_k]:
                        best_links.add((node_map_path[p_k], node_map_path[c_k]))

                for c_k in ["带束层1", "带束层2", "帘布层1", "冠带层1", "冠带层2"]:
                    if node_map_path[c_k] and node_map_path["生胎成型GT"]:
                        best_links.add((node_map_path[c_k], node_map_path["生胎成型GT"]))

                chain = ["生胎成型GT", "硫化CT", "终检TU", "动平衡TB"]
                for i in range(len(chain) - 1):
                    src_k, dst_k = chain[i], chain[i+1]
                    if node_map_path[src_k] and node_map_path[dst_k]:
                        best_links.add((node_map_path[src_k], node_map_path[dst_k]))

        pairs = [
            ("tread_workcenter", "胎面", "first_breaker_workcenter", "带束层1"),
            ("tread_workcenter", "胎面", "second_breaker_workcenter", "带束层2"),
            ("inner_liner_workcenter", "内衬", "first_ply_workcenter", "帘布层1"),
            ("sidewall_workcenter", "胎侧", "wound_cap_ply1_workcenter", "冠带层1"),
            ("bead_workcenter", "胎圈", "wound_cap_ply2_workcenter", "冠带层2"),
            ("first_breaker_workcenter", "带束层1", "gt_workcenter", "生胎成型GT"),
            ("second_breaker_workcenter", "带束层2", "gt_workcenter", "生胎成型GT"),
            ("first_ply_workcenter", "帘布层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply1_workcenter", "冠带层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply2_workcenter", "冠带层2", "gt_workcenter", "生胎成型GT"),
            ("gt_workcenter", "生胎成型GT", "ct_workcenter", "硫化CT"),
            ("ct_workcenter", "硫化CT", "tu_first_workcenter", "终检TU"),
            ("tu_first_workcenter", "终检TU", "tb_first_workcenter", "动平衡TB")
        ]

        nodes_set = set()
        links = []

        for src_col, src_prefix, dst_col, dst_prefix in pairs:
            sql = f"""
                SELECT 
                    CAST({src_col} AS VARCHAR) as src,
                    CAST({dst_col} AS VARCHAR) as dst,
                    COUNT(*) as flow_val,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_val
                FROM clean_yield
                {where_clause} AND {src_col} IS NOT NULL AND {dst_col} IS NOT NULL
                GROUP BY 1, 2
                HAVING COUNT(*) >= ?
            """
            l_rows = qry(sql, params + [min_samples])
            for r in l_rows:
                src_name = f"{src_prefix}_{r['src']}"
                dst_name = f"{dst_prefix}_{r['dst']}"
                nodes_set.add(src_name)
                nodes_set.add(dst_name)

                m_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
                s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
                v_3sigma = m_val + 3.0 * s_val

                is_best = (src_name, dst_name) in best_links

                links.append({
                    "source": src_name,
                    "target": dst_name,
                    "value": int(r['flow_val']),
                    "avg_3sigma": round(v_3sigma, 2),
                    "is_best_path": is_best
                })

        sankey_col_map = {
            "胎面": "tread_workcenter",
            "胎圈": "bead_workcenter",
            "内衬": "inner_liner_workcenter",
            "胎侧": "sidewall_workcenter",
            "带束层1": "first_breaker_workcenter",
            "带束层2": "second_breaker_workcenter",
            "帘布层1": "first_ply_workcenter",
            "冠带层1": "wound_cap_ply1_workcenter",
            "冠带层2": "wound_cap_ply2_workcenter",
            "生胎成型GT": "gt_workcenter",
            "硫化CT": "ct_workcenter",
            "终检TU": "tu_first_workcenter",
            "动平衡TB": "tb_first_workcenter"
        }

        # 严格限定在当前选定规格 (article10) 下查询流过各机台的实际均值与标准差与 CPK
        node_stats = {}
        global_usl, global_lsl = get_spec_limits(article10, indicator)
        for prefix, col_name in sankey_col_map.items():
            extra_f = ""
            if indicator == "weight":
                extra_f = " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"
                avg_sql = f"""
                    SELECT 
                        CAST({col_name} AS VARCHAR) as mach,
                        AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val,
                        STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_val,
                        AVG(TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) as avg_abs
                    FROM clean_yield
                    WHERE article10 = ? AND {col_name} IS NOT NULL {extra_f}
                    GROUP BY 1
                """
                for r in qry(avg_sql, [article10]):
                    m_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
                    s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
                    abs_val = float(r['avg_abs']) if r['avg_abs'] is not None else 0.0
                    node_stats[f"{prefix}_{r['mach']}"] = {
                        "avg_val": round(abs_val, 3),
                        "ratio_val": round(m_val, 2),
                        "std_val": round(s_val, 2),
                        "cpk_val": round(m_val, 2)
                    }
            else:
                avg_sql = f"""
                    SELECT 
                        CAST({col_name} AS VARCHAR) as mach,
                        AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val,
                        STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_val
                    FROM clean_yield
                    WHERE article10 = ? AND {col_name} IS NOT NULL {extra_f}
                    GROUP BY 1
                """
                for r in qry(avg_sql, [article10]):
                    m_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
                    s_val = float(r['std_val']) if r['std_val'] is not None else 0.0
                    cpk_v = calc_cpk(m_val, s_val, global_usl, global_lsl)
                    node_stats[f"{prefix}_{r['mach']}"] = {
                        "avg_val": round(m_val, 2),
                        "std_val": round(s_val, 2),
                        "cpk_val": round(cpk_v, 2) if cpk_v is not None else None
                    }

        depth_map = {
            "胎面": 0,
            "胎圈": 0,
            "内衬": 0,
            "胎侧": 0,
            "带束层1": 1,
            "带束层2": 1,
            "帘布层1": 1,
            "冠带层1": 1,
            "冠带层2": 1,
            "生胎成型GT": 2,
            "硫化CT": 3,
            "终检TU": 4,
            "动平衡TB": 4
        }

        nodes = []
        for n in sorted(list(nodes_set)):
            prefix = n.split("_")[0]
            m_code = n.split("_")[-1]
            d_val = depth_map.get(prefix, 0)
            is_best = n in best_nodes
            is_best_tu = (n == f"终检TU_{best_tu_machine}") if best_tu_machine else False
            st = node_stats.get(n, {})

            nodes.append({
                "name": n,
                "machine_code": m_code,
                "depth": d_val,
                "is_best_path": is_best,
                "is_best_tu": is_best_tu,
                "avg_val": st.get("avg_val"),
                "std_val": st.get("std_val"),
                "cpk_val": st.get("cpk_val"),
                "ratio_val": st.get("ratio_val")
            })

        # 统计原始排产数并得出具体为空的提示原因
        raw_res = qry("SELECT COUNT(*) AS total_raw FROM clean_yield WHERE article10 = ?", [article10])
        total_raw_count = raw_res[0]["total_raw"] if raw_res else 0

        reason = "ok"
        empty_message = ""
        if total_raw_count == 0:
            reason = "no_production"
            empty_message = f"规格 {article10} 在历史周期内未生产排产"
        elif len(nodes) == 0:
            reason = "threshold_filtered"
            empty_message = f"规格 {article10} 历史总排产量较少（已排产 {total_raw_count} 条，低于样本门槛 {min_samples}），已被筛选，建议调小样本门槛"

        return {
            "status": "success",
            "data": {
                "best_tu_machine": best_tu_machine,
                "best_tu_value": round(best_tu_value, 2),
                "nodes": nodes,
                "links": links,
                "total_raw_count": total_raw_count,
                "reason": reason,
                "empty_message": empty_message
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



# ── 6.5. 选中规格关联物料批次 (Lot) 质量追溯曲线数据 (CPK & 实际值箱线图) ─────
@app.get("/api/articles/lot-cpk-trend")
def get_article_lot_cpk_trend(
    article10: str = Query(...),
    target_date: Optional[str] = Query(None),
    indicator: str = Query("rfpp"),
    component: Optional[str] = Query(None),
    time_col: Optional[str] = Query("gt_loc_timestamp"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(1)
):
    try:
        if not isinstance(indicator, str):
            indicator = "rfpp"
        if not isinstance(article10, str):
            article10 = ""
        if not isinstance(target_date, str):
            target_date = None
        if not isinstance(start_date, str):
            start_date = None
        if not isinstance(end_date, str):
            end_date = None
        if not isinstance(component, str):
            component = None
        if not isinstance(time_col, str):
            time_col = "gt_loc_timestamp"
        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 1
        if indicator == "weight":
            ind_col = "TRY_CAST(tire_weight_actual_first AS DOUBLE)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        date_col = "tu_first_shift_date"

        # 1. 确定目标日期与日期范围
        if not target_date:
            max_dt_sql = f"SELECT MAX({date_col}::DATE) as max_d FROM clean_yield WHERE article10 = ? AND {ind_col} IS NOT NULL"
            res_dt = qry(max_dt_sql, [article10])
            if res_dt and res_dt[0]['max_d']:
                target_date = str(res_dt[0]['max_d'])
            else:
                target_date = "2026-07-07"

        if not end_date:
            end_date = target_date
        if not start_date:
            start_date = target_date

        # 2. 规格 USL/LSL 计算
        if indicator == "weight":
            sql_tw = "SELECT AVG(TRY_CAST(tire_weight_target_first AS DOUBLE)) as target_w FROM clean_yield WHERE article10 = ?"
            res_tw = qry(sql_tw, [article10])
            global_usl = float(res_tw[0]['target_w']) if (res_tw and res_tw[0]['target_w'] is not None) else 12.0
            global_lsl = None
        else:
            global_usl, global_lsl = get_spec_limits(article10, indicator)

        # 3. 动态识别 clean_yield 中所有的 `*_lot` 字段与时间戳字段
        cols_info = qry("DESCRIBE SELECT * FROM clean_yield")
        col_names = [r['column_name'] for r in cols_info]

        lot_cols = [c for c in col_names if c.endswith("_lot")]
        
        # 中文标签对照表
        label_map = {
            "tread": "胎面",
            "bead": "胎圈",
            "inner_liner": "内衬",
            "sidewall": "胎侧",
            "first_ply": "帘布层1",
            "first_breaker": "带束层1",
            "second_breaker": "带束层2",
            "wound_cap_ply1": "冠带层1",
            "wound_cap_ply2": "冠带层2",
            "gt": "生胎成型GT",
            "ct": "硫化CT",
            "tu_first": "终检TU",
            "tb_first": "动平衡TB"
        }

        # 判定选中的时间戳列是否存在 (如 gt_loc_timestamp, ct_loc_timestamp 等)，若未覆盖新 parquet 则降级为 tu_first_shift_date
        target_time_col = time_col or "gt_loc_timestamp"
        if target_time_col in col_names:
            time_expr = f"TRY_CAST({target_time_col} AS TIMESTAMP)"
        else:
            time_expr = f"{date_col}::DATE"

        # 如果传入了具体的工段 (component)，仅过滤该工段对应的 lot 字段
        if component and component != "全部工段":
            matched_cols = []
            for lc in lot_cols:
                bp = lc[:-4]
                cname = label_map.get(bp, bp.upper())
                if cname == component:
                    matched_cols.append(lc)
            if matched_cols:
                lot_cols = matched_cols

        lot_data_list = []

        for lot_col in lot_cols:
            base_prefix = lot_col[:-4] # e.g. "tread"
            wc_col = f"{base_prefix}_workcenter"
            if wc_col not in col_names:
                continue

            comp_name = label_map.get(base_prefix, base_prefix.upper())

            # 查询在 [start_date, end_date] 范围内，该 article10 使用的该工段所有 Lot 批次及其 Machine & 均值极值四分位统计值
            # 按照【机台升序, 指定时间戳 (first_date) 升序】排列，确保同一机台按加工时间先后（由早到晚）呈现
            spec_sql = f"""
                SELECT 
                    CAST({wc_col} AS VARCHAR) as machine,
                    CAST({lot_col} AS VARCHAR) as lot_code,
                    COUNT(*) as spec_n,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as spec_mean,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as spec_std,
                    MIN(TRY_CAST({ind_col} AS DOUBLE)) as min_v,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY TRY_CAST({ind_col} AS DOUBLE)) as q1_v,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY TRY_CAST({ind_col} AS DOUBLE)) as q3_v,
                    MAX(TRY_CAST({ind_col} AS DOUBLE)) as max_v,
                    MIN({time_expr}) as first_date
                FROM clean_yield
                WHERE article10 = ?
                  AND {date_col}::DATE >= ?::DATE
                  AND {date_col}::DATE <= ?::DATE
                  AND {lot_col} IS NOT NULL AND CAST({lot_col} AS VARCHAR) != ''
                  AND {ind_col} IS NOT NULL
                GROUP BY 1, 2
                HAVING COUNT(*) >= ?
                ORDER BY machine ASC, first_date ASC, lot_code ASC
            """
            spec_rows = qry(spec_sql, [article10, start_date, end_date, min_samples])

            for r in spec_rows:
                m_code = str(r['machine']) if r['machine'] else "N/A"
                l_code = str(r['lot_code']) if r['lot_code'] else "N/A"

                # 检查是否需要插入切断占位点 (当工段或机台发生切换时)
                if lot_data_list and not lot_data_list[-1].get('is_break'):
                    last_item = lot_data_list[-1]
                    if last_item['component'] != comp_name or last_item['machine'] != m_code:
                        lot_data_list.append({
                            "component": last_item['component'],
                            "machine": last_item['machine'],
                            "lot": "",
                            "is_break": True,
                            "spec_n": 0,
                            "spec_cpk": None,
                            "multi_n": 0,
                            "multi_cpk": None,
                            "boxplot": None,
                            "mean_v": None,
                            "is_warning": False,
                            "building_machine": "N/A",
                            "gt_distribution": {}
                        })

                # 查询该批次在各个成型机台（gt_workcenter）中的消费占比
                dist_sql = f"""
                    SELECT 
                        CAST(gt_workcenter AS VARCHAR) as gt_mac,
                        COUNT(*) as cnt
                    FROM clean_yield
                    WHERE {lot_col} = ?
                      AND {date_col}::DATE >= ?::DATE
                      AND {date_col}::DATE <= ?::DATE
                      AND gt_workcenter IS NOT NULL
                    GROUP BY 1
                """
                dist_rows = qry(dist_sql, [l_code, start_date, end_date])
                total_cnt = sum(int(dr['cnt']) for dr in dist_rows)
                gt_dist = {}
                if total_cnt > 0:
                    for dr in dist_rows:
                        mac = str(dr['gt_mac'])
                        gt_dist[mac] = round(int(dr['cnt']) / total_cnt, 3)
                
                primary_gt = "N/A"
                if gt_dist:
                    primary_gt = max(gt_dist.keys(), key=lambda k: gt_dist[k])

                s_n = int(r['spec_n'])
                s_m = float(r['spec_mean']) if r['spec_mean'] is not None else 0.0
                s_s = float(r['spec_std']) if r['spec_std'] is not None else 0.0

                if indicator == "weight":
                    s_cpk = s_m
                else:
                    s_cpk = round(calc_cpk(s_m, s_s, global_usl, global_lsl), 2)

                min_v = round(float(r['min_v']), 2) if r['min_v'] is not None else 0.0
                mean_v = round(s_m, 2)
                q1_v = round(float(r['q1_v']), 2) if r['q1_v'] is not None else min_v
                q3_v = round(float(r['q3_v']), 2) if r['q3_v'] is not None else mean_v
                max_v = round(float(r['max_v']), 2) if r['max_v'] is not None else q3_v

                # 查询除当前选中单规格外的其它规格全加权 Lot CPK (排除 article10)
                multi_sql = f"""
                    SELECT 
                        COUNT(*) as multi_n,
                        AVG(TRY_CAST({ind_col} AS DOUBLE)) as multi_mean,
                        STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as multi_std
                    FROM clean_yield
                    WHERE {lot_col} = ?
                      AND {date_col}::DATE >= ?::DATE
                      AND {date_col}::DATE <= ?::DATE
                      AND {ind_col} IS NOT NULL
                """
                m_rows = qry(multi_sql, [l_code, start_date, end_date])
                if m_rows and m_rows[0]['multi_n']:
                    m_n = int(m_rows[0]['multi_n'])
                    m_m = float(m_rows[0]['multi_mean']) if m_rows[0]['multi_mean'] is not None else 0.0
                    m_s = float(m_rows[0]['multi_std']) if m_rows[0]['multi_std'] is not None else 0.0
                    if indicator == "weight":
                        m_cpk = m_m
                    else:
                        m_cpk = round(calc_cpk(m_m, m_s, global_usl, global_lsl), 2)
                else:
                    m_n = s_n
                    m_cpk = s_cpk

                # 判定预警条件
                if indicator == "weight":
                    is_warn = (abs(s_m - global_usl) / global_usl * 100.0) > 0.8
                else:
                    is_warn = (s_cpk < 1.33 and m_cpk < 1.33 and m_n > s_n)

                lot_data_list.append({
                    "component": comp_name,
                    "machine": m_code,
                    "lot": l_code,
                    "is_break": False,
                    "spec_n": s_n,
                    "spec_cpk": s_cpk,
                    "multi_n": m_n,
                    "multi_cpk": m_cpk,
                    "boxplot": [min_v, q1_v, mean_v, q3_v, max_v],
                    "mean_v": mean_v,
                    "is_warning": is_warn,
                    "building_machine": primary_gt,
                    "gt_distribution": gt_dist
                })

        return {
            "status": "success",
            "target_date": target_date,
            "start_date": start_date,
            "end_date": end_date,
            "article10": article10,
            "indicator": indicator,
            "time_col": target_time_col,
            "usl": round(global_usl, 2),
            "lsl": round(global_lsl, 2) if global_lsl is not None else None,
            "data": sanitize_data(lot_data_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 6.6. 选中物料批次 (Lot) 下属 Barcode 级测量实际值分布接口 ────────────────
@app.get("/api/articles/lot-barcode-detail")
def get_lot_barcode_detail(
    article10: str = Query(...),
    lot: str = Query(...),
    component: Optional[str] = Query(None),
    indicator: str = Query("rfpp")
):
    try:
        if indicator == "weight":
            ind_col = "TRY_CAST(tire_weight_actual_first AS DOUBLE)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"

        # 中文工段名称映射到数据库 _lot 字段前缀
        prefix_map = {
            "胎面": "tread",
            "胎圈": "bead",
            "内衬": "inner_liner",
            "胎侧": "sidewall",
            "帘布层1": "first_ply",
            "带束层1": "first_breaker",
            "带束层2": "second_breaker",
            "冠带层1": "wound_cap_ply1",
            "冠带层2": "wound_cap_ply2"
        }

        # 识别具体的 lot_col
        lot_col = None
        if component and component in prefix_map:
            lot_col = f"{prefix_map[component]}_lot"
        else:
            # 动态检查 clean_yield 包含的 *_lot 字段
            cols_info = qry("DESCRIBE SELECT * FROM clean_yield")
            col_names = [r['column_name'] for r in cols_info]
            lot_cols = [c for c in col_names if c.endswith("_lot")]
            
            # 找到匹配当前 lot 值的列
            for lc in lot_cols:
                check_sql = f"SELECT COUNT(*) as cnt FROM clean_yield WHERE article10 = ? AND {lc} = ?"
                c_res = qry(check_sql, [article10, lot])
                if c_res and c_res[0]['cnt'] > 0:
                    lot_col = lc
                    break

        if not lot_col:
            lot_col = "tread_lot"

        sql = f"""
            SELECT 
                CAST(barcode AS VARCHAR) as barcode,
                AVG(TRY_CAST({ind_col} AS DOUBLE)) as val,
                MAX(CAST(ct_workcenter AS VARCHAR)) as ct_workcenter,
                MAX(CAST(tu_first_workcenter AS VARCHAR)) as tu_first_workcenter,
                COUNT(*) as cnt
            FROM clean_yield
            WHERE article10 = ?
              AND {lot_col} = ?
              AND {ind_col} IS NOT NULL
              AND barcode IS NOT NULL AND CAST(barcode AS VARCHAR) != ''
            GROUP BY 1
            ORDER BY barcode ASC
        """
        rows = qry(sql, [article10, lot])

        barcode_list = []
        for r in rows:
            b_code = str(r['barcode']) if r['barcode'] else ""
            if not b_code: continue
            v = round(float(r['val']), 2) if r['val'] is not None else 0.0
            ct_wc = str(r['ct_workcenter']) if r['ct_workcenter'] else "N/A"
            tu_wc = str(r['tu_first_workcenter']) if r['tu_first_workcenter'] else "N/A"

            barcode_list.append({
                "barcode": b_code,
                "val": v,
                "ct_workcenter": ct_wc,
                "tu_workcenter": tu_wc,
                "count": int(r['cnt'])
            })

        return {
            "status": "success",
            "article10": article10,
            "lot": lot,
            "component": component,
            "indicator": indicator,
            "data": sanitize_data(barcode_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



# ── 11. 过滤选项：规格列表 ────────────────────────────────────
@app.get("/api/filters/articles")
def get_filter_articles(min_yield: int = Query(0)):
    try:
        having_clause = "HAVING COUNT(*) > ?" if min_yield else ""
        sql = f"""
            SELECT article10, COUNT(*) AS cnt
            FROM clean_yield
            GROUP BY article10
            {having_clause}
            ORDER BY cnt DESC
            LIMIT 100
        """
        params = [min_yield] if min_yield else None
        return {"status": "success", "data": qry(sql, params)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 12. 过滤选项：日期范围 ────────────────────────────────────
@app.get("/api/filters/daterange")
def get_date_range():
    try:
        sql = """
            SELECT
                MIN(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)) AS date_min,
                MAX(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)) AS date_max
            FROM clean_yield
            WHERE tu_first_loc_timestamp IS NOT NULL
        """
        row = qry(sql)[0]
        row["date_min"] = str(row["date_min"])
        row["date_max"] = str(row["date_max"])
        return {"status": "success", "data": row}
    except Exception as e:
        return {"status": "error", "message": str(e)}



# ── 13. CPK 趋势接口 ────────────────────────────────────
@app.get("/api/trend/cpk")
def get_cpk_trend(
    grain: str = Query("daily"),     # "daily" | "hourly" | "minute" | "weekly"
    article10: Optional[str] = Query(None),
    exclude_articles: Optional[str] = Query(None), # 英文逗号分割的需剔除规格代码列表
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    phase: Optional[str] = Query("all"),
    shift: Optional[str] = Query("all"),
    exclude_outliers: bool = Query(False)
):
    try:
        if not isinstance(exclude_articles, str):
            exclude_articles = None
        if not isinstance(article10, str):
            article10 = None
        if not isinstance(time_col, str):
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"

        # Select time expression
        col_ref = time_col if time_col else "tu_first_loc_timestamp"
        date_cast = f"STRFTIME(CAST((TRY_CAST({col_ref} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')"
        if grain == "daily":
            time_expr = date_cast
        elif grain == "hourly":
            time_expr = f"STRFTIME(DATE_TRUNC('hour', TRY_CAST({col_ref} AS TIMESTAMP)), '%Y-%m-%d %H:00')"
        elif grain == "minute":
            time_expr = f"STRFTIME(DATE_TRUNC('minute', TRY_CAST({col_ref} AS TIMESTAMP)), '%Y-%m-%d %H:%M')"
        elif grain == "weekly":
            time_expr = f"DATE_TRUNC('week', CAST(TRY_CAST({col_ref} AS TIMESTAMP) AS DATE))"
        else:
            time_expr = date_cast

        exclude_clause = ""
        exclude_params = []
        if exclude_articles:
            ex_list = [x.strip() for x in exclude_articles.split(",") if x.strip()]
            if ex_list:
                placeholders = ",".join(["?"] * len(ex_list))
                exclude_clause = f" AND article10 NOT IN ({placeholders})"
                exclude_params = ex_list

        time_null_clause = f"AND {build_production_time_where(col_ref, shift=shift)}"
        phase_cond = get_phase_sql_condition(phase)

        cond_rfpp = "AND b.v_rfpp <= q.up_rfpp" if exclude_outliers else ""
        cond_rfh1 = "AND b.v_rfh1 <= q.up_rfh1" if exclude_outliers else ""
        cond_cony = "AND b.v_cony <= q.up_cony" if exclude_outliers else ""
        cond_weight = "AND b.v_weight <= q.up_weight" if exclude_outliers else ""

        if article10:
            # 单规格：池化计算，直接计算均值与标准差，不区分 group，不加权；使用 CTE 计算上四分位界线异常值条数
            sql = f"""
                WITH base_filtered AS (
                    SELECT
                        {time_expr} AS time_period,
                        article10,
                        TRY_CAST(rfppwc_first AS DOUBLE) AS v_rfpp,
                        TRY_CAST(rfh1wc_first AS DOUBLE) AS v_rfh1,
                        TRY_CAST(cony_first AS DOUBLE) AS v_cony,
                        CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                        tire_weight_actual_first,
                        tire_weight_target_first,
                        conny_usl,
                        conny_lsl,
                        standard_rfpp,
                        standard_rfh1,
                        "group"
                    FROM clean_yield
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      {time_null_clause}
                      {phase_cond}
                      AND article10 = ?
                ),
                q_bounds AS (
                    SELECT
                        time_period,
                        (2.5 * QUANTILE_CONT(v_rfpp, 0.75) - 1.5 * QUANTILE_CONT(v_rfpp, 0.25)) AS up_rfpp,
                        (2.5 * QUANTILE_CONT(v_rfh1, 0.75) - 1.5 * QUANTILE_CONT(v_rfh1, 0.25)) AS up_rfh1,
                        (2.5 * QUANTILE_CONT(v_cony, 0.75) - 1.5 * QUANTILE_CONT(v_cony, 0.25)) AS up_cony,
                        (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                    FROM base_filtered
                    GROUP BY 1
                ),
                spec_daily_stats AS (
                    SELECT
                        b.time_period,
                        b.article10,
                        COUNT(CASE WHEN 1=1 {cond_rfpp} THEN 1 END) AS sample_size,
                        AVG(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS avg_rfpp,
                        STDDEV(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS std_rfpp,
                        SUM(CASE WHEN b.v_rfpp > q.up_rfpp THEN 1 ELSE 0 END) AS outliers_rfpp,
                        AVG(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS avg_rfh1,
                        STDDEV(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS std_rfh1,
                        SUM(CASE WHEN b.v_rfh1 > q.up_rfh1 THEN 1 ELSE 0 END) AS outliers_rfh1,
                        AVG(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS avg_cony,
                        STDDEV(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS std_cony,
                        SUM(CASE WHEN b.v_cony > q.up_cony THEN 1 ELSE 0 END) AS outliers_cony,
                        COALESCE(ANY_VALUE(b.conny_usl), 95.0) AS usl_cony,
                        COALESCE(ANY_VALUE(b.conny_lsl), -95.0) AS lsl_cony,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
                        STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                        SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight,
                        COALESCE(ANY_VALUE(b.standard_rfpp), 
                                 CASE ANY_VALUE(b."group") 
                                     WHEN 'GROUP 1'  THEN 10.5 
                                     WHEN 'GROUP 2A' THEN 11.5 
                                     WHEN 'GROUP 2B' THEN 12.5 
                                     WHEN 'GROUP 3'  THEN 12.5 
                                 END) * 10.0 AS usl_rfpp,
                        COALESCE(ANY_VALUE(b.standard_rfh1), 
                                 CASE ANY_VALUE(b."group") 
                                     WHEN 'GROUP 1'  THEN 7.5 
                                     WHEN 'GROUP 2A' THEN 8.5 
                                     WHEN 'GROUP 2B' THEN 9.0 
                                     WHEN 'GROUP 3'  THEN 9.5 
                                 END) * 10.0 AS usl_rfh1
                    FROM base_filtered b
                    JOIN q_bounds q ON b.time_period = q.time_period
                    GROUP BY 1, 2
                    HAVING COUNT(*) >= 10
                )
                SELECT
                    time_period,
                    sample_size AS total_n,
                    CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS weighted_cpk_rfpp,
                    avg_rfpp AS weighted_avg_rfpp,
                    std_rfpp AS weighted_std_rfpp,
                    outliers_rfpp,
                    CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS weighted_cpk_rfh1,
                    avg_rfh1 AS weighted_avg_rfh1,
                    std_rfh1 AS weighted_std_rfh1,
                    outliers_rfh1,
                    CASE WHEN std_cony > 1e-6 THEN LEAST((usl_cony - avg_cony) / (3.0 * std_cony), (avg_cony - lsl_cony) / (3.0 * std_cony)) ELSE NULL END AS weighted_cpk_cony,
                    avg_cony AS weighted_avg_cony,
                    std_cony AS weighted_std_cony,
                    outliers_cony,
                    (sum_act_w - sum_tar_w) / NULLIF(sum_tar_w, 0.0) * 100.0 as weighted_diff_weight,
                    std_w AS weighted_std_weight,
                    outliers_weight
                FROM spec_daily_stats
                ORDER BY 1
            """
            params = [article10]
        else:
            # 全厂综合：各规格按生产组别计算独立 CPK，然后通过日产量加权平均；基于全厂样本计算当天的 IQR 异常值
            sql = f"""
                WITH base_filtered AS (
                    SELECT
                        {time_expr} AS time_period,
                        "group",
                        article10,
                        TRY_CAST(rfppwc_first AS DOUBLE) AS v_rfpp,
                        TRY_CAST(rfh1wc_first AS DOUBLE) AS v_rfh1,
                        TRY_CAST(cony_first AS DOUBLE) AS v_cony,
                        CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                        tire_weight_actual_first,
                        tire_weight_target_first,
                        conny_usl,
                        conny_lsl,
                        standard_rfpp,
                        standard_rfh1
                    FROM clean_yield
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      {time_null_clause}
                      {phase_cond}
                      {exclude_clause}
                ),
                q_bounds AS (
                    SELECT
                        time_period,
                        (2.5 * QUANTILE_CONT(v_rfpp, 0.75) - 1.5 * QUANTILE_CONT(v_rfpp, 0.25)) AS up_rfpp,
                        (2.5 * QUANTILE_CONT(v_rfh1, 0.75) - 1.5 * QUANTILE_CONT(v_rfh1, 0.25)) AS up_rfh1,
                        (2.5 * QUANTILE_CONT(v_cony, 0.75) - 1.5 * QUANTILE_CONT(v_cony, 0.25)) AS up_cony,
                        (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                    FROM base_filtered
                    GROUP BY 1
                ),
                spec_daily_stats AS (
                    SELECT
                        b.time_period,
                        b."group",
                        b.article10,
                        COUNT(CASE WHEN 1=1 {cond_rfpp} THEN 1 END) AS sample_size,
                        AVG(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS avg_rfpp,
                        STDDEV(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS std_rfpp,
                        SUM(CASE WHEN b.v_rfpp > q.up_rfpp THEN 1 ELSE 0 END) AS outliers_rfpp,
                        AVG(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS avg_rfh1,
                        STDDEV(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS std_rfh1,
                        SUM(CASE WHEN b.v_rfh1 > q.up_rfh1 THEN 1 ELSE 0 END) AS outliers_rfh1,
                        AVG(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS avg_cony,
                        STDDEV(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS std_cony,
                        SUM(CASE WHEN b.v_cony > q.up_cony THEN 1 ELSE 0 END) AS outliers_cony,
                        COALESCE(ANY_VALUE(b.conny_usl), 95.0) AS usl_cony,
                        COALESCE(ANY_VALUE(b.conny_lsl), -95.0) AS lsl_cony,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
                        STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                        SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight,
                        COALESCE(ANY_VALUE(b.standard_rfpp), 
                                 CASE b."group" 
                                     WHEN 'GROUP 1'  THEN 10.5 
                                     WHEN 'GROUP 2A' THEN 11.5 
                                     WHEN 'GROUP 2B' THEN 12.5 
                                     WHEN 'GROUP 3'  THEN 12.5 
                                 END) * 10.0 AS usl_rfpp,
                        COALESCE(ANY_VALUE(b.standard_rfh1), 
                                 CASE b."group" 
                                     WHEN 'GROUP 1'  THEN 7.5 
                                     WHEN 'GROUP 2A' THEN 8.5 
                                     WHEN 'GROUP 2B' THEN 9.0 
                                     WHEN 'GROUP 3'  THEN 9.5 
                                 END) * 10.0 AS usl_rfh1
                    FROM base_filtered b
                    JOIN q_bounds q ON b.time_period = q.time_period
                    GROUP BY 1, 2, 3
                    HAVING COUNT(*) >= 10
                ),
                spec_cpk AS (
                    SELECT
                        time_period,
                        sample_size,
                        CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp,
                        avg_rfpp,
                        std_rfpp,
                        outliers_rfpp,
                        CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS cpk_rfh1,
                        avg_rfh1,
                        std_rfh1,
                        outliers_rfh1,
                        CASE WHEN std_cony > 1e-6 THEN LEAST((usl_cony - avg_cony) / (3.0 * std_cony), (avg_cony - lsl_cony) / (3.0 * std_cony)) ELSE NULL END AS cpk_cony,
                        avg_cony,
                        std_cony,
                        outliers_cony,
                        sum_act_w,
                        sum_tar_w,
                        std_w,
                        outliers_weight
                    FROM spec_daily_stats
                )
                SELECT
                    time_period,
                    SUM(sample_size) AS total_n,
                    SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfpp,
                    SUM(avg_rfpp * sample_size) / NULLIF(SUM(CASE WHEN avg_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_avg_rfpp,
                    SQRT(SUM(POWER(COALESCE(std_rfpp, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_rfpp,
                    SUM(outliers_rfpp) AS outliers_rfpp,
                    SUM(cpk_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfh1,
                    SUM(avg_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN avg_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_avg_rfh1,
                    SQRT(SUM(POWER(COALESCE(std_rfh1, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_rfh1,
                    SUM(outliers_rfh1) AS outliers_rfh1,
                    SUM(cpk_cony * sample_size) / NULLIF(SUM(CASE WHEN cpk_cony IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_cony,
                    SUM(avg_cony * sample_size) / SUM(sample_size) AS weighted_avg_cony,
                    SQRT(SUM(POWER(COALESCE(std_cony, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_cony IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_cony,
                    SUM(outliers_cony) AS outliers_cony,
                    (SUM(sum_act_w) - SUM(sum_tar_w)) / NULLIF(SUM(sum_tar_w), 0.0) * 100.0 as weighted_diff_weight,
                    SQRT(SUM(POWER(COALESCE(std_w, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_w IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_weight,
                    SUM(outliers_weight) AS outliers_weight
                FROM spec_cpk
                GROUP BY 1
                ORDER BY 1
            """
            params = exclude_params
        rows = qry(sql, params)

        periods = sorted(list(set(str(r['time_period']) for r in rows)))
        period_idx = {p: i for i, p in enumerate(periods)}

        cpk_trends = {
            "RFPP 综合 CPK": [None] * len(periods),
            "RFH1 综合 CPK": [None] * len(periods)
        }
        stats_by_date = {}

        for r in rows:
            p_str = str(r['time_period'])
            idx = period_idx[p_str]

            total_n = int(r['total_n']) if r.get('total_n') is not None else 0
            cpk_rfpp = r['weighted_cpk_rfpp']
            avg_rfpp = r.get('weighted_avg_rfpp')
            std_rfpp = r.get('weighted_std_rfpp')
            outliers_rfpp = int(r['outliers_rfpp']) if r.get('outliers_rfpp') is not None else None

            cpk_rfh1 = r['weighted_cpk_rfh1']
            avg_rfh1 = r.get('weighted_avg_rfh1')
            std_rfh1 = r.get('weighted_std_rfh1')
            outliers_rfh1 = int(r['outliers_rfh1']) if r.get('outliers_rfh1') is not None else None

            cpk_cony = r.get('weighted_cpk_cony')
            avg_cony = r['weighted_avg_cony']
            std_cony = r.get('weighted_std_cony')
            outliers_cony = int(r['outliers_cony']) if r.get('outliers_cony') is not None else None

            avg_weight = r['weighted_diff_weight']
            std_weight = r.get('weighted_std_weight')
            outliers_weight = int(r['outliers_weight']) if r.get('outliers_weight') is not None else None

            p_stats = {
                "total_n": total_n,
                "rfpp": {
                    "cpk": round(float(cpk_rfpp), 4) if cpk_rfpp is not None and not (np.isnan(cpk_rfpp) or np.isinf(cpk_rfpp)) else None,
                    "mean": round(float(avg_rfpp), 3) if avg_rfpp is not None and not (np.isnan(avg_rfpp) or np.isinf(avg_rfpp)) else None,
                    "std": round(float(std_rfpp), 3) if std_rfpp is not None and not (np.isnan(std_rfpp) or np.isinf(std_rfpp)) else None,
                    "outliers": outliers_rfpp
                },
                "rfh1": {
                    "cpk": round(float(cpk_rfh1), 4) if cpk_rfh1 is not None and not (np.isnan(cpk_rfh1) or np.isinf(cpk_rfh1)) else None,
                    "mean": round(float(avg_rfh1), 3) if avg_rfh1 is not None and not (np.isnan(avg_rfh1) or np.isinf(avg_rfh1)) else None,
                    "std": round(float(std_rfh1), 3) if std_rfh1 is not None and not (np.isnan(std_rfh1) or np.isinf(std_rfh1)) else None,
                    "outliers": outliers_rfh1
                },
                "cony": {
                    "cpk": round(float(cpk_cony), 4) if cpk_cony is not None and not (np.isnan(cpk_cony) or np.isinf(cpk_cony)) else None,
                    "mean": round(float(avg_cony), 3) if avg_cony is not None and not (np.isnan(avg_cony) or np.isinf(avg_cony)) else None,
                    "std": round(float(std_cony), 3) if std_cony is not None and not (np.isnan(std_cony) or np.isinf(std_cony)) else None,
                    "outliers": outliers_cony
                },
                "weight": {
                    "cpk": round(float(avg_weight), 4) if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)) else None,
                    "mean": round(float(avg_weight), 3) if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)) else None,
                    "std": round(float(std_weight), 3) if std_weight is not None and not (np.isnan(std_weight) or np.isinf(std_weight)) else None,
                    "outliers": outliers_weight
                }
            }
            stats_by_date[p_str] = p_stats

            if cpk_rfpp is not None and not (np.isnan(cpk_rfpp) or np.isinf(cpk_rfpp)):
                cpk_trends["RFPP 综合 CPK"][idx] = round(float(cpk_rfpp), 4)
            if cpk_rfh1 is not None and not (np.isnan(cpk_rfh1) or np.isinf(cpk_rfh1)):
                cpk_trends["RFH1 综合 CPK"][idx] = round(float(cpk_rfh1), 4)
            if cpk_cony is not None and not (np.isnan(cpk_cony) or np.isinf(cpk_cony)):
                cpk_trends["CONY 综合 CPK"] = cpk_trends.get("CONY 综合 CPK", [None] * len(periods))
                cpk_trends["CONY 综合 CPK"][idx] = round(float(cpk_cony), 4)
            if avg_cony is not None and not (np.isnan(avg_cony) or np.isinf(avg_cony)):
                cpk_trends["CONY 综合 实际值"] = cpk_trends.get("CONY 综合 实际值", [None] * len(periods))
                cpk_trends["CONY 综合 实际值"][idx] = round(float(avg_cony), 4)
            if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)):
                cpk_trends["胎重 综合 偏差"] = cpk_trends.get("胎重 综合 偏差", [None] * len(periods))
                cpk_trends["胎重 综合 偏差"][idx] = round(float(avg_weight), 4)

        return {
            "status": "success",
            "data": {
                "dates": periods,
                "cpk_trends": cpk_trends,
                "stats_by_date": stats_by_date
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 14. CGRS 历史参数推荐接口 ────────────────────────────────────

# 简单的 TTL 内存缓存（不依赖第三方库）
import time as _time
_param_recommend_cache: dict = {}
_RECOMMEND_CACHE_TTL = 600  # 10 分钟

def _recommend_cache_key(article: str, indicator: str, target_date: str) -> str:
    return f"{article}|{indicator}|{target_date}"

def _recommend_cache_get(key: str):
    entry = _param_recommend_cache.get(key)
    if entry and (_time.time() - entry['ts'] < _RECOMMEND_CACHE_TTL):
        return entry['data']
    return None

def _recommend_cache_set(key: str, data):
    _param_recommend_cache[key] = {'ts': _time.time(), 'data': data}


@app.get("/api/cgrs/param-recommendation")
def get_param_recommendation(
    article: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    target_date: Optional[str] = Query(None, description="target date YYYY-MM-DD")
):
    """
    Search best parameter recommendation in past 30 days for GT and CU stages.
    """
    try:
        if hasattr(target_date, "default") or not isinstance(target_date, str):
            target_date = None

        max_d_res = qry("SELECT MAX(tu_first_shift_date::DATE) as max_d FROM clean_yield")[0]
        max_d_str = str(max_d_res['max_d']) if max_d_res and max_d_res.get('max_d') else datetime.now().strftime("%Y-%m-%d")

        if not target_date or target_date > max_d_str:
            target_date = max_d_str

        cache_key = _recommend_cache_key(article, indicator, target_date)
        cached = _recommend_cache_get(cache_key)
        if cached is not None:
            return cached

        gt_machines = _get_same_section_machines(article, target_date, days=30, section="gt")
        gt_event, gt_scanned = _find_best_event_for_machines(gt_machines, target_date, article, indicator)

        cu_machines = _get_same_section_machines(article, target_date, days=30, section="cu")
        cu_event, cu_scanned = _find_best_event_for_machines(cu_machines, target_date, article, indicator)

        has_rec = (gt_event is not None) or (cu_event is not None)

        result = {
            "status": "success",
            "has_recommendation": has_rec,
            "message": "参数推荐检索完成" if has_rec else "近 30 天同规格暂无符合条件的正向调控记录",
            "recommendation": sanitize_data(gt_event or cu_event),
            "gt_recommendation": sanitize_data(gt_event),
            "cu_recommendation": sanitize_data(cu_event),
            "scanned_gt_machines": len(gt_machines),
            "scanned_cu_machines": len(cu_machines),
            "scanned_events": gt_scanned + cu_scanned,
            "target_date": target_date
        }

        _recommend_cache_set(cache_key, result)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e), "has_recommendation": False}


@app.get("/api/machines/top-warning")
def get_top_warning_api(
    spec: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    target_date: str = Query(..., description="target date YYYY-MM-DD"),
    n: int = Query(3, description="Top N count"),
    days: int = Query(3, description="days window"),
    min_samples: int = Query(1, description="min samples threshold"),
):
    """
    Return Top N negative contribution machines for target_date.
    """
    try:
        if not isinstance(target_date, str) or target_date in ("null", "None", ""):
            return {"status": "error", "message": "target_date 必填"}
        try:
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        except Exception:
            return {"status": "error", "message": "target_date 格式错误，需为 YYYY-MM-DD"}

        result = {}
        for i in range(days):
            d = (target_dt - timedelta(days=i)).strftime("%Y-%m-%d")
            top_list = get_top_warning_machines(
                n=n,
                article10=spec,
                indicator=indicator,
                target_date=d,
                min_samples=min_samples,
                include_tu=True,
            )
            result[d] = top_list

        best_tu_mach, best_tu_val = get_best_tu_machine_for_spec(spec, indicator, min_samples=min_samples)

        return {
            "status": "success",
            "data": result,
            "target_date": target_date,
            "best_tu_machine": best_tu_mach,
            "best_tu_value": best_tu_val
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/api/machines/best-tu")
def get_best_tu_api(
    article10: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    min_samples: int = Query(10, description="min samples threshold"),
):
    best_tu_mach, best_val = get_best_tu_machine_for_spec(article10, indicator, min_samples)
    return {
        "status": "success",
        "data": {
            "best_tu_machine": best_tu_mach,
            "best_tu_value": best_val,
        }
    }


@app.get("/api/machines/cpk-trend-comparison")
def get_machine_cpk_trend_comparison(
    workcenter_type: str = Query("gt", description="机台工段类型：'gt' 或 'ct'/'cu'"),
    machines: str = Query(..., description="机台编号列表，逗号分隔，如 TB285,TB286"),
    article10: str = Query(..., description="当前选中规格代码 article10"),
    indicator: str = Query("rfpp", description="质量指标，如 rfpp, rfh1, cony, weight"),
    target_date: Optional[str] = Query(None, description="基准日期 YYYY-MM-DD，默认最新日期"),
    days: int = Query(14, description="对比天数，默认 14 天"),
    min_samples: int = Query(3, description="单日最低样本数门槛")
):
    """
    CPK trend comparison endpoint for machines.
    """
    try:
        if hasattr(days, "default"):
            days = 14
        try:
            days = int(days)
        except Exception:
            days = 14
            
        if hasattr(min_samples, "default"):
            min_samples = 3
        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 3

        if hasattr(target_date, "default") or not isinstance(target_date, str) or target_date in ("null", "None", ""):
            target_date = None

        max_d_res = qry("SELECT MAX(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)) as max_d FROM clean_yield")[0]
        max_d_str = str(max_d_res['max_d']) if max_d_res and max_d_res.get('max_d') else datetime.now().strftime("%Y-%m-%d")

        if not target_date or target_date > max_d_str:
            target_date = max_d_str

        # 生成过去 14 天包含 target_date 的日期列表
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        date_objs = [target_dt - timedelta(days=i) for i in range(days - 1, -1, -1)]
        date_strs = [d.strftime("%Y-%m-%d") for d in date_objs]
        start_date = date_strs[0]
        end_date = date_strs[-1]

        wc_type_clean = str(workcenter_type).strip().lower()
        if wc_type_clean in ("ct", "cu", "curing"):
            wc_col = "ct_workcenter"
        else:
            wc_col = "gt_workcenter"

        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
            usl, lsl = None, None
        elif indicator == "cony":
            ind_col = "TRY_CAST(cony_first AS DOUBLE)"
            usl, lsl = get_spec_limits(article10, indicator) if article10 else (100.0, None)
        else:
            col_field = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            ind_col = f"TRY_CAST({col_field} AS DOUBLE)"
            usl, lsl = get_spec_limits(article10, indicator) if article10 else (100.0, None)

        mach_list = [m.strip().upper() for m in str(machines).split(",") if m.strip()]
        
        # 支持自动发现全量 GT 成型机台
        if any("ALL" in m for m in mach_list):
            spec_prefix8 = article10[:8] if len(article10) >= 8 else article10
            gt_sql = f"""
                SELECT DISTINCT gt_workcenter
                FROM clean_yield
                WHERE TRY_CAST(article10 AS VARCHAR) LIKE '%{spec_prefix8}%'
                  AND gt_workcenter IS NOT NULL
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
            """
            gt_rows = qry(gt_sql, [start_date, end_date])
            discovered = [f"GT:{r['gt_workcenter']}" for r in gt_rows if r.get('gt_workcenter')]
            explicit_machs = [m for m in mach_list if "ALL" not in m]
            mach_list = list(dict.fromkeys(explicit_machs + discovered))

        mach_list = list(dict.fromkeys(mach_list)) # 去重

        machines_data = []

        for item in mach_list:
            if ":" in item:
                wtype_part, mach = item.split(":", 1)
                wtype_part = wtype_part.strip().lower()
                mach = mach.strip()
            else:
                mach = item.strip()
                if mach.startswith("CU") or mach.startswith("CT"):
                    wtype_part = "ct"
                elif mach.startswith("TU"):
                    wtype_part = "tu"
                elif mach.startswith("TB"):
                    wtype_part = "tb"
                else:
                    wtype_part = "gt"

            if wtype_part in ("ct", "cu", "curing"):
                wc_col = "ct_workcenter"
                stage_label = "硫化 (CT)"
                workcenter_type_val = "ct"
            elif wtype_part in ("tu", "tu_first"):
                wc_col = "tu_first_workcenter"
                stage_label = "终检 (TU)"
                workcenter_type_val = "tu"
            elif wtype_part in ("tb", "tb_first"):
                wc_col = "tb_first_workcenter"
                stage_label = "动平衡 (TB)"
                workcenter_type_val = "tb"
            else:
                wc_col = "gt_workcenter"
                stage_label = "成型 (GT)"
                workcenter_type_val = "gt"

            # 1. 查询该机台单规格在过去 14 天的日统计
            single_sql = f"""
                SELECT 
                    STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d') as d,
                    COUNT(*) as n,
                    AVG({ind_col}) as avg_v,
                    STDDEV({ind_col}) as std_v
                FROM clean_yield
                WHERE {wc_col} = ?
                  AND article10 = ?
                  AND {ind_col} IS NOT NULL
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1
            """
            single_rows = qry(single_sql, [mach, article10, start_date, end_date])
            single_map = {r['d']: r for r in single_rows}

            # 2. 查询该机台多规格 (全规格) 在过去 14 天的日统计
            all_sql = f"""
                SELECT 
                    STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d') as d,
                    "group",
                    article10 as spec,
                    COUNT(*) as n,
                    AVG({ind_col}) as avg_v,
                    STDDEV({ind_col}) as std_v
                FROM clean_yield
                WHERE {wc_col} = ?
                  AND {ind_col} IS NOT NULL
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1, 2, 3
            """
            all_rows = qry(all_sql, [mach, start_date, end_date])
            
            # 按日期归组多规格子数据
            all_map = {}
            for r in all_rows:
                d_key = r['d']
                if d_key not in all_map:
                    all_map[d_key] = []
                all_map[d_key].append(r)

            single_cpk_series = []
            single_n_series = []
            all_cpk_series = []
            all_n_series = []

            for d_str in date_strs:
                # 单规格计算
                s_item = single_map.get(d_str)
                if s_item and s_item['n'] >= min_samples:
                    n_val = s_item['n']
                    m_v = float(s_item['avg_v']) if s_item['avg_v'] is not None else 0.0
                    s_v = float(s_item['std_v']) if s_item['std_v'] is not None else 0.0
                    if indicator == "weight":
                        cpk_val = round(m_v, 2)
                    else:
                        c_v = calc_cpk(m_v, s_v, usl, lsl)
                        cpk_val = round(c_v, 2) if c_v is not None else None
                    single_cpk_series.append(cpk_val)
                    single_n_series.append(n_val)
                else:
                    single_cpk_series.append(None)
                    single_n_series.append(s_item['n'] if s_item else 0)

                # 全规格 (多规格) 加权计算
                a_list = all_map.get(d_str, [])
                tot_n = sum(r['n'] for r in a_list)
                if tot_n >= min_samples:
                    # 使用多规格加权 CPK / 均值
                    if indicator == "weight":
                        # 权重加权平均偏差
                        weighted_avg = sum(float(r['avg_v'] or 0.0) * r['n'] for r in a_list) / tot_n
                        all_cpk_series.append(round(weighted_avg, 2))
                    else:
                        # 按组别求解每个 spec/group 的 CPK 后加权
                        spec_cpks = []
                        for r in a_list:
                            rm_v = float(r['avg_v'] or 0.0)
                            rs_v = float(r['std_v'] or 0.0)
                            rcpk = calc_cpk(rm_v, rs_v, usl, lsl)
                            if rcpk is not None:
                                spec_cpks.append((rcpk, r['n']))
                        if spec_cpks:
                            w_cpk = sum(c * n for c, n in spec_cpks) / sum(n for c, n in spec_cpks)
                            all_cpk_series.append(round(w_cpk, 2))
                        else:
                            all_cpk_series.append(None)
                    all_n_series.append(tot_n)
                else:
                    all_cpk_series.append(None)
                    all_n_series.append(tot_n)

            # 3. 查询该机台在 cgrs_records 表中的参数修改调参记录 (仅限当前选中规格 article10，按班次日期)
            cgrs_candidates = [mach]
            if mach.startswith("TB2"):
                cgrs_candidates.append(f"TB1{mach[3:]}")
            elif mach.startswith("TB1"):
                cgrs_candidates.append(f"TB2{mach[3:]}")
            elif mach.startswith("CU") and not mach.startswith("CUG"):
                cgrs_candidates.append(f"CUG{mach[2:]}")
            elif mach.startswith("CUG"):
                cgrs_candidates.append(f"CU{mach[3:]}")

            cands_in = "', '".join(cgrs_candidates)
            spec_prefix7 = article10[:7] if len(article10) >= 7 else article10
            tuning_map = {}
            try:
                if mach.startswith("CU"):
                    cgrs_spec_filter = ""
                    cgrs_sql_params = [start_date, end_date]
                else:
                    cgrs_spec_filter = f"AND (ProdSpecific2 = ? OR ProdSpecific2 LIKE '{spec_prefix7}%' OR ProdSpecific1 = ? OR ProdSpecific1 LIKE '{spec_prefix7}%')"
                    cgrs_sql_params = [article10, article10, start_date, end_date]

                cgrs_sql = f"""
                    SELECT 
                        STRFTIME(TRY_CAST(event_timestamp AS DATE), '%Y-%m-%d') as d,
                        COUNT(*) as cnt
                    FROM cgrs_records
                    WHERE Workcenter IN ('{cands_in}')
                      {cgrs_spec_filter}
                      AND TRY_CAST(event_timestamp AS DATE) BETWEEN ?::DATE AND ?::DATE
                    GROUP BY 1
                """
                cgrs_rows = qry(cgrs_sql, cgrs_sql_params)
                tuning_map = {r['d']: int(r['cnt']) for r in cgrs_rows if r.get('d')}
            except Exception:
                pass

            tuning_counts_series = [tuning_map.get(d_str, 0) for d_str in date_strs]
            has_tuning_series = [tuning_map.get(d_str, 0) > 0 for d_str in date_strs]

            # 4. 计算过去 3 天历史基准期 (indices 10..12, 即 T-3 ~ T-1) 在当前限定规格上的基准 CPK 与产量
            base_3d_single_n = sum(single_n_series[10:13]) if len(single_n_series) >= 13 else sum(single_n_series)
            t0_single_n = single_n_series[-1] if single_n_series else 0

            single_cpks_3d = [single_cpk_series[i] for i in range(10, 13) if single_cpk_series[i] is not None]
            
            # 严格基于当前规格：只有过去 3 天在本规格上有实际产出 (base_3d_single_n > 0 且存在有效 CPK) 时，才计算 mu_base_3d
            if base_3d_single_n > 0 and single_cpks_3d:
                mu_base_3d = round(sum(single_cpks_3d) / len(single_cpks_3d), 2)
            else:
                mu_base_3d = None

            # 计算观察期当天 (index 13) 在当前规格上的 CPK
            t0_single_cpk = single_cpk_series[-1] if single_cpk_series else None
            
            if t0_single_cpk is not None and mu_base_3d is not None:
                net_delta = round(t0_single_cpk - mu_base_3d, 2)
                is_deg_warn = (net_delta < 0.0)
            else:
                net_delta = None
                is_deg_warn = False

            t0_tuning_cnt = tuning_counts_series[-1] if tuning_counts_series else 0
            base_3d_tuning_cnt = sum(tuning_counts_series[10:13]) if len(tuning_counts_series) >= 13 else 0

            # 3.5 计算观察期 target_date 当天终检测量的轮胎是否实际受 CGRS 调参影响 (物理因果时序匹配)
            cgrs_comp = calculate_cgrs_cpk_comparison(
                workcenter=mach,
                article10=article10,
                target_date=target_date,
                indicator=indicator,
                limit_n=20
            )
            t0_affected_tuning_cnt = cgrs_comp.get("events_count", 0) if (cgrs_comp and cgrs_comp.get("has_cgrs")) else 0

            machines_data.append({
                "machine": mach,
                "workcenter_type": workcenter_type_val,
                "stage_label": stage_label,
                "dates": date_strs,
                "single_spec_cpk": single_cpk_series,
                "all_spec_cpk": all_cpk_series,
                "single_spec_n": single_n_series,
                "all_spec_n": all_n_series,
                "tuning_counts": tuning_counts_series,
                "has_tuning": has_tuning_series,
                "total_14d_tunings": sum(tuning_counts_series),
                "t0_tuning_cnt": t0_tuning_cnt,
                "t0_affected_tuning_cnt": t0_affected_tuning_cnt,
                "cgrs_comparison": sanitize_data(cgrs_comp),
                "base_3d_tuning_cnt": base_3d_tuning_cnt,
                "latest_single_cpk": t0_single_cpk,
                "latest_all_cpk": all_cpk_series[-1] if all_cpk_series else None,
                "total_14d_tires": sum(all_n_series),
                "t0_n": t0_single_n,
                "base_3d_n": base_3d_single_n,
                "mu_base_3d": mu_base_3d,
                "is_degradation_warning": is_deg_warn,
                "net_delta": net_delta
            })

        return {
            "status": "success",
            "workcenter_type": wc_type_clean,
            "article10": article10,
            "target_date": target_date,
            "indicator": indicator,
            "machines_data": machines_data
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e), "machines_data": []}


@app.get("/api/cgrs/recommended-params")
def get_cgrs_recommended_params(
    machine: str = Query(..., description="机台编号，如 TB262 或 CUM03"),
    article10: str = Query(..., description="10位轮胎规格，如 0315567079"),
    workcenter_type: str = Query("gt", description="工段类型: gt 或 ct"),
    indicator: str = Query("rfpp", description="指标"),
    target_date: Optional[str] = Query(None, description="观察基准日期，如 2026-08-17"),
    reason: str = Query("degradation", description="推荐原因: degradation 或 new_machine")
):
    try:
        ref_date = target_date.strip() if target_date and target_date.strip() else datetime.now().strftime('%Y-%m-%d')
        spec_prefix7 = article10[:7] if len(article10) >= 7 else article10

        is_cu = machine.startswith("CU") or machine.startswith("CT") or workcenter_type.lower() in ("ct", "cu")
        
        # 严格限制工段隔绝，绝对不跨工段 (硫化只用硫化机参数，成型只用成型机参数)
        if is_cu:
            clean_wc_col = "ct_workcenter"
            clean_time_col = "ct_loc_timestamp"
            stage_name_cn = "硫化 CT"
        else:
            stage_wc_cond = "(Workcenter LIKE 'TB%' OR Workcenter LIKE 'GT%')"
            clean_wc_col = "gt_workcenter"
            clean_time_col = "gt_loc_timestamp"
            stage_name_cn = "成型 GT"
            # 成型机在 cgrs_records 中通过 ProdSpecific2 绑定规格 (只匹配全规格或前 7 位，完全不进行前 5 位模糊匹配)
            spec_cond_cgrs_p7 = f"(ProdSpecific2 = '{article10}' OR ProdSpecific2 LIKE '{spec_prefix7}%')"

        col_field = "rfppwc_first" if indicator == "rfpp" else ("rfh1wc_first" if indicator == "rfh1" else "cony_first")
        ind_col = f"TRY_CAST({col_field} AS DOUBLE)"
        usl, lsl = get_spec_limits(article10, indicator) if article10 else (100.0, None)

        candidates = [machine]
        if machine.startswith("TB2"):
            candidates.append(f"TB1{machine[3:]}")
        elif machine.startswith("TB1"):
            candidates.append(f"TB2{machine[3:]}")
        elif machine.startswith("CU") and not machine.startswith("CUG"):
            candidates.append(f"CUG{machine[2:]}")
        elif machine.startswith("CUG"):
            candidates.append(f"CU{machine[3:]}")
        cands_in = "', '".join(candidates)

        def eval_event_improvement(wc, ev_time_str):
            wc_cands = [wc]
            if wc.startswith("TB2"):
                wc_cands.append(f"TB1{wc[3:]}")
                wc_cands.append(f"TB{wc[3:]}")
            elif wc.startswith("TB1"):
                wc_cands.append(f"TB2{wc[3:]}")
                wc_cands.append(f"TB{wc[3:]}")
            elif wc.startswith("CU") and not wc.startswith("CUG"):
                wc_cands.append(f"CUG{wc[2:]}")
            elif wc.startswith("CUG"):
                wc_cands.append(f"CU{wc[3:]}")
            wc_in = "', '".join(wc_cands)

            spec_cond = f"AND article10 LIKE '{spec_prefix7}%'"

            sql_b = f"""
                SELECT {ind_col} as val
                FROM clean_yield
                WHERE {clean_wc_col} IN ('{wc_in}')
                  {spec_cond}
                  AND TRY_CAST({clean_time_col} AS TIMESTAMP) < '{ev_time_str}'::TIMESTAMP
                ORDER BY {clean_time_col} DESC
                LIMIT 50
            """
            vals_b = [float(x['val']) for x in qry(sql_b) if x.get('val') is not None]

            sql_a = f"""
                SELECT {ind_col} as val
                FROM clean_yield
                WHERE {clean_wc_col} IN ('{wc_in}')
                  {spec_cond}
                  AND TRY_CAST({clean_time_col} AS TIMESTAMP) >= '{ev_time_str}'::TIMESTAMP
                  AND TRY_CAST({clean_time_col} AS TIMESTAMP) <= '{ref_date} 23:59:59'::TIMESTAMP
                ORDER BY {clean_time_col} ASC
                LIMIT 50
            """
            vals_a = [float(x['val']) for x in qry(sql_a) if x.get('val') is not None]

            cpk_b = calc_cpk(float(np.mean(vals_b)), float(np.std(vals_b, ddof=1)), usl, lsl) if len(vals_b) > 1 else None
            cpk_a = calc_cpk(float(np.mean(vals_a)), float(np.std(vals_a, ddof=1)), usl, lsl) if len(vals_a) > 1 else None
            diff = (cpk_a - cpk_b) if (cpk_a is not None and cpk_b is not None) else None
            return cpk_b, cpk_a, diff

        chosen_event = None
        source_type = "same_machine_best"
        source_mach = machine
        matched_spec_level = "exact"

        if not is_cu:
            # ──────── 成型机 GT 推荐逻辑 ────────
            # 1. 优先级 1: 优先在【同规格同机台】下检索 ref_date 前 30 天的历史调参版本
            sql_same = f"""
                SELECT 
                    Workcenter,
                    TechOffsetHistoryLocalDate as event_time,
                    ParameterLocalName,
                    ParameterName,
                    TechOffsetHistoryValueFrom,
                    TechOffsetHistoryValueTo,
                    ParameterValue,
                    ParameterUnitSymbol,
                    Priority,
                    UserName,
                    ProdSpecific2
                FROM cgrs_records
                WHERE Workcenter IN ('{cands_in}')
                  AND {spec_cond_cgrs_p7}
                  AND TRY_CAST(event_timestamp AS DATE) <= '{ref_date}'::DATE
                  AND TRY_CAST(event_timestamp AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                ORDER BY TechOffsetHistoryLocalDate DESC
            """
            rows_same = qry(sql_same)
            if rows_same:
                event_groups = {}
                for r in rows_same:
                    t_key = str(r.get('event_time', ''))[:16]
                    if t_key not in event_groups:
                        event_groups[t_key] = []
                    event_groups[t_key].append(r)

                scored_events = []
                for t_str, p_list in event_groups.items():
                    cb, ca, cdiff = eval_event_improvement(machine, t_str)
                    scored_events.append({
                        "source_machine": machine,
                        "event_time": t_str,
                        "cpk_b": cb,
                        "cpk_a": ca,
                        "diff": cdiff,
                        "params": p_list
                    })

                improved = [e for e in scored_events if e['diff'] is not None and e['diff'] > 0]
                if improved:
                    improved.sort(key=lambda x: x['diff'], reverse=True)
                    chosen_event = improved[0]
                else:
                    scored_events.sort(key=lambda x: (x['cpk_a'] is not None, x['cpk_a'] or -999.0), reverse=True)
                    chosen_event = scored_events[0]

            # 2. 优先级 2: 若本机台无同规格调参，或调参没有改善 -> 搜索【同工段同规格】生产该规格的其他机台 / 标杆机台 (完全不使用前五位)
            if not chosen_event or (chosen_event.get('diff') is not None and chosen_event['diff'] <= 0):
                sql_stage_producers = f"""
                    SELECT DISTINCT {clean_wc_col} as wc
                    FROM clean_yield
                    WHERE article10 LIKE '{spec_prefix7}%'
                      AND {clean_wc_col} NOT IN ('{cands_in}')
                """
                producers = [x['wc'] for x in qry(sql_stage_producers) if x.get('wc')]
                prod_order_case = ""
                if producers:
                    p_in = "', '".join(producers)
                    prod_order_case = f"CASE WHEN Workcenter IN ('{p_in}') THEN 0 ELSE 1 END,"

                sql_stage_p7 = f"""
                    SELECT 
                        Workcenter,
                        TechOffsetHistoryLocalDate as event_time,
                        ParameterLocalName,
                        ParameterName,
                        TechOffsetHistoryValueFrom,
                        TechOffsetHistoryValueTo,
                        ParameterValue,
                        ParameterUnitSymbol,
                        Priority,
                        UserName,
                        ProdSpecific2
                    FROM cgrs_records
                    WHERE {stage_wc_cond}
                      AND Workcenter NOT IN ('{cands_in}')
                      AND {spec_cond_cgrs_p7}
                      AND TRY_CAST(event_timestamp AS DATE) <= '{ref_date}'::DATE
                      AND TRY_CAST(event_timestamp AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                    ORDER BY {prod_order_case} TechOffsetHistoryLocalDate DESC
                    LIMIT 100
                """
                rows_stage_p7 = qry(sql_stage_p7)
                if rows_stage_p7:
                    stage_groups = {}
                    for r in rows_stage_p7:
                        w = r.get('Workcenter')
                        t = str(r.get('event_time', ''))[:16]
                        k = (w, t)
                        if k not in stage_groups:
                            stage_groups[k] = []
                        stage_groups[k].append(r)

                    stage_scored = []
                    for (w, t_str), p_list in stage_groups.items():
                        cb, ca, cdiff = eval_event_improvement(w, t_str)
                        stage_scored.append({
                            "source_machine": w,
                            "event_time": t_str,
                            "cpk_b": cb,
                            "cpk_a": ca,
                            "diff": cdiff,
                            "params": p_list
                        })
                    improved_stage = [e for e in stage_scored if e['diff'] is not None and e['diff'] > 0]
                    if improved_stage:
                        improved_stage.sort(key=lambda x: x['diff'], reverse=True)
                        candidate_event = improved_stage[0]
                    else:
                        stage_scored.sort(key=lambda x: (x['cpk_a'] is not None, x['cpk_a'] or -999.0), reverse=True)
                        candidate_event = stage_scored[0]

                    if not chosen_event or (chosen_event.get('diff') or -999) < (candidate_event.get('diff') or -999):
                        chosen_event = candidate_event
                        source_type = "same_stage_best"
                        source_mach = candidate_event['source_machine']
                        matched_spec_level = "same_spec"

        else:
            # ──────── 硫化机 CT 推荐逻辑 ────────
            # 硫化机参数不与规格绑定，但每个规格生产的硫化机基本固定。
            # 追溯该规格在历史上不同天的硫化机表现情况来进行参数推荐。
            sql_fixed_ct = f"""
                SELECT DISTINCT ct_workcenter as wc
                FROM clean_yield
                WHERE article10 LIKE '{spec_prefix7}%'
                  AND ct_workcenter IS NOT NULL
                  AND ct_workcenter != ''
                  AND (ct_workcenter LIKE 'CU%' OR ct_workcenter LIKE 'CT%' OR ct_workcenter LIKE 'CUG%')
                  AND TRY_CAST(ct_loc_timestamp AS DATE) <= '{ref_date}'::DATE
            """
            fixed_ct_rows = qry(sql_fixed_ct)
            fixed_ct_machines = [r['wc'] for r in fixed_ct_rows if r.get('wc')]

            # Priority 1: 本机台在 past 30 days 内的调参记录 (不按规格过滤，因为硫化机调参不绑定规格)
            # 追溯该机台在调参事件发生后，生产该规格的表现 (CPK)
            sql_same_ct = f"""
                SELECT 
                    Workcenter,
                    TechOffsetHistoryLocalDate as event_time,
                    ParameterLocalName,
                    ParameterName,
                    TechOffsetHistoryValueFrom,
                    TechOffsetHistoryValueTo,
                    ParameterValue,
                    ParameterUnitSymbol,
                    Priority,
                    UserName
                FROM cgrs_records
                WHERE Workcenter IN ('{cands_in}')
                  AND TRY_CAST(event_timestamp AS DATE) <= '{ref_date}'::DATE
                  AND TRY_CAST(event_timestamp AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                ORDER BY TechOffsetHistoryLocalDate DESC
            """
            rows_same_ct = qry(sql_same_ct)
            if rows_same_ct:
                event_groups = {}
                for r in rows_same_ct:
                    t_key = str(r.get('event_time', ''))[:16]
                    if t_key not in event_groups:
                        event_groups[t_key] = []
                    event_groups[t_key].append(r)

                scored_events = []
                for t_str, p_list in event_groups.items():
                    cb, ca, cdiff = eval_event_improvement(machine, t_str)
                    scored_events.append({
                        "source_machine": machine,
                        "event_time": t_str,
                        "cpk_b": cb,
                        "cpk_a": ca,
                        "diff": cdiff,
                        "params": p_list
                    })

                improved = [e for e in scored_events if e['diff'] is not None and e['diff'] > 0]
                if improved:
                    improved.sort(key=lambda x: x['diff'], reverse=True)
                    chosen_event = improved[0]
                else:
                    # 仅当本机台在该规格上有生产 CPK 数据时才采用
                    valid_events = [e for e in scored_events if e['cpk_a'] is not None]
                    if valid_events:
                        valid_events.sort(key=lambda x: x['cpk_a'], reverse=True)
                        chosen_event = valid_events[0]

            # Priority 2: 生产该规格的其他固定硫化机在 past 30 days 内的调参记录
            if not chosen_event or (chosen_event.get('diff') is not None and chosen_event['diff'] <= 0):
                other_fixed = [m for m in fixed_ct_machines if m not in candidates]
                if other_fixed:
                    other_in = "', '".join(other_fixed)
                    sql_other_ct = f"""
                        SELECT 
                            Workcenter,
                            TechOffsetHistoryLocalDate as event_time,
                            ParameterLocalName,
                            ParameterName,
                            TechOffsetHistoryValueFrom,
                            TechOffsetHistoryValueTo,
                            ParameterValue,
                            ParameterUnitSymbol,
                            Priority,
                            UserName
                        FROM cgrs_records
                        WHERE Workcenter IN ('{other_in}')
                          AND TRY_CAST(event_timestamp AS DATE) <= '{ref_date}'::DATE
                          AND TRY_CAST(event_timestamp AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                        ORDER BY TechOffsetHistoryLocalDate DESC
                        LIMIT 100
                    """
                    rows_other_ct = qry(sql_other_ct)
                    if rows_other_ct:
                        stage_groups = {}
                        for r in rows_other_ct:
                            w = r.get('Workcenter')
                            t = str(r.get('event_time', ''))[:16]
                            k = (w, t)
                            if k not in stage_groups:
                                stage_groups[k] = []
                            stage_groups[k].append(r)

                        stage_scored = []
                        for (w, t_str), p_list in stage_groups.items():
                            cb, ca, cdiff = eval_event_improvement(w, t_str)
                            stage_scored.append({
                                "source_machine": w,
                                "event_time": t_str,
                                "cpk_b": cb,
                                "cpk_a": ca,
                                "diff": cdiff,
                                "params": p_list
                            })

                        improved_stage = [e for e in stage_scored if e['diff'] is not None and e['diff'] > 0]
                        if improved_stage:
                            improved_stage.sort(key=lambda x: x['diff'], reverse=True)
                            candidate_event = improved_stage[0]
                        else:
                            valid_stage = [e for e in stage_scored if e['cpk_a'] is not None]
                            if valid_stage:
                                valid_stage.sort(key=lambda x: x['cpk_a'], reverse=True)
                                candidate_event = valid_stage[0]
                            else:
                                candidate_event = stage_scored[0] if stage_scored else None

                        if candidate_event:
                            if not chosen_event or (chosen_event.get('diff') or -999) < (candidate_event.get('diff') or -999):
                                chosen_event = candidate_event
                                source_type = "same_stage_best"
                                source_mach = candidate_event['source_machine']
                                matched_spec_level = "fixed_spec_producer"

        if not chosen_event:
            return {
                "status": "success",
                "has_recommendation": False,
                "reason": reason,
                "recommend_title": f"暂无【{stage_name_cn}】该规格历史参考调参数据",
                "message": f"在观察日 [{ref_date}] 前 30 天内，同工段【{stage_name_cn}】暂无规格 [{article10}] 的工艺调参记录",
                "params": []
            }

        def fmt_num(v):
            if v is None:
                return "-"
            f = float(v)
            return f"{f:.4f}".rstrip('0').rstrip('.') if '.' in f"{f:.4f}" else f"{f}"

        formatted_params = []
        for p in chosen_event['params']:
            v_from = float(p.get("TechOffsetHistoryValueFrom") or 0.0)
            v_to = float(p.get("TechOffsetHistoryValueTo") or 0.0)
            d_val = round(v_to - v_from, 4)
            delta_str = f"{d_val:+.4f}".rstrip('0').rstrip('.') if '.' in f"{d_val:+.4f}" else f"{d_val:+}"
            if delta_str == "+0" or delta_str == "-0":
                delta_str = "0"

            p_val = p.get("ParameterValue")
            unit_str = p.get("ParameterUnitSymbol") or ""

            # 纯设定值轨迹：若有最终设定值，则改前设定值 = 设定值 - delta 偏置调整量
            if p_val is not None:
                try:
                    f_to = float(p_val)
                    f_from = round(f_to - d_val, 4)
                    setting_from = fmt_num(f_from)
                    setting_to = fmt_num(f_to)
                except Exception:
                    setting_from = fmt_num(v_from)
                    setting_to = fmt_num(v_to)
            else:
                setting_from = fmt_num(v_from)
                setting_to = fmt_num(v_to)

            ev_time = str(p.get("event_time", "") or chosen_event['event_time'])[:19]

            formatted_params.append({
                "param_name": p.get("ParameterName", ""),
                "param_local_name": p.get("ParameterLocalName") or p.get("ParameterName"),
                "event_time": ev_time,
                "val_from": fmt_num(v_from),
                "val_to": fmt_num(v_to),
                "delta": delta_str,
                "final_value": fmt_num(p_val),
                "setting_from": setting_from,
                "setting_to": setting_to,
                "unit": unit_str,
                "priority": p.get("Priority") or 3,
                "operator": p.get("UserName") or "工艺员"
            })

        cb = chosen_event.get('cpk_b')
        ca = chosen_event.get('cpk_a')
        diff = chosen_event.get('diff')
        yoy = round((ca - cb) / cb * 100.0, 1) if (cb and ca and cb > 0) else None

        recommend_category = "same_machine" if source_type == "same_machine_best" else "cross_machine"

        if source_type == "same_machine_best":
            rec_title = f"建议复原至本机台 [{machine}] 历史最佳调参 ({chosen_event['event_time']})"
            rec_desc = f"在观察日 [{ref_date}] 前 30 天内，本机台曾于 {chosen_event['event_time']} 进行工艺优化，调参后 CPK 提升至 {ca:.2f}（提升 {yoy:+.1f}%）。" if (ca and yoy) else (f"在观察日 [{ref_date}] 前 30 天内匹配到本机台调参版本，调参后 CPK 为 {ca:.2f}。" if ca else f"在观察日 [{ref_date}] 前 30 天内匹配到本机台优化调参版本。")
        else:
            rec_title = f"推荐参考生产该规格的标杆机台 [{source_mach}] 历史最佳参数 ({chosen_event['event_time']})"
            rec_desc = f"本机台过去 30 天无有效提升调参，系统自动匹配到生产该规格的标杆机台 [{source_mach}] 最佳工艺设定，调参后该机台 CPK 提升至 {ca:.2f}。" if ca else f"匹配到生产该规格的标杆机台 [{source_mach}] 工艺设定。"

        return sanitize_data({
            "status": "success",
            "has_recommendation": True,
            "reason": reason,
            "recommend_category": recommend_category,
            "source_type": source_type,
            "source_machine": source_mach,
            "target_machine": machine,
            "target_spec": article10,
            "target_date": ref_date,
            "matched_spec_level": matched_spec_level,
            "best_event_time": chosen_event['event_time'],
            "cpk_before": round(cb, 2) if cb is not None else None,
            "cpk_after": round(ca, 2) if ca is not None else None,
            "cpk_diff": round(diff, 2) if diff is not None else None,
            "yoy_pct": yoy,
            "recommend_title": rec_title,
            "recommend_desc": rec_desc,
            "params": formatted_params
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "has_recommendation": False,
            "message": f"推荐接口执行异常: {str(e)}"
        }


# ── 静态文件托管 (必须放在所有 API 路由之后注册，否则会拦截 /api 请求) ──
import sys
from fastapi.staticfiles import StaticFiles
if getattr(sys, 'frozen', False):
    _static_base = sys._MEIPASS
else:
    _static_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_frontend_dist_candidate = os.path.join(_static_base, "frontend", "dist")
_root_dist_candidate = os.path.join(_static_base, "dist")
FRONTEND_DIST = _frontend_dist_candidate if os.path.isdir(_frontend_dist_candidate) else _root_dist_candidate
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
