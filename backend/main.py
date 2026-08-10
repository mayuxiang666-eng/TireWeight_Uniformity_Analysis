from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import duckdb
import os
import json
from datetime import datetime, timedelta
import numpy as np
# from kmeans_service import get_kmeans_diagnostics, get_kmeans_paths, get_kmeans_labeled_data

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

# ── 数据源路径与全局常驻连接 ────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_BASE, "data", "yield_flat_table_joined_100_cleaned.parquet")
if not os.path.exists(DATA_PATH):
    legacy_path = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
    if os.path.exists(legacy_path):
        DATA_PATH = legacy_path

# 全局 DuckDB 常驻连接与内存表，将 Parquet 数据载入内存以提升并发检索速度
db_conn = duckdb.connect()

def reload_duckdb_data():
    """重新加载数据并重建内存表"""
    if os.path.exists(DATA_PATH):
        db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")
        return True
    return False

reload_duckdb_data()


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
        return 0.8
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


# 工位与批次物料对应关系
LOT_MAP = {
    "tread_workcenter": "tread_lot",
    "wound_cap_ply1_workcenter": "wound_cap_ply1_lot",
    "wound_cap_ply2_workcenter": "wound_cap_ply2_lot",
    "first_breaker_workcenter": "first_breaker_lot",
    "second_breaker_workcenter": "second_breaker_lot",
    "sidewall_workcenter": "sidewall_lot",
    "bead_workcenter": "bead_lot",
    "inner_liner_workcenter": "inner_liner_lot",
    "first_ply_workcenter": "first_ply_lot"
}


# ── 辅助函数：根据数据范围计算/补全时间段 (补充时序强校验，防反向交叠) ────
def get_periods(baseline_from=None, baseline_to=None, study_from=None, study_to=None):
    res = qry("SELECT MIN(tu_first_shift_date)::DATE as min_d, MAX(tu_first_shift_date)::DATE as max_d FROM clean_yield")[0]
    min_d_obj = res['min_d']
    max_d_obj = res['max_d']
    
    min_d = min_d_obj.strftime("%Y-%m-%d") if hasattr(min_d_obj, 'strftime') else str(min_d_obj)
    max_d = max_d_obj.strftime("%Y-%m-%d") if hasattr(max_d_obj, 'strftime') else str(max_d_obj)
    
    min_dt = datetime.strptime(min_d, "%Y-%m-%d")
    max_dt = datetime.strptime(max_d, "%Y-%m-%d")
    
    # 规则: 如果基准期间和研究期都未选择，则默认采用前十天和后十天
    if not baseline_from and not study_from:
        baseline_from = min_d
        baseline_to = (min_dt + timedelta(days=9)).strftime("%Y-%m-%d")
        study_from = (max_dt - timedelta(days=9)).strftime("%Y-%m-%d")
        study_to = max_d
    else:
        # 补齐单侧缺省的截止日期
        if study_from and not study_to:
            study_to = max_d
        if baseline_from and not baseline_to:
            baseline_to = (datetime.strptime(baseline_from, "%Y-%m-%d") + timedelta(days=9)).strftime("%Y-%m-%d")

    # 时序强约束校验 (仅在两者都存在时生效)
    try:
        if baseline_from and baseline_to and study_from and study_to:
            bf = datetime.strptime(baseline_from, "%Y-%m-%d")
            bt = datetime.strptime(baseline_to, "%Y-%m-%d")
            sf = datetime.strptime(study_from, "%Y-%m-%d")
            st = datetime.strptime(study_to, "%Y-%m-%d")
            
            if bf > bt:
                bt = bf
                baseline_to = baseline_from
            if bt >= sf:
                sf = bt + timedelta(days=1)
                study_from = sf.strftime("%Y-%m-%d")
            if sf > st:
                st = sf
                study_to = study_from
    except Exception:
        pass
        
    return baseline_from, baseline_to, study_from, study_to


