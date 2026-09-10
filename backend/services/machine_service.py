# -*- coding: utf-8 -*-
"""
机台质量分析服务模块 (Machine Service)
包含各机台 CPK 计算、历史趋势下钻、Top3 负贡献排行分析、最优 TU 计算及多机台对比分析
"""
from typing import Optional, List, Dict, Any, Tuple
import os
import sys
import json
import math
import traceback
from datetime import datetime, timedelta
import numpy as np

from backend.core.db import qry
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl
from backend.core.serializer import sanitize_data
from backend.core.time_utils import build_production_time_where, get_phase_sql_condition

# CGRS 计算回调钩子 (解耦同层服务间 import，由路由层或运行时动态注入)
_cgrs_cpk_comparator = None

def set_cgrs_comparator(func):
    """设置 CGRS 比较分析计算引擎"""
    global _cgrs_cpk_comparator
    _cgrs_cpk_comparator = func

def _get_cgrs_comparator():
    global _cgrs_cpk_comparator
    if _cgrs_cpk_comparator is None:
        import sys
        mod = sys.modules.get("backend.services.cgrs_service")
        if mod:
            _cgrs_cpk_comparator = getattr(mod, "calculate_cgrs_cpk_comparison", None)
    return _cgrs_cpk_comparator

def get_machine_cpk(
    target_date: str,
    article10: str,
    indicator: str = "rfpp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 10,
    tolerance: float = 0.8,
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




def get_machine_cpk_trend(
    machine: str,
    workcenter_col: str,
    indicator: str = "rfpp",
    article10: Optional[str] = None,
    mode: Optional[str] = None,
    tolerance: float = 0.8
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





def aggregate_node_stats_py(rows, usl, indicator="rfpp", lsl=None):
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




def get_top_warning(
    spec: str,
    indicator: str = "rfpp",
    target_date: str = None,
    n: int = 3,
    days: int = 3,
    min_samples: int = 1
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



def get_best_tu(
    article10: str,
    indicator: str = "rfpp",
    min_samples: int = 10
):
    best_tu_mach, best_val = get_best_tu_machine_for_spec(article10, indicator, min_samples)
    return {
        "status": "success",
        "data": {
            "best_tu_machine": best_tu_mach,
            "best_tu_value": best_val,
        }
    }



def get_cpk_trend_comparison(
    workcenter_type: str = "gt",
    machines: str = "",
    article10: str = "",
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    days: int = 14,
    min_samples: int = 3
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
            _cgrs_calc = _get_cgrs_comparator()
            cgrs_comp = _cgrs_calc(
                workcenter=mach,
                article10=article10,
                target_date=target_date,
                indicator=indicator,
                limit_n=20
            ) if _cgrs_calc else {"has_cgrs": False, "events_count": 0, "events": []}
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






# 业务纯函数命名映射与别名兼容
get_machines_cpk = get_machine_cpk
get_top_warning_api = get_top_warning
get_best_tu_api = get_best_tu
get_machine_cpk_trend_comparison = get_cpk_trend_comparison