# ── 辅助函数：对嫌疑机台进行局部/全局对照诊断 (参数化重构 & 字段白名单防护) ────
def diagnose_machine(machine_id, workcenter_col, study_from, study_to):
    if workcenter_col not in LOT_MAP:
        return "设备系统性工艺漂移", "该工序无对应物料批次，排除特定批次物料影响，判定为设备系统性性能衰退或工艺漂移，建议停机校验"
        
    lot_col = LOT_MAP.get(workcenter_col)
    
    # 获取机台总排产与异常数
    m_sql = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CAST(grade_anomaly AS INT)) as anomalies
        FROM clean_yield
        WHERE {workcenter_col} = ?
          AND tu_first_shift_date::DATE >= ?::DATE
          AND tu_first_shift_date::DATE <= ?::DATE
    """
    m_stats = qry(m_sql, [machine_id, study_from, study_to])[0]
    m_total = m_stats['total'] or 0
    m_anomalies = m_stats['anomalies'] or 0
    
    if m_total == 0 or m_anomalies == 0:
        return "设备系统性工艺漂移", "所有批次的异常率表现均匀，判定为设备自身工艺漂移，建议停机进行零点校准"

    if not lot_col:
        return "设备系统性工艺漂移", "该工序无对应物料批次，判定为设备系统性性能衰退或工艺漂移，建议停机校验"

    # 查询该机台下的大排产物料批次
    lot_sql = f"""
        SELECT 
            {lot_col} as lot_val,
            COUNT(*) as lot_total,
            SUM(CAST(grade_anomaly AS INT)) as lot_anomaly
        FROM clean_yield
        WHERE {workcenter_col} = ?
          AND tu_first_shift_date::DATE >= ?::DATE
          AND tu_first_shift_date::DATE <= ?::DATE
          AND {lot_col} IS NOT NULL
        GROUP BY {lot_col}
        HAVING lot_total > 30 AND lot_anomaly >= 5
    """
    lots = qry(lot_sql, [machine_id, study_from, study_to])
    
    if not lots:
        return "设备系统性工艺漂移", "未发现局部异常集中度超标的物料批次，设备整体异常率偏高，建议执行校准"
        
    outliers = []
    for lot in lots:
        lot_val = lot['lot_val']
        lot_total = lot['lot_total']
        lot_anomaly = lot['lot_anomaly']
        
        # Local Lift
        local_lift = (lot_anomaly / lot_total) / (m_anomalies / m_total)
        
        # Cross-Machine Lift
        g_sql = f"""
            SELECT 
                COUNT(*) as g_total,
                SUM(CAST(grade_anomaly AS INT)) as g_anomaly
            FROM clean_yield
            WHERE {lot_col} = ?
              AND tu_first_shift_date::DATE >= ?::DATE
              AND tu_first_shift_date::DATE <= ?::DATE
        """
        g_stats = qry(g_sql, [lot_val, study_from, study_to])[0]
        g_total = g_stats['g_total'] or 0
        g_anomaly = g_stats['g_anomaly'] or 0
        
        cross_lift = 1.0
        if g_total > 0 and g_anomaly > 0:
            cross_lift = (lot_anomaly / lot_total) / (g_anomaly / g_total)
            
        if local_lift > 1.5:
            outliers.append({
                "lot": lot_val,
                "local_lift": local_lift,
                "cross_lift": cross_lift
            })
            
    if not outliers:
        return "设备系统性工艺漂移", "该机台下各批次异常率偏高且表现均匀，排除特定批次物料影响，判定为设备硬件精度衰退"
        
    # 对最显著的偏高批次给出结论
    primary = outliers[0]
    if primary['local_lift'] > 1.5 and primary['cross_lift'] > 1.5:
        return "机台-批次适配性故障", f"物料批次 {primary['lot']} 仅在嫌疑机台异常率偏高（Local Lift={primary['local_lift']:.2f}, Cross={primary['cross_lift']:.2f}），而在其他机台正常。建议微调机台适配参数"
    else:
        return "全局物料批次缺陷", f"物料批次 {primary['lot']} 在全场所有设备上异常率均偏高（Local Lift={primary['local_lift']:.2f}, Cross={primary['cross_lift']:.2f}），判定为原材料自身缺陷。建议封存并追溯该批次"


# ── 健康检测与 ETL 重载 ──────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "message": "轮胎质量分析看板 API 运行中"}


@app.post("/api/etl/reload")
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
        file_exists = os.path.exists(DATA_PATH)
        mtime_str = None
        size_bytes = 0
        if file_exists:
            mtime = os.path.getmtime(DATA_PATH)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_bytes = os.path.getsize(DATA_PATH)
            
        row_res = qry("SELECT COUNT(*) as n FROM clean_yield") if file_exists else []
        row_count = row_res[0]['n'] if row_res else 0
        
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


# ── 1. 总览摘要 ─────────────────────────────────────────────────
# @app.get("/api/summary")
# def get_summary():
#     try:
#         sql = """
#             SELECT
#                 COUNT(*)                            AS total_records,
#                 COUNT(DISTINCT article10)           AS unique_articles,
#                 SUM(CAST(grade_anomaly AS INT)) AS total_anomalies,
#                 ROUND(AVG(CAST(grade_anomaly AS DOUBLE)) * 100, 4) AS anomaly_rate_pct,
#                 MIN(tu_first_shift_date)::DATE             AS date_min,
#                 MAX(tu_first_shift_date)::DATE             AS date_max
#             FROM clean_yield
#         """
#         return {"status": "success", "data": qry(sql)[0]}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 2. 日度趋势 ─────────────────────────────────────────────────
# @app.get("/api/trend/daily")
# def get_daily_trend(
#     article10: Optional[str] = Query(None),
# ):
#     try:
#         where = ""
#         params = []
#         if article10:
#             where = "WHERE article10 = ?"
#             params.append(article10)
# 
#         sql = f"""
#             SELECT
#                 tu_first_shift_date::DATE                              AS date,
#                 COUNT(*)                                        AS total,
#                 SUM(CAST(grade_anomaly AS INT))             AS anomalies,
#                 COUNT(*) - SUM(CAST(grade_anomaly AS INT)) AS normals,
#                 ROUND(AVG(CAST(grade_anomaly AS DOUBLE))*100, 4) AS anomaly_rate
#             FROM clean_yield
#             {where}
#             GROUP BY 1
#             ORDER BY 1
#         """
#         rows = qry(sql, params)
#         # 丢弃最后一天（防数据不完整）
#         if len(rows) > 1:
#             rows = rows[:-1]
#         # 转为字符串日期
#         for r in rows:
#             r["date"] = str(r["date"])
#         return {"status": "success", "data": rows}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 3. 周度趋势 ─────────────────────────────────────────────────
# @app.get("/api/trend/weekly")
# def get_weekly_trend(
#     article10: Optional[str] = Query(None),
# ):
#     try:
#         where = ""
#         params = []
#         if article10:
#             where = "WHERE article10 = ?"
#             params.append(article10)
# 
#         sql = f"""
#             SELECT
#                 DATE_TRUNC('week', tu_first_shift_date::DATE)         AS week_start,
#                 COUNT(*)                                        AS total,
#                 SUM(CAST(grade_anomaly AS INT))             AS anomalies,
#                 COUNT(*) - SUM(CAST(grade_anomaly AS INT)) AS normals,
#                 ROUND(AVG(CAST(grade_anomaly AS DOUBLE))*100, 4) AS anomaly_rate
#             FROM clean_yield
#             {where}
#             GROUP BY 1
#             ORDER BY 1
#         """
#         rows = qry(sql, params)
#         for r in rows:
#             r["week_start"] = str(r["week_start"])
#         return {"status": "success", "data": rows}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 4. 规格型号排行 (支持 Shift-Share 贡献度计算，根据 min_yield 过滤) ──────
# @app.get("/api/articles")
# def get_articles(
#     limit: int = Query(20, ge=1, le=200),
#     date_from: Optional[str] = Query(None),
#     date_to: Optional[str] = Query(None),
#     baseline_from: Optional[str] = Query(None),
#     baseline_to: Optional[str] = Query(None),
#     study_from: Optional[str] = Query(None),
#     study_to: Optional[str] = Query(None),
#     sort_by: Optional[str] = Query("contribution"), # "contribution" | "anomalies"
#     min_yield: int = Query(50)
# ):
#     try:
#         # 获取补全/调整后的分析周期，确保全局日期逻辑一致
#         b_from, b_to, s_from, s_to = get_periods(baseline_from, baseline_to, study_from, study_to)
#         
#         # 当选择了基准期和研究期时间段，启动 Shift-Share 贡献度算法
#         if b_from and b_to and s_from and s_to:
#             sql_overall = """
#                 SELECT 
#                     COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_b,
#                     COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_s
#                 FROM clean_yield
#                 WHERE tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE
#             """
#             overall = qry(sql_overall, [
#                 b_from, b_to, 
#                 s_from, s_to,
#                 b_from, s_to
#             ])[0]
#             total_b = overall['total_b'] or 0
#             total_s = overall['total_s'] or 0
#             
#             sql = """
#                 WITH by_article AS (
#                     SELECT
#                         article10,
#                         COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_b,
#                         SUM(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                         COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_s,
#                         SUM(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#                     FROM clean_yield
#                     WHERE tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE
#                     GROUP BY article10
#                     HAVING total_s > ?  -- 过滤：根据 min_yield 过滤
#                 )
#                 SELECT
#                     article10,
#                     total_s AS total,
#                     anomalies_s AS anomalies,
#                     CASE WHEN total_s > 0 THEN ROUND(CAST(anomalies_s AS DOUBLE) / total_s * 100, 4) ELSE 0 END AS anomaly_rate,
#                     ROUND(
#                         (
#                             (CAST(anomalies_s AS DOUBLE) / NULLIF(?, 0)) - 
#                             (CAST(anomalies_b AS DOUBLE) / NULLIF(?, 0))
#                         ) * 100, 
#                         4
#                     ) AS contribution
#                 FROM by_article
#             """
#             params = [
#                 b_from, b_to,
#                 b_from, b_to,
#                 s_from, s_to,
#                 s_from, s_to,
#                 b_from, s_to,
#                 min_yield,
#                 total_s, total_b
#             ]
#             rows = qry(sql, params)
#             for r in rows:
#                 contrib = r['contribution'] or 0.0
#                 r['contribution'] = contrib
#                 r['abs_contribution'] = abs(contrib)
#             
#             if sort_by == "anomalies":
#                 rows.sort(key=lambda x: x['anomalies'], reverse=True)
#             else:
#                 rows.sort(key=lambda x: x['abs_contribution'], reverse=True)
#                 
#             return {"status": "success", "data": sanitize_data(rows[:limit])}
#         else:
#             # 默认排序模式：按绝对异常数倒序，根据 min_yield 过滤
#             conditions = []
#             params = []
#             
#             # 如果提供了 s_from，优先使用研究期进行过滤
#             if s_from:
#                 conditions.append("tu_first_shift_date::DATE >= ?::DATE")
#                 params.append(s_from)
#             if s_to:
#                 conditions.append("tu_first_shift_date::DATE <= ?::DATE")
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
    indicator: str = Query("rfpp"),       # "rfpp" | "rfh1" | "cony"
    study_from: Optional[str] = Query(None),  # 仅作为分析目标日期使用
    study_to: Optional[str] = Query(None),
    only_declining: bool = Query(False),
    min_samples: int = Query(30),
):
    try:
        # 确定分析目标日期（取 study_to，单日点击时 study_from == study_to）
        target_date = study_to or study_from
        if not target_date:
            res = qry("SELECT MAX(tu_first_shift_date)::DATE AS max_d FROM clean_yield")[0]
            td = res['max_d']
            target_date = td.strftime("%Y-%m-%d") if hasattr(td, 'strftime') else str(td)

        if indicator == "weight":
            # 胎重指标下的单日偏差贡献度排行
            # 计算公式: 贡献度 = (规格偏差率 - 全厂整体偏差率) * 产量占比
            sql_target = """
                SELECT
                    article10,
                    COUNT(*) AS sample_size,
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_actual,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) AS sum_target
                FROM clean_yield
                WHERE tu_first_shift_date::DATE = ?
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            rows = qry(sql_target, [target_date, min_samples])
            if not rows:
                return {"status": "success", "data": []}
                
            total_n = sum(int(r['sample_size']) for r in rows)
            if total_n == 0:
                return {"status": "success", "data": []}
                
            total_actual = sum(float(r['sum_actual']) for r in rows)
            total_target = sum(float(r['sum_target']) for r in rows)
            
            # 全厂聚合有符号偏差率
            overall_diff = (total_actual - total_target) / total_target * 100.0 if total_target > 0 else 0.0
            
            results = []
            for r in rows:
                article10 = r['article10']
                n = int(r['sample_size'])
                sum_act = float(r['sum_actual'])
                sum_tar = float(r['sum_target'])
                
                # 规格聚合有符号偏差率
                spec_diff = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0
                
                # 贡献度 = (spec_diff - overall_diff) * (n / total_n)
                contrib = (spec_diff - overall_diff) * (n / total_n)
                
                critical_m = calculate_critical_machine(
                    article10=article10,
                    indicator="weight",
                    target_date=target_date,
                    min_samples=min_samples
                )
                
                results.append({
                    "article10": article10,
                    "stable_score": round(contrib, 4), # 贡献度
                    "single_cpk": round(spec_diff, 4),   # 规格有符号偏差 %
                    "avg_cpk": round(overall_diff, 4),   # 全厂有符号偏差 %
                    "sample_size": n,
                    "warning_machine": critical_m or "无"
                })
                
            # 按贡献度的绝对值从大到小排序，取前 10
            results.sort(key=lambda x: abs(x['stable_score']), reverse=True)
            return {"status": "success", "data": sanitize_data(results[:10])}

        ind_col = "cony_first" if indicator == "cony" else ("rfppwc_first" if indicator == "rfpp" else "rfh1wc_first")
        
        sql_target = f"""
            SELECT
                article10,
                COUNT(*) AS sample_size,
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
            WHERE tu_first_shift_date::DATE = ?
              AND {ind_col} IS NOT NULL
            GROUP BY 1
            HAVING COUNT(*) >= ?
        """
        rows = qry(sql_target, [target_date, min_samples])
        if not rows:
            return {"status": "success", "data": []}

        # 计算各规格的单日指标值 (CPK 或实际均值)
        valid_specs = []
        total_n = 0
        weighted_cpk_sum = 0.0

        for r in rows:
            article10 = r['article10']
            n = r['sample_size']
            avg_v = r['avg_v'] or 0.0
            std_v = r['std_v'] or 0.0
            
            if indicator == "cony":
                val = avg_v
            else:
                usl_v = r['usl_rfpp'] if indicator == "rfpp" else r['usl_rfh1']
                if std_v > 1e-6 and usl_v is not None:
                    val = (usl_v - avg_v) / (3.0 * std_v)
                else:
                    continue
            
            if np.isnan(val) or np.isinf(val):
                continue
                
            valid_specs.append({
                "article10": article10,
                "val": val,
                "n": n
            })
            weighted_cpk_sum += val * n
            total_n += n

        if total_n == 0:
            return {"status": "success", "data": []}

        # 方案 B：加权系统综合均值
        avg_cpk = weighted_cpk_sum / total_n

        # 计算负向贡献度 (即拉低厂区整体 CPK 的规格)
        results = []
        for s in valid_specs:
            neg_contrib = (avg_cpk - s['val']) * s['n']
            if neg_contrib <= 0:
                continue
            
            critical_m = calculate_critical_machine(
                article10=s['article10'],
                indicator=indicator,
                target_date=target_date,
                min_samples=min_samples
            )
            
            results.append({
                "article10": s['article10'],
                "stable_score": round(neg_contrib, 4), # 负贡献数值作为图表主数值
                "single_cpk": round(s['val'], 4),
                "avg_cpk": round(avg_cpk, 4),
                "sample_size": s['n'],
                "warning_machine": critical_m or "无"
            })

        # 按负贡献度降序（从大到小，拉低最严重的排在最前）
        results.sort(key=lambda x: x['stable_score'], reverse=True)
        return {"status": "success", "data": sanitize_data(results[:10])}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 5. 规格型号下钻：日度趋势 ──────────────────────────────────

# @app.get("/api/articles/{article}/trend")
# def get_article_trend(article: str):
#     try:
#         sql = """
#             SELECT
#                 tu_first_shift_date::DATE                              AS date,
#                 COUNT(*)                                        AS total,
#                 SUM(CAST(grade_anomaly AS INT))             AS anomalies,
#                 ROUND(AVG(CAST(grade_anomaly AS DOUBLE))*100, 4) AS anomaly_rate
#             FROM clean_yield
#             WHERE article10 = ?
#             GROUP BY 1
#             ORDER BY 1
#         """
#         rows = qry(sql, [article])
#         if len(rows) > 1:
#             rows = rows[:-1]
#         for r in rows:
#             r["date"] = str(r["date"])
#         return {"status": "success", "data": rows}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 6. 工位机台异常排行 (支持 Shift-Share 贡献度与 Step Lift，根据 min_yield 过滤) ──
@app.get("/api/machines")
def get_machines(
    article10: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    baseline_from: Optional[str] = Query(None),
    baseline_to: Optional[str] = Query(None),
    study_from: Optional[str] = Query(None),
    study_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("contribution"), # "contribution" | "step_lift" | "anomalies"
    min_yield: int = Query(50),
    workcenter_col: Optional[str] = Query(None),
    cluster_id: Optional[int] = Query(None),
    cluster_type: Optional[str] = Query(None)
):
    try:
        # 获取补全/调整后的分析周期，确保全局日期逻辑一致
        b_from, b_to, s_from, s_to = get_periods(baseline_from, baseline_to, study_from, study_to)
        
        # if cluster_id is not None and cluster_type and s_from and s_to and b_from and b_to and workcenter_col:
#             # 1. 自动补齐工序列名，如 tread_workcenter
#             wc_col = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
            
#             # 2. 调取 KMeans 聚类打标 DataFrame (这里使用调整后的日期，才能打中 /api/diagnose/paths 生成的缓存)
#             df_anom_res, df_norm_res, total_all = get_kmeans_labeled_data(
#                 db_conn, s_from, s_to, b_from, b_to, min_yield
#             )
#             df_labeled = df_anom_res if cluster_type == 'anomaly' else df_norm_res
            
#             if df_labeled is not None and not df_labeled.empty and wc_col in df_labeled.columns:
#                 # 过滤出当前聚类的样本
#                 df_cluster = df_labeled[df_labeled['cluster'] == cluster_id]
#                 cluster_size = len(df_cluster)
                
#                 # 统计各机台在该聚类簇内的出现次数 (频数)，作为 anomalies
#                 counts = df_cluster[wc_col].value_counts()
#                 if not counts.empty:
#                     machines_list = list(counts.index)
#                     machines_placeholders = ",".join(["?"] * len(machines_list))
#                     sql_global = f"""
#                         SELECT 
#                             {wc_col} AS machine,
#                             COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
#                             SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                             COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
#                             SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#                         FROM clean_yield
#                         WHERE {wc_col} IN ({machines_placeholders})
#                         GROUP BY {wc_col}
#                     """
#                     params = [
#                         b_from, b_to,
#                         b_from, b_to,
#                         s_from, s_to,
#                         s_from, s_to
#                     ] + machines_list
#                     global_stats = {r["machine"]: r for r in qry(sql_global, params)}
                    
#                     rows = []
#                     for mach, count in counts.items():
#                         g = global_stats.get(mach, {})
#                         t_s = g.get("total_s", 0) or 0
#                         a_s = g.get("anomalies_s", 0) or 0
#                         t_b = g.get("total_b", 0) or 0
#                         a_b = g.get("anomalies_b", 0) or 0
                        
#                         rate_s = count / t_s * 100 if t_s > 0 else 0.0
#                         rate_b = a_b / t_b * 100 if t_b > 0 else 0.0
#                         contrib = rate_s - rate_b
                        
#                         natural_pct = t_s / max(1, total_all)
#                         concentration = count / max(1, cluster_size)
#                         s_lift = concentration / (natural_pct + 1e-8)
                        
#                         rows.append({
#                             "workcenter_col": wc_col,
#                             "machine": mach,
#                             "total": t_s,
#                             "anomalies": int(count),
#                             "total_b": t_b,
#                             "anomalies_b": a_b,
#                             "anomaly_rate": round(rate_s, 4),
#                             "contribution": round(contrib, 4),
#                             "abs_contribution": abs(round(contrib, 4)),
#                             "step_lift": round(s_lift, 4)
#                         })
                    
#                     if sort_by == "anomalies":
#                         rows.sort(key=lambda x: x['anomalies'], reverse=True)
#                     elif sort_by == "step_lift":
#                         rows.sort(key=lambda x: x['step_lift'], reverse=True)
#                     else:
#                         rows.sort(key=lambda x: x['abs_contribution'], reverse=True)
                        
#                     return {"status": "success", "data": sanitize_data(rows[:limit])}
            
#             return {"status": "success", "data": []}
        col_sql = """
            SELECT column_name
            FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
            WHERE column_name LIKE '%workcenter%'
              AND column_name NOT LIKE 'tu_%'
              AND column_name NOT LIKE 'tb_%'
              AND column_name NOT LIKE 'tg_%'
              AND column_name != 'css_workcenter'
        """
        wc_cols = [r["column_name"] for r in qry(col_sql)]

        if workcenter_col:
            normalized_wc = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
            if normalized_wc in wc_cols:
                wc_cols = [normalized_wc]
            else:
                wc_cols = []

        if not wc_cols:
            return {"status": "success", "data": []}

        where_parts = []
        if article10:
            where_parts.append("article10 = ?")
            
        # 如果有完整的对比期，直接在底层 union 中只提取这两个时期的数据，避免全量扫描
        use_full_range = b_from and b_to and s_from and s_to
        use_study_filter = not use_full_range and s_from
        
        if use_full_range:
            where_parts.append("tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE")
        elif use_study_filter:
            if s_from:
                where_parts.append("tu_first_shift_date >= ?::DATE")
            if s_to:
                where_parts.append("tu_first_shift_date <= ?::DATE")
                
        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        union_parts = []
        union_params = []
        for col in wc_cols:
            union_parts.append(f"""
                SELECT '{col}' AS workcenter_col,
                       CONCAT('{col}', ':', CAST({col} AS VARCHAR)) AS machine,
                       tu_first_shift_date,
                       grade_anomaly
                FROM clean_yield
                {where_clause}
                {"AND" if where_clause else "WHERE"} {col} IS NOT NULL
            """)
            if article10:
                union_params.append(article10)
            if use_full_range:
                union_params.append(b_from)
                union_params.append(s_to)
            elif use_study_filter:
                if s_from:
                    union_params.append(s_from)
                if s_to:
                    union_params.append(s_to)
        union_sql = " UNION ALL ".join(union_parts)

        # 当选择基准期和研究期时，执行深度 Shift-Share 和 Step Lift 计算
        if b_from and b_to and s_from and s_to:
            sql_overall = f"""
                WITH melted AS ({union_sql})
                SELECT 
                    COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
                    COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
                    SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s_all,
                    SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b_all
                FROM melted
            """
            overall_params = union_params + [
                b_from, b_to,
                s_from, s_to,
                s_from, s_to,
                b_from, b_to
            ]
            overall = qry(sql_overall, overall_params)[0]
            total_b_all = overall['total_b'] or 0
            total_s_all = overall['total_s'] or 0
            anomalies_s_all = overall['anomalies_s_all'] or 0
            anomalies_b_all = overall['anomalies_b_all'] or 0

            # 全局整体异常率变化
            overall_rate_s = (anomalies_s_all / total_s_all) if total_s_all > 0 else 0.0
            overall_rate_b = (anomalies_b_all / total_b_all) if total_b_all > 0 else 0.0
            delta_rate_overall = overall_rate_s - overall_rate_b

            sql = f"""
                WITH melted AS ({union_sql}),
                by_machine AS (
                    SELECT
                        workcenter_col,
                        machine,
                        COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
                        SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
                        COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
                        SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
                    FROM melted
                    GROUP BY workcenter_col, machine
                    HAVING total_s > ?  -- 过滤：根据 min_yield 过滤
                )
                SELECT
                    workcenter_col,
                    machine,
                    total_s AS total,
                    anomalies_s AS anomalies,
                    total_b,
                    anomalies_b,
                    CASE WHEN total_s > 0 THEN ROUND(CAST(anomalies_s AS DOUBLE) / total_s * 100, 4) ELSE 0 END AS anomaly_rate,
                    ROUND(
                        (CAST(bm.anomalies_s AS DOUBLE) / NULLIF(?, 0)) / 
                        ((CAST(bm.total_s AS DOUBLE) / NULLIF(?, 0)) + 1e-8),
                        4
                    ) AS step_lift
                FROM by_machine bm
            """
            machine_params = union_params + [
                b_from, b_to,
                b_from, b_to,
                s_from, s_to,
                s_from, s_to,
                min_yield,
                anomalies_s_all, total_s_all
            ]
            rows = qry(sql, machine_params)
            for r in rows:
                # 1. 动计算当前机台的异常率变化
                mach_rate_s = (r['anomalies'] / r['total']) if r['total'] > 0 else 0.0
                mach_rate_b = (r['anomalies_b'] / r['total_b']) if r['total_b'] > 0 else 0.0
                delta_rate_mach = mach_rate_s - mach_rate_b

                # 2. 计算贡献度：研究期该机台异常率 - 基准期该机台异常率
                contrib = round(delta_rate_mach * 100.0, 4)

                r['contribution'] = contrib
                r['abs_contribution'] = abs(contrib)
                raw_m = r['machine']
                if ':' in raw_m:
                    r['machine'] = raw_m.split(':', 1)[1]

            if sort_by == "anomalies":
                rows.sort(key=lambda x: x['anomalies'], reverse=True)
            elif sort_by == "step_lift":
                rows.sort(key=lambda x: x['step_lift'] or 0.0, reverse=True)
            else:
                rows.sort(key=lambda x: x['abs_contribution'], reverse=True)

            return {"status": "success", "data": sanitize_data(rows[:limit])}
        else:
            # 默认排序模式：按异常数倒序，根据 min_yield 过滤
            sql = f"""
                WITH melted AS ({union_sql})
                SELECT
                    workcenter_col,
                    machine,
                    COUNT(*)                                        AS total,
                    SUM(CAST(grade_anomaly AS INT))             AS anomalies,
                    COUNT(*) - SUM(CAST(grade_anomaly AS INT)) AS normals,
                    ROUND(AVG(CAST(grade_anomaly AS DOUBLE))*100, 4) AS anomaly_rate
                FROM melted
                GROUP BY workcenter_col, machine
                HAVING total > ?  -- 过滤：根据 min_yield 过滤
                ORDER BY anomalies DESC
                LIMIT ?
            """
            rows = qry(sql, union_params + [min_yield, limit])
            for r in rows:
                raw_m = r['machine']
                if ':' in raw_m:
                    r['machine'] = raw_m.split(':', 1)[1]
            return {"status": "success", "data": sanitize_data(rows)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 6.5. 机台 CPK (avg + 3sigma) 数据与下钻趋势接口 ─────────────────────
def compute_machine_all_weighted_cpk(workcenter_col: str, machine: str, indicator_col: str):
    """
    计算特定机台在全历史 dates 上的全规格加权 CPK 序列：
    先按 (dt, article10) Group 计算单规格 CPK，再按 Group 产量加权得到每日的全规格加权 CPK。
    """
    normalized_col = workcenter_col if workcenter_col.endswith("_workcenter") else f"{workcenter_col}_workcenter"
    sql = f"""
        SELECT 
            tu_first_shift_date::DATE AS dt,
            article10,
            COUNT(*) AS n,
            AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS mean_v,
            STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS std_v
        FROM clean_yield
        WHERE {normalized_col} = ? AND {indicator_col} IS NOT NULL AND tu_first_shift_date IS NOT NULL
        GROUP BY 1, 2
        HAVING COUNT(*) >= 1
    """
    rows = qry(sql, [machine])
    if not rows:
        return {}, 0.0, 0.0

    indicator = "rfpp" if indicator_col == "rfppwc_first" else "rfh1"
    daily_groups = {}
    for r in rows:
        dt_str = str(r['dt'])
        n = r['n']
        m_v = float(r['mean_v']) if r['mean_v'] is not None else 0.0
        s_v = float(r['std_v']) if r['std_v'] is not None else 0.0
        
        spec_usl = get_spec_usl(r['article10'], indicator)
        cpk_i = (spec_usl - m_v) / (3.0 * s_v + 1e-5) if s_v > 0 else 1.33
        cpk_i = max(0.0, min(5.0, cpk_i))

        if dt_str not in daily_groups:
            daily_groups[dt_str] = []
        daily_groups[dt_str].append((n, cpk_i))

    daily_cpk_map = {}
    for dt_str, g_list in daily_groups.items():
        total_n = sum(x[0] for x in g_list)
        if total_n > 0:
            w_cpk = sum(x[0] * x[1] for x in g_list) / total_n
            daily_cpk_map[dt_str] = round(w_cpk, 4)

    cpk_vals = list(daily_cpk_map.values())
    if cpk_vals:
        mean_all = float(np.mean(cpk_vals))
        std_all = float(np.std(cpk_vals))
    else:
        mean_all, std_all = 0.0, 0.0

    return daily_cpk_map, mean_all, std_all


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

        col_sql = """
            SELECT column_name
            FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
            WHERE column_name LIKE '%workcenter%'
              AND column_name != 'css_workcenter'
        """
        wc_cols = [r["column_name"] for r in qry(col_sql)]

        # 规格 USL 基准
        global_usl = get_spec_usl(article10, indicator)

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
                    spec_cpk = round(max(0.0, min(5.0, (global_usl - spec_avg) / (3.0 * spec_std))), 2)
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
                    c_v = round(max(0.0, min(5.0, (global_usl - m_v) / (3.0 * s_v))), 2) if s_v > 0 else 1.33
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
                    multi_cpk = round(max(0.0, min(5.0, (global_usl - multi_avg) / (3.0 * multi_std))), 2)
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
                    c_v = round(max(0.0, min(5.0, (global_usl - m_v) / (3.0 * s_v))), 2) if s_v > 0 else 1.33
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

        # 计算规格 USL 基准
        if article10 and (mode == "single" or mode == "spec_3sigma" or mode != "multi" and mode != "all_3sigma"):
            global_usl = get_spec_usl(article10, indicator)
        else:
            usl_sql = f"SELECT AVG(TRY_CAST({indicator_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({indicator_col} AS DOUBLE)), 0.0) as usl FROM clean_yield"
            usl_res = qry(usl_sql)
            global_usl = float(usl_res[0]['usl']) if usl_res and usl_res[0]['usl'] is not None else 100.0

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
            
            if s_val > 0:
                cpk_val = round(max(0.0, min(5.0, (global_usl - m_val) / (3.0 * s_val))), 2)
            else:
                cpk_val = 1.33

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

        # 计算规格 USL 基准 (确保与看板全局统一)
        global_usl = get_spec_usl(spec, indicator)

        where_parts = ["article10 = ?"]
        params = [spec]

        if start_date and end_date:
            where_parts.append("tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE")
            params.extend([start_date, end_date])
        elif target_date:
            where_parts.append("tu_first_shift_date::DATE = ?::DATE")
            params.append(target_date)

        # 聚合这四个核心工段的所有四元组组合
        sql = f"""
            SELECT 
                CAST(gt_workcenter AS VARCHAR) as gt,
                CAST(ct_workcenter AS VARCHAR) as ct,
                CAST(tu_first_workcenter AS VARCHAR) as tu,
                CAST(tb_first_workcenter AS VARCHAR) as tb,
                COUNT(*) as lot_cnt,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) as avg_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as std_val
            FROM clean_yield
            WHERE {" AND ".join(where_parts)}
              AND gt_workcenter IS NOT NULL
              AND ct_workcenter IS NOT NULL
              AND tu_first_workcenter IS NOT NULL
              AND tb_first_workcenter IS NOT NULL
            GROUP BY 1, 2, 3, 4
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
            "paths": path_list
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



def aggregate_node_stats_py(rows, usl, indicator="rfpp"):
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
        cpk = (usl - combined_mean) / (3.0 * combined_std) if combined_std > 1e-6 else 1.33
        cpk = max(0.0, min(5.0, cpk))
    
    return {
        "lot_cnt": total_n,
        "avg": combined_mean,
        "std": combined_std,
        "cpk": cpk
    }


def calculate_critical_machine(
    article10: str,
    indicator: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_date: Optional[str] = None,
    min_samples: int = 10,
) -> Optional[str]:
    try:
        if start_date in ("null", "None", ""):
            start_date = None
        if end_date in ("null", "None", ""):
            end_date = None
        if target_date in ("null", "None", ""):
            target_date = None

        if indicator == "weight":
            indicator_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
            avg_col = f"AVG(ABS(TRY_CAST({indicator_col} AS DOUBLE)))"
        elif indicator == "cony":
            indicator_col = "cony_first"
            avg_col = f"AVG(TRY_CAST({indicator_col} AS DOUBLE))"
        else:
            indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            avg_col = f"AVG(TRY_CAST({indicator_col} AS DOUBLE))"
            
        global_usl = get_spec_usl(article10, indicator)

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

        sql = f"""
            SELECT 
                CAST(gt_workcenter AS VARCHAR) as gt,
                CAST(ct_workcenter AS VARCHAR) as ct,
                CAST(tu_first_workcenter AS VARCHAR) as tu,
                CAST(tb_first_workcenter AS VARCHAR) as tb,
                COUNT(*) as lot_cnt,
                {avg_col} as avg_val,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as std_val
            FROM clean_yield
            WHERE {" AND ".join(where_parts)}
              AND gt_workcenter IS NOT NULL
              AND ct_workcenter IS NOT NULL
              AND tu_first_workcenter IS NOT NULL
              AND tb_first_workcenter IS NOT NULL
            GROUP BY 1, 2, 3, 4
            HAVING COUNT(*) >= 1
        """
        rows = qry(sql, params)
        if not rows:
            return None

        # 映射数据并计算 cpk
        data = []
        for r in rows:
            lot_cnt = int(r['lot_cnt'])
            avg_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
            std_val = float(r['std_val']) if r['std_val'] is not None else 0.0
            
            if indicator == "weight":
                cpk = avg_val
            else:
                cpk = (global_usl - avg_val) / (3.0 * std_val) if std_val > 0 else 1.33
                cpk = max(0.0, min(5.0, cpk))
            
            data.append({
                "lot_cnt": lot_cnt,
                "cpk": cpk,
                "avg_val": avg_val,
                "std_val": std_val,
                "gt_workcenter": r['gt'],
                "ct_workcenter": r['ct'],
                "tu_first_workcenter": r['tu'],
                "tb_first_workcenter": r['tb']
            })

        # 1. 全局加权 CPK (改用合并方差)
        global_avg_cpk = aggregate_node_stats_py(data, global_usl, indicator)["cpk"]

        # 计算全局总产量 (作为分量占比的分母)
        total_tires = sum(p['lot_cnt'] for p in data)
        if total_tires <= 0:
            return None

        cols = ["gt_workcenter", "ct_workcenter", "tu_first_workcenter", "tb_first_workcenter"]

        # 2. 查找活跃层级中的唯一机台
        machines = set()
        for p in data:
            for col in cols:
                if p[col]:
                    machines.add(p[col])

        # 3. 计算机台贡献分析 (改用合并方差)
        machine_list = []
        for mach in machines:
            mach_tires = 0
            matching_rows = []
            partner_groups = {}

            for p in data:
                matched_cols = [col for col in cols if p[col] == mach]
                if matched_cols:
                    mach_tires += p['lot_cnt']
                    matching_rows.append(p)

                    for m_col in matched_cols:
                        partner_parts = [('*' if c == m_col else (p[c] or '*')) for c in cols]
                        partner_key = "_".join(partner_parts)

                        if partner_key not in partner_groups:
                            partner_groups[partner_key] = {
                                "mCol": m_col,
                                "partnerParts": partner_parts,
                                "machTires": 0
                            }
                        partner_groups[partner_key]["machTires"] += p['lot_cnt']

            # 用合并方差公式计算该机台总体的综合 CPK
            mach_avg_cpk = aggregate_node_stats_py(matching_rows, global_usl, indicator)["cpk"] if matching_rows else 0.0

            controlled_baseline_numerator = 0.0
            controlled_baseline_denominator = 0.0

            for group in partner_groups.values():
                m_col = group["mCol"]
                partner_parts = group["partnerParts"]
                group_mach_tires = group["machTires"]

                other_rows = []

                for p in data:
                    if p[m_col] != mach:
                        is_match = True
                        for idx, c in enumerate(cols):
                            if c == m_col:
                                continue
                            if p[c] != partner_parts[idx]:
                                is_match = False
                                break
                        if is_match:
                            other_rows.append(p)

                # 用合并方差公式计算该替代路径下的联合对照基准 CPK (若缺失则默认回退全局均值)
                partner_baseline = aggregate_node_stats_py(other_rows, global_usl, indicator)["cpk"] if other_rows else global_avg_cpk
                controlled_baseline_numerator += partner_baseline * group_mach_tires
                controlled_baseline_denominator += group_mach_tires

            controlled_baseline = (
                controlled_baseline_numerator / controlled_baseline_denominator
                if controlled_baseline_denominator > 0
                else global_avg_cpk
            )

            contribution = mach_avg_cpk - controlled_baseline
            volume = mach_tires / total_tires
            impact_score = contribution * volume

            machine_list.append({
                "machine": mach,
                "impact_score": impact_score
            })

        # 按 impact_score 排序得出最坏机台
        if indicator == "weight":
            # 按 impact_score 降序（最大正的排最前，代表独立拉大偏离最多）
            machine_list.sort(key=lambda x: x["impact_score"], reverse=True)
            if machine_list and machine_list[0]["impact_score"] > 0:
                return machine_list[0]["machine"]
        else:
            # 按 impact_score 升序（最负的最靠前）
            machine_list.sort(key=lambda x: x["impact_score"])
            if machine_list and machine_list[0]["impact_score"] < 0:
                return machine_list[0]["machine"]
        return None
    except Exception as e:
        print(f"Error in calculate_critical_machine: {e}")
        return None



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
        critical_m = calculate_critical_machine(
            article10=article10,
            indicator=indicator,
            start_date=start_date,
            end_date=end_date,
            target_date=target_date,
            min_samples=min_samples
        )
        if critical_m:
            warning_machines[critical_m] = 1.0

        where_parts = ["article10 = ?"]
        params = [article10]
        if target_date:
            where_parts.append("tu_first_shift_date::DATE = ?::DATE")
            params.append(target_date)

        where_clause = "WHERE " + " AND ".join(where_parts)
        if indicator == "weight":
            where_clause += " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"

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

        highlighted_nodes = set()
        highlighted_links = set()

        # 顺序流转 5 列结构 (1: 热准备 -> 2: 裁断 -> 3: 成型GT -> 4: 硫化CT -> 5: 终检TU/TB)
        pairs = [
            # 1. 热准备 (Depth 0) -> 裁断 (Depth 1)
            ("tread_workcenter", "胎面", "first_breaker_workcenter", "带束层1"),
            ("tread_workcenter", "胎面", "second_breaker_workcenter", "带束层2"),
            ("inner_liner_workcenter", "内衬", "first_ply_workcenter", "帘布层1"),
            ("sidewall_workcenter", "胎侧", "wound_cap_ply1_workcenter", "冠带层1"),
            ("bead_workcenter", "胎圈", "wound_cap_ply2_workcenter", "冠带层2"),

            # 2. 裁断 (Depth 1) -> 成型GT (Depth 2)
            ("first_breaker_workcenter", "带束层1", "gt_workcenter", "生胎成型GT"),
            ("second_breaker_workcenter", "带束层2", "gt_workcenter", "生胎成型GT"),
            ("first_ply_workcenter", "帘布层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply1_workcenter", "冠带层1", "gt_workcenter", "生胎成型GT"),
            ("wound_cap_ply2_workcenter", "冠带层2", "gt_workcenter", "生胎成型GT"),

            # 3. 成型GT (Depth 2) -> 硫化CT (Depth 3)
            ("gt_workcenter", "生胎成型GT", "ct_workcenter", "硫化CT"),

            # 4. 硫化CT (Depth 3) -> 终检TU (Depth 4)
            ("ct_workcenter", "硫化CT", "tu_first_workcenter", "终检TU"),

            # 5. 终检TU (Depth 4) -> 终检TB (Depth 4)
            ("tu_first_workcenter", "终检TU", "tb_first_workcenter", "动平衡TB")
        ]

        nodes_set = set()
        links = []

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

        nodes = []
        for n in sorted(list(nodes_set)):
            prefix = n.split("_")[0]
            m_code = n.split("_")[-1]
            d_val = depth_map.get(prefix, 0)
            is_hl = False
            is_max_tu = (n == f"终检TU_{highest_tu_machine}") if highest_tu_machine else False
            is_warn = m_code in warning_machines
            w_score = warning_machines.get(m_code, 0.0)

            col_name = sankey_prefix_to_col.get(prefix)
            
            if indicator == "weight":
                spec_cpk = None
                spec_ratio = None
                spec_avg = None
                if col_name and (col_name, m_code) in machine_cpk_lookup_details:
                    info = machine_cpk_lookup_details[(col_name, m_code)]
                    spec_cpk = abs(info.get("spec_cpk", 0.0))
                    spec_ratio = info.get("spec_cpk", 0.0)
                    spec_avg = info.get("spec_avg", 0.0)
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
                    "spec_avg": round(spec_avg, 2) if spec_avg is not None else None
                })
            else:
                spec_cpk = machine_cpk_lookup_details.get((col_name, m_code), {}).get("spec_cpk") if col_name else None
                nodes.append({
                    "name": n,
                    "machine_code": m_code,
                    "depth": d_val,
                    "is_highlighted": is_hl,
                    "is_max_tu": is_max_tu,
                    "is_warning_machine": is_warn,
                    "warning_score": round(w_score, 2),
                    "spec_cpk": round(spec_cpk, 2) if spec_cpk is not None else None
                })

        return {
            "status": "success",
            "data": {
                "highest_tu_machine": highest_tu_machine,
                "highest_tu_value": round(highest_tu_value, 2),
                "nodes": nodes,
                "links": links
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


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
            for r in tu_rows:
                s_act = float(r['sum_act'])
                s_tar = float(r['sum_tar'])
                r['dev'] = abs((s_act - s_tar) / s_tar * 100.0) if s_tar > 0 else 999.0
            tu_rows.sort(key=lambda x: x['dev'])
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['dev'] if tu_rows else 0.0
        elif indicator == "cony":
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
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['std_v'] if tu_rows else 0.0
        else:
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
            for r in tu_rows:
                avg_v = r['avg_v'] or 0.0
                std_v = r['std_v'] or 0.0
                cpk = (global_usl - avg_v) / (3.0 * std_v) if std_v > 0.0 else 1.33
                r['cpk'] = cpk
            tu_rows.sort(key=lambda x: x['cpk'], reverse=True)
            best_tu_machine = tu_rows[0]['tu_machine'] if tu_rows else None
            best_tu_value = tu_rows[0]['cpk'] if tu_rows else 0.0

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
                    CAST(tb_first_workcenter AS VARCHAR) as tb
                FROM clean_yield
                {where_clause} AND tu_first_workcenter = ?
                GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13
                ORDER BY COUNT(*) DESC
                LIMIT 1
            """
            top_path_rows = qry(path_sql, params + [best_tu_machine])
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

        # 严格限定在当前选定规格 (article10) 下查询流过各机台的实际均值
        node_averages = {}
        for prefix, col_name in sankey_col_map.items():
            extra_f = ""
            if indicator == "weight":
                extra_f = " AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0"
            avg_sql = f"""
                SELECT 
                    CAST({col_name} AS VARCHAR) as mach,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_val
                FROM clean_yield
                WHERE article10 = ? AND {col_name} IS NOT NULL {extra_f}
                GROUP BY 1
            """
            for r in qry(avg_sql, [article10]):
                node_averages[f"{prefix}_{r['mach']}"] = float(r['avg_val']) if r['avg_val'] is not None else 0.0

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

            nodes.append({
                "name": n,
                "machine_code": m_code,
                "depth": d_val,
                "is_best_path": is_best,
                "is_best_tu": is_best_tu,
                "avg_val": round(node_averages.get(n, 0.0), 2)
            })

        return {
            "status": "success",
            "data": {
                "best_tu_machine": best_tu_machine,
                "best_tu_value": round(best_tu_value, 2),
                "nodes": nodes,
                "links": links
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

        # 2. 规格 USL 计算
        if indicator == "weight":
            sql_tw = "SELECT AVG(TRY_CAST(tire_weight_target_first AS DOUBLE)) as target_w FROM clean_yield WHERE article10 = ?"
            res_tw = qry(sql_tw, [article10])
            global_usl = float(res_tw[0]['target_w']) if (res_tw and res_tw[0]['target_w'] is not None) else 12.0
        else:
            global_usl = get_spec_usl(article10, indicator)

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
                    s_cpk = round(max(0.0, min(5.0, (global_usl - s_m) / (3.0 * s_s))), 2) if s_s > 0 else 1.33

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
                        m_cpk = round(max(0.0, min(5.0, (global_usl - m_m) / (3.0 * m_s))), 2) if m_s > 0 else 1.33
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



# ── 7. 自动生成预警建议接口 (根据 min_yield 过滤) ─────────────────────────
# @app.get("/api/insights")
# def get_insights(
#     baseline_from: Optional[str] = Query(None),
#     baseline_to: Optional[str] = Query(None),
#     study_from: Optional[str] = Query(None),
#     study_to: Optional[str] = Query(None),
#     min_yield: int = Query(50),
#     cv_threshold: float = Query(0.3)
# ):
#     try:
#         # 获取补全后的分析周期
#         b_from, b_to, s_from, s_to = get_periods(baseline_from, baseline_to, study_from, study_to)
#         
#         # 计算全局宏观差异
#         sql_overall = """
#             SELECT 
#                 COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
#                 SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                 COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
#                 SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#             FROM clean_yield
#         """
#         overall = qry(sql_overall, [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to])[0]
#         total_b = overall['total_b'] or 0
#         anomalies_b = overall['anomalies_b'] or 0
#         total_s = overall['total_s'] or 0
#         anomalies_s = overall['anomalies_s'] or 0
#         
#         rate_b = round((anomalies_b / total_b * 100), 2) if total_b > 0 else 0.0
#         rate_s = round((anomalies_s / total_s * 100), 2) if total_s > 0 else 0.0
#         delta = round(rate_s - rate_b, 2)
#         
#         study_days = (datetime.strptime(s_to, "%Y-%m-%d") - datetime.strptime(s_from, "%Y-%m-%d")).days + 1
#         
#         # 1. 查询 Top 20 规格
#         sql_overall_yield = """
#             SELECT 
#                 COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_b,
#                 COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_s
#             FROM clean_yield
#             WHERE tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE
#         """
#         overall_stats = qry(sql_overall_yield, [b_from, b_to, s_from, s_to, b_from, s_to])[0]
#         t_s_all = overall_stats['total_s'] or 0
#         t_b_all = overall_stats['total_b'] or 0
# 
#         sql_top_articles = """
#             WITH by_article AS (
#                 SELECT
#                     article10,
#                     COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_b,
#                     SUM(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                     COUNT(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN 1 END) AS total_s,
#                     SUM(CASE WHEN tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#                 FROM clean_yield
#                 WHERE tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE
#                 GROUP BY article10
#                 HAVING total_s > ?
#             )
#             SELECT
#                 article10,
#                 total_s AS total,
#                 anomalies_s AS anomalies,
#                 CASE WHEN total_s > 0 THEN ROUND(CAST(anomalies_s AS DOUBLE) / total_s * 100, 4) ELSE 0 END AS anomaly_rate,
#                 ROUND(
#                     (
#                         (CAST(anomalies_s AS DOUBLE) / NULLIF(?, 0)) - 
#                         (CAST(anomalies_b AS DOUBLE) / NULLIF(?, 0))
#                     ) * 100, 
#                     4
#                 ) AS contribution
#             FROM by_article
#         """
#         art_rows = qry(sql_top_articles, [
#             b_from, b_to,
#             b_from, b_to,
#             s_from, s_to,
#             s_from, s_to,
#             b_from, s_to,
#             min_yield,
#             t_s_all, t_b_all
#         ])
#         art_rows.sort(key=lambda x: abs(x['contribution'] or 0.0), reverse=True)
#         top_articles = art_rows[:10]
# 
#         # 2. 找到工序机台列
#         col_sql = """
#             SELECT column_name
#             FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
#             WHERE column_name LIKE '%workcenter%'
#               AND column_name NOT LIKE 'tu_%'
#               AND column_name NOT LIKE 'tb_%'
#               AND column_name NOT LIKE 'tg_%'
#               AND column_name != 'css_workcenter'
#         """
#         wc_cols = [r["column_name"] for r in qry(col_sql)]
# 
#         spec_issues = []
#         machine_issues = []
#         material_issues = []
# 
#         if top_articles and wc_cols:
#             target_specs = [a['article10'] for a in top_articles]
#             spec_placeholders = ",".join(["?"] * len(target_specs))
#             
#             union_parts = []
#             union_params = []
#             for col in wc_cols:
#                 union_parts.append(f"""
#                     SELECT article10, '{col}' AS workcenter_col, 
#                            CONCAT('{col}', ':', CAST({col} AS VARCHAR)) AS machine,
#                            tu_first_shift_date, grade_anomaly
#                     FROM clean_yield
#                     WHERE article10 IN ({spec_placeholders}) AND {col} IS NOT NULL
#                       AND tu_first_shift_date >= ?::DATE AND tu_first_shift_date <= ?::DATE
#                 """)
#                 union_params += target_specs + [b_from, s_to]
#             
#             union_sql = " UNION ALL ".join(union_parts)
#             
#             sql_by_mach = f"""
#                 WITH melted AS ({union_sql}),
#                 overall_by_art AS (
#                     SELECT 
#                         article10,
#                         COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
#                         SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                         COUNT(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
#                         SUM(CASE WHEN tu_first_shift_date::DATE >= ?::DATE AND tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#                     FROM clean_yield
#                     WHERE article10 IN ({spec_placeholders})
#                     GROUP BY article10
#                 ),
#                 by_machine AS (
#                     SELECT
#                         m.article10,
#                         m.workcenter_col,
#                         m.machine,
#                         COUNT(CASE WHEN m.tu_first_shift_date::DATE >= ?::DATE AND m.tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_b,
#                         SUM(CASE WHEN m.tu_first_shift_date::DATE >= ?::DATE AND m.tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_b,
#                         COUNT(CASE WHEN m.tu_first_shift_date::DATE >= ?::DATE AND m.tu_first_shift_date::DATE <= ?::DATE THEN 1 END) AS total_s,
#                         SUM(CASE WHEN m.tu_first_shift_date::DATE >= ?::DATE AND m.tu_first_shift_date::DATE <= ?::DATE THEN CAST(grade_anomaly AS INT) ELSE 0 END) AS anomalies_s
#                     FROM melted m
#                     GROUP BY m.article10, m.workcenter_col, m.machine
#                     HAVING total_s > ?
#                 )
#                 SELECT
#                     bm.article10,
#                     bm.workcenter_col,
#                     bm.machine,
#                     bm.total_s AS total,
#                     bm.anomalies_s AS anomalies,
#                     bm.total_b,
#                     bm.anomalies_b,
#                     ROUND(
#                         (CAST(bm.anomalies_s AS DOUBLE) / NULLIF(o.anomalies_s, 0)) / 
#                         ((CAST(bm.total_s AS DOUBLE) / NULLIF(o.total_s, 0)) + 1e-8),
#                         4
#                     ) AS step_lift
#                 FROM by_machine bm
#                 JOIN overall_by_art o ON bm.article10 = o.article10
#             """
#             
#             mach_params = (
#                 union_params + 
#                 [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to] + 
#                 target_specs + 
#                 [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to, min_yield]
#             )
#             
#             raw_mach_rows = qry(sql_by_mach, mach_params)
#             
#             for r in raw_mach_rows:
#                 raw_m = r['machine']
#                 if ':' in raw_m:
#                     r['machine'] = raw_m.split(':', 1)[1]
# 
#             machines_by_spec = {}
#             for r in raw_mach_rows:
#                 spec = r['article10']
#                 if spec not in machines_by_spec:
#                     machines_by_spec[spec] = []
#                 machines_by_spec[spec].append(r)
# 
#             for art_item in top_articles:
#                 art_name = art_item['article10']
#                 mach_list = machines_by_spec.get(art_name, [])
#                 
#                 # 1. 降序排序并截取 Top 20，对齐前端展示口径
#                 mach_list.sort(key=lambda x: x['step_lift'] or 0.0, reverse=True)
#                 mach_list_top20 = mach_list[:20]
#                 
#                 # 5. 小样本保护：若机台数 <= 1，直接跳过该规格，不生成任何警报
#                 if len(mach_list_top20) <= 1:
#                     continue
#                     
#                 lifts = [m['step_lift'] or 0.0 for m in mach_list_top20]
#                 mean_mach = sum(lifts) / len(lifts)
#                 if mean_mach == 0.0:
#                     cv_mach = 0.0
#                 else:
#                     std_mach = float(np.std(lifts, ddof=0))
#                     cv_mach = std_mach / mean_mach
#                     
#                 # 引入混合判定逻辑
#                 max_lift = max(lifts) if lifts else 0.0
#                 if cv_mach < cv_threshold and max_lift < 1.2:
#                     spec_issues.append(art_name)
#                 else:
#                     # 2. 定位异常机台：使用四分位数，并加入绝对门槛 step_lift >= 1.2 防止误判
#                     q3_mach = float(np.percentile(lifts, 75))
#                     candidate_machs = [
#                         m for m in mach_list_top20 
#                         if (m['step_lift'] or 0.0) >= q3_mach 
#                         and (m['step_lift'] or 0.0) >= 1.2 
#                         and m['anomalies'] >= 3
#                     ]
#                     
#                     # 3. 超过 3 个机台时，计算相邻差值进行假异常排除，限制至多只输出 Top 3
#                     if len(candidate_machs) > 3:
#                         candidate_machs.sort(key=lambda x: x['step_lift'] or 0.0, reverse=True)
#                         l1 = candidate_machs[0]['step_lift'] or 0.0
#                         l2 = candidate_machs[1]['step_lift'] or 0.0
#                         l3 = candidate_machs[2]['step_lift'] or 0.0
#                         
#                         diff_threshold = 0.5
#                         if (l1 - l2) >= diff_threshold:
#                             # 第一名显著高，后两名为假异常，仅保留 Top 1
#                             outlier_machs = candidate_machs[:1]
#                         elif (l2 - l3) >= diff_threshold:
#                             # 前两名均高但第三名显著低，仅保留 Top 2
#                             outlier_machs = candidate_machs[:2]
#                         else:
#                             # 前三名相差不大，保留 Top 3
#                             outlier_machs = candidate_machs[:3]
#                     else:
#                         outlier_machs = candidate_machs
#                     
#                     for outlier_m in outlier_machs:
#                         m_name = outlier_m['machine']
#                         wc_col = outlier_m['workcenter_col']
#                         m_lift = outlier_m['step_lift']
#                         
#                         lot_col = LOT_MAP.get(wc_col)
#                         if not lot_col:
#                             machine_issues.append({
#                                 "article10": art_name,
#                                 "workcenter_col": wc_col,
#                                 "machine": m_name,
#                                 "step_lift": m_lift
#                             })
#                             continue
#                             
#                         m_spec_total = outlier_m['total'] or 0
#                         m_spec_anoms = outlier_m['anomalies'] or 0
#                         
#                         if m_spec_total == 0 or m_spec_anoms == 0:
#                             machine_issues.append({
#                                 "article10": art_name,
#                                 "workcenter_col": wc_col,
#                                 "machine": m_name,
#                                 "step_lift": m_lift
#                             })
#                             continue
#                             
#                         lot_sql = f"""
#                             SELECT 
#                                 {lot_col} as lot_val,
#                                 COUNT(*) as lot_total,
#                                 SUM(CAST(grade_anomaly AS INT)) as lot_anomaly
#                             FROM clean_yield
#                             WHERE article10 = ? AND {wc_col} = ?
#                               AND tu_first_shift_date::DATE >= ?::DATE
#                               AND tu_first_shift_date::DATE <= ?::DATE
#                               AND {lot_col} IS NOT NULL
#                             GROUP BY {lot_col}
#                             HAVING lot_total >= 30 AND lot_anomaly >= 5
#                         """
#                         lots = qry(lot_sql, [art_name, m_name, s_from, s_to])
#                         
#                         # 5. 小样本保护：若符合门槛的物料批次样本数 <= 1，退化判定为机台本身问题
#                         if len(lots) <= 1:
#                             machine_issues.append({
#                                 "article10": art_name,
#                                 "workcenter_col": wc_col,
#                                 "machine": m_name,
#                                 "step_lift": m_lift
#                             })
#                             continue
#                             
#                         lot_lifts = []
#                         lot_data_list = []
#                         for l in lots:
#                             lot_val = l['lot_val']
#                             lot_total = l['lot_total']
#                             lot_anom = l['lot_anomaly']
#                             l_lift = (lot_anom / lot_total) / (m_spec_anoms / m_spec_total)
#                             lot_lifts.append(l_lift)
#                             lot_data_list.append({
#                                 "lot_val": lot_val,
#                                 "local_lift": l_lift
#                             })
#                             
#                         mean_lot = sum(lot_lifts) / len(lot_lifts)
#                         if mean_lot == 0.0:
#                             cv_lot = 0.0
#                         else:
#                             std_lot = float(np.std(lot_lifts, ddof=0))
#                             cv_lot = std_lot / mean_lot
#                             
#                         if cv_lot < cv_threshold:
#                             machine_issues.append({
#                                 "article10": art_name,
#                                 "workcenter_col": wc_col,
#                                 "machine": m_name,
#                                 "step_lift": m_lift
#                             })
#                         else:
#                             q3_lot = float(np.percentile(lot_lifts, 75))
#                             for ld in lot_data_list:
#                                 if ld['local_lift'] >= q3_lot and ld['local_lift'] >= 1.2:
#                                     material_issues.append({
#                                         "article10": art_name,
#                                         "workcenter_col": wc_col,
#                                         "machine": m_name,
#                                         "lot_val": ld['lot_val'],
#                                         "local_lift": ld['local_lift']
#                                     })
# 
#         alerts = []
#         
#         # 1. 整体分析报告 (恒为 info 绿色)
#         overall_detail = f"研究期排产 {total_s:,} 条，质量异常 {anomalies_s:,} 条，分析时间为 {study_days} 天。基准期异常率 {rate_b}% → 研究期异常率 {rate_s}%（较基准期波动了 {delta:+.2f} 百分点）"
#         alerts.append({
#             "level": "info",
#             "category": "overall",
#             "title": "生产期整体质量分析报告",
#             "detail": overall_detail
#         })
#         
#         # 2. 规格预警卡片
#         if spec_issues:
#             spec_names_str = " ".join([f"[{name}]" for name in spec_issues])
#             spec_detail = f"{spec_names_str} 存在规格缺陷"
#             spec_level = "high"
#         else:
#             spec_detail = "未检测到异常规格"
#             spec_level = "info"
#         alerts.append({
#             "level": spec_level,
#             "category": "article",
#             "title": "规格预警",
#             "detail": spec_detail
#         })
#         
#         # 3. 机台预警卡片
#         if machine_issues:
#             # Group by article10
#             mach_by_spec = {}
#             for mi in machine_issues:
#                 spec = mi['article10']
#                 wc_clean = mi['workcenter_col'].replace('_workcenter', '').upper()
#                 mach_name = f"{wc_clean}:{mi['machine']}"
#                 lift_str = f"{mi['step_lift']}x"
#                 if spec not in mach_by_spec:
#                     mach_by_spec[spec] = []
#                 mach_by_spec[spec].append(f"{mach_name}({lift_str})")
#             
#             machine_details_list = []
#             for spec, machs in mach_by_spec.items():
#                 machine_details_list.append(f"[{spec}]: {', '.join(machs)}")
#             machine_detail = "；".join(machine_details_list)
#             machine_level = "high"
#         else:
#             machine_detail = "未检测到异常机台"
#             machine_level = "info"
#         alerts.append({
#             "level": machine_level,
#             "category": "machine",
#             "title": "机台预警",
#             "detail": machine_detail
#         })
#         
#         # 4. 物料预警卡片
#         if material_issues:
#             # Group by article10, then by machine
#             mat_by_spec = {}
#             for mi in material_issues:
#                 spec = mi['article10']
#                 wc_clean = mi['workcenter_col'].replace('_workcenter', '').upper()
#                 mach_name = f"{wc_clean}:{mi['machine']}"
#                 lot_info = f"批次 {mi['lot_val']}({mi['local_lift']:.2f}x)"
#                 
#                 if spec not in mat_by_spec:
#                     mat_by_spec[spec] = {}
#                 if mach_name not in mat_by_spec[spec]:
#                     mat_by_spec[spec][mach_name] = []
#                 mat_by_spec[spec][mach_name].append(lot_info)
#             
#             material_details_list = []
#             for spec, machs_dict in mat_by_spec.items():
#                 mach_parts = []
#                 for mach_name, lots in machs_dict.items():
#                     mach_parts.append(f"在机台 {mach_name} 上 {', '.join(lots)}")
#                 material_details_list.append(f"[{spec}]: {'；'.join(mach_parts)}")
#             material_detail = "；".join(material_details_list)
#             material_level = "high"
#         else:
#             material_detail = "未检测到异常物料"
#             material_level = "info"
#         alerts.append({
#             "level": material_level,
#             "category": "material",
#             "title": "物料预警",
#             "detail": material_detail
#         })
# 
#         return {
#             "status": "success", 
#             "data": {
#                 "overall": {
#                     "baseline_rate_pct": rate_b, 
#                     "study_rate_pct": rate_s, 
#                     "delta_pct": delta, 
#                     "total_baseline": total_b, 
#                     "total_study": total_s
#                 }, 
#                 "alerts": alerts
#             }
#         }
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 8. 诊断：嫌疑机台清单与自动诊断接口 (KMeans) ─────────────
# @app.get("/api/diagnose/suspects")
# def get_suspects(
#     study_from: str,
#     study_to: str,
#     article10: Optional[str] = Query(None),
#     lift_threshold: float = Query(1.5),
#     min_yield: int = Query(50)
# ):
#     try:
#         b_from, b_to, s_from, s_to = get_periods(None, None, study_from, study_to)
#         suspects, _ = get_kmeans_diagnostics(db_conn, s_from, s_to, b_from, b_to, article10, min_yield, lift_threshold)
#         
#         for r in suspects:
#             diag, _ = diagnose_machine(r['machine'], r['workcenter_col'], s_from, s_to)
#             r['diagnosis'] = diag
#             
#         return {"status": "success", "data": suspects}
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 9. 诊断：双机台路径联合提升接口 (KMeans) ──────────────
# @app.get("/api/diagnose/combinations")
# def get_joint_combinations(
#     study_from: str,
#     study_to: str,
#     article10: Optional[str] = Query(None),
#     min_matches: int = Query(50),
#     limit: int = Query(10),
#     min_yield: int = Query(50)
# ):
#     try:
#         b_from, b_to, s_from, s_to = get_periods(None, None, study_from, study_to)
#         _, combinations = get_kmeans_diagnostics(db_conn, s_from, s_to, b_from, b_to, article10, min_yield, 1.5)
#         
#         # Filter combinations by min_matches and limit
#         filtered = [c for c in combinations if c['total_matches'] >= min_matches]
#         return {"status": "success", "data": filtered[:limit]}
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 9.5 诊断：工艺路径聚类对比接口 (KMeans) ──────────────────
# @app.get("/api/diagnose/paths")
# def get_paths(
#     baseline_from: Optional[str] = Query(None),
#     baseline_to: Optional[str] = Query(None),
#     study_from: Optional[str] = Query(None),
#     study_to: Optional[str] = Query(None),
#     min_yield: int = Query(50)
# ):
#     try:
#         b_from, b_to, s_from, s_to = get_periods(baseline_from, baseline_to, study_from, study_to)
#         paths_data = get_kmeans_paths(db_conn, s_from, s_to, b_from, b_to, min_yield)
#         return {"status": "success", "data": sanitize_data(paths_data)}
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"status": "error", "message": str(e)}
# 
# 
# ── 10. 诊断：批次诊断接口 (限制机台内 Lot 排产 >= 30) ──────────────────
# @app.get("/api/diagnose/lots")
# def get_lot_diagnosis(
#     study_from: str,
#     study_to: str,
#     machine: str,
#     workcenter_col: str,
#     min_total: int = Query(30),
#     min_anomaly: int = Query(5),
#     limit: int = Query(10),
# ):
#     try:
#         # Whitelist dynamic col check
#         if workcenter_col not in LOT_MAP:
#             return {"status": "error", "message": "无对应物理列或列名非法"}
# 
#         lot_col = LOT_MAP.get(workcenter_col)
#         if not lot_col:
#             return {"status": "success", "message": "该工序工位无对应原材料物料批次数据", "data": []}
# 
#         # 1. 机台 M 的整体数据
#         m_sql = f"""
#             SELECT 
#                 COUNT(*) as total,
#                 SUM(CAST(grade_anomaly AS INT)) as anomalies
#             FROM clean_yield
#             WHERE {workcenter_col} = ?
#               AND tu_first_shift_date::DATE >= ?::DATE
#               AND tu_first_shift_date::DATE <= ?::DATE
#         """
#         m_stats = qry(m_sql, [machine, study_from, study_to])[0]
#         m_total = m_stats['total'] or 0
#         m_anomalies = m_stats['anomalies'] or 0
#         if m_total == 0 or m_anomalies == 0:
#             return {"status": "success", "data": []}
# 
#         # 2. 查询该机台下每个 Lot 在研究期的数据
#         lot_sql = f"""
#             SELECT 
#                 {lot_col} as lot_val,
#                 COUNT(*) as lot_total,
#                 SUM(CAST(grade_anomaly AS INT)) as lot_anomaly
#             FROM clean_yield
#             WHERE {workcenter_col} = ?
#               AND tu_first_shift_date::DATE >= ?::DATE
#               AND tu_first_shift_date::DATE <= ?::DATE
#               AND {lot_col} IS NOT NULL
#             GROUP BY {lot_col}
#             HAVING lot_total >= ? AND lot_anomaly >= ?
#         """
#         lots = qry(lot_sql, [machine, study_from, study_to, min_total, min_anomaly])
#         results = []
#         for l in lots:
#             lot_val = l['lot_val']
#             lot_total = l['lot_total']
#             lot_anomaly = l['lot_anomaly']
#             lot_rate = (lot_anomaly / lot_total) * 100
#             
#             # Local Lift
#             local_lift = (lot_anomaly / lot_total) / (m_anomalies / m_total)
# 
#             # Global Lot metrics (Cross-Machine)
#             g_sql = f"""
#                 SELECT 
#                     COUNT(*) as g_total,
#                     SUM(CAST(grade_anomaly AS INT)) as g_anomaly
#                 FROM clean_yield
#                 WHERE {lot_col} = ?
#                   AND tu_first_shift_date::DATE >= ?::DATE
#                   AND tu_first_shift_date::DATE <= ?::DATE
#             """
#             g_stats = qry(g_sql, [lot_val, study_from, study_to])[0]
#             g_total = g_stats['g_total'] or 0
#             g_anomaly = g_stats['g_anomaly'] or 0
#             
#             cross_lift = 1.0
#             if g_total > 0 and g_anomaly > 0:
#                 cross_lift = (lot_anomaly / lot_total) / (g_anomaly / g_total)
#             
#             # 自动诊断判断
#             if local_lift > 1.5 and cross_lift > 1.5:
#                 diag = "机台-批次适配性故障"
#                 sugg = "建议微调该机台该特定物理批次的加工张力/温度参数"
#             elif local_lift > 1.5 and cross_lift <= 1.5:
#                 diag = "全局物料批次缺陷"
#                 sugg = "批次在各机台异常率均偏高，原材料存在自身缺陷，建议封存批次"
#             else:
#                 diag = "设备系统性工艺漂移"
#                 sugg = "批次在该机台异常率与平均持平但整体偏高，建议停机精度校验"
# 
#             results.append({
#                 "lot_col": lot_col,
#                 "lot_val": lot_val,
#                 "lot_total": lot_total,
#                 "lot_anomaly": lot_anomaly,
#                 "lot_anomaly_rate": round(lot_rate, 2),
#                 "local_lift": round(local_lift, 2),
#                 "cross_machine_lift": round(cross_lift, 2),
#                 "diagnosis": diag,
#                 "suggestion": sugg
#             })
# 
#         results.sort(key=lambda x: x['local_lift'], reverse=True)
#         return {"status": "success", "data": results[:limit]}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
# 
# 
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
                MIN(tu_first_shift_date)::DATE AS date_min,
                MAX(tu_first_shift_date)::DATE AS date_max
            FROM clean_yield
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
    grain: str = Query("daily"),     # "daily" | "weekly"
    article10: Optional[str] = Query(None),
    exclude_articles: Optional[str] = Query(None) # 英文逗号分割的需剔除规格代码列表
):
    try:
        # Select time expression
        if grain == "daily":
            time_expr = "tu_first_shift_date::DATE"
        else:
            time_expr = "DATE_TRUNC('week', tu_first_shift_date::DATE)"

        exclude_clause = ""
        exclude_params = []
        if exclude_articles:
            ex_list = [x.strip() for x in exclude_articles.split(",") if x.strip()]
            if ex_list:
                placeholders = ",".join(["?"] * len(ex_list))
                exclude_clause = f" AND article10 NOT IN ({placeholders})"
                exclude_params = ex_list

        if article10:
            # 单规格：池化计算，直接计算均值与标准差，不区分 group，不加权
            sql = f"""
                WITH spec_daily_stats AS (
                    SELECT
                        {time_expr} AS time_period,
                        article10,
                        COUNT(*) AS sample_size,
                        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
                        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
                        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
                        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
                        AVG(TRY_CAST(cony_first AS DOUBLE)) AS avg_cony,
                        STDDEV(TRY_CAST(cony_first AS DOUBLE)) AS std_cony,
                        SUM(CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
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
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      AND tu_first_shift_date IS NOT NULL
                      AND article10 = ?
                    GROUP BY 1, 2
                    HAVING COUNT(*) >= 10
                )
                SELECT
                    time_period,
                    sample_size AS total_n,
                    CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS weighted_cpk_rfpp,
                    CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS weighted_cpk_rfh1,
                    avg_cony AS weighted_avg_cony,
                    (sum_act_w - sum_tar_w) / NULLIF(sum_tar_w, 0.0) * 100.0 as weighted_diff_weight
                FROM spec_daily_stats
                ORDER BY 1
            """
            params = [article10]
        else:
            # 全厂综合：各规格按生产组别计算独立 CPK，然后通过日产量加权平均
            sql = f"""
                WITH spec_daily_stats AS (
                    SELECT
                        {time_expr} AS time_period,
                        "group",
                        article10,
                        COUNT(*) AS sample_size,
                        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
                        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
                        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
                        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
                        AVG(TRY_CAST(cony_first AS DOUBLE)) AS avg_cony,
                        STDDEV(TRY_CAST(cony_first AS DOUBLE)) AS std_cony,
                        SUM(CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
                        COALESCE(ANY_VALUE(standard_rfpp), 
                                 CASE "group" 
                                     WHEN 'GROUP 1'  THEN 10.5 
                                     WHEN 'GROUP 2A' THEN 11.5 
                                     WHEN 'GROUP 2B' THEN 12.5 
                                     WHEN 'GROUP 3'  THEN 12.5 
                                 END) * 10.0 AS usl_rfpp,
                        COALESCE(ANY_VALUE(standard_rfh1), 
                                 CASE "group" 
                                     WHEN 'GROUP 1'  THEN 7.5 
                                     WHEN 'GROUP 2A' THEN 8.5 
                                     WHEN 'GROUP 2B' THEN 9.0 
                                     WHEN 'GROUP 3'  THEN 9.5 
                                 END) * 10.0 AS usl_rfh1
                    FROM clean_yield
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      AND tu_first_shift_date IS NOT NULL
                      {exclude_clause}
                    GROUP BY 1, 2, 3
                    HAVING COUNT(*) >= 10
                ),
                spec_cpk AS (
                    SELECT
                        time_period,
                        sample_size,
                        CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp,
                        CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS cpk_rfh1,
                        avg_cony,
                        sum_act_w,
                        sum_tar_w
                    FROM spec_daily_stats
                )
                SELECT
                    time_period,
                    SUM(sample_size) AS total_n,
                    SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfpp,
                    SUM(cpk_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfh1,
                    SUM(avg_cony * sample_size) / SUM(sample_size) AS weighted_avg_cony,
                    (SUM(sum_act_w) - SUM(sum_tar_w)) / NULLIF(SUM(sum_tar_w), 0.0) * 100.0 as weighted_diff_weight
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

        for r in rows:
            p_str = str(r['time_period'])
            idx = period_idx[p_str]

            cpk_rfpp = r['weighted_cpk_rfpp']
            cpk_rfh1 = r['weighted_cpk_rfh1']
            avg_cony = r['weighted_avg_cony']
            avg_weight = r['weighted_diff_weight']

            if cpk_rfpp is not None and not (np.isnan(cpk_rfpp) or np.isinf(cpk_rfpp)):
                cpk_trends["RFPP 综合 CPK"][idx] = round(float(cpk_rfpp), 4)
            if cpk_rfh1 is not None and not (np.isnan(cpk_rfh1) or np.isinf(cpk_rfh1)):
                cpk_trends["RFH1 综合 CPK"][idx] = round(float(cpk_rfh1), 4)
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
                "cpk_trends": cpk_trends
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 静态文件托管 (必须放在所有 API 路由之后注册，否则会拦截 /api 请求) ──
import sys
from fastapi.staticfiles import StaticFiles
if getattr(sys, 'frozen', False):
    _static_base = sys._MEIPASS
else:
    _static_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIST = os.path.join(_static_base, "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
