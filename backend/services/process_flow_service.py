# -*- coding: utf-8 -*-
"""
工序全流程分析服务模块 (Process Flow Service)
包含 13 道工序静态拓扑字典 WORKCENTER_STAGES、机台组合树分析、全流程工序桑基图与最优工序路径流转分析
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
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl, INDICATORS_SPEC
from backend.core.serializer import sanitize_data
from backend.core.time_utils import build_production_time_where, get_phase_sql_condition

# 13 道关键工段拓扑映射静态配置表 (与桑基图节点映射逐字段对齐，严禁随意改名)
WORKCENTER_STAGES = [
    {"key": "tread",       "col": "tread_workcenter",           "name": "胎面"},
    {"key": "bead",        "col": "bead_workcenter",            "name": "胎圈"},
    {"key": "inner_liner", "col": "inner_liner_workcenter",     "name": "内衬"},
    {"key": "sidewall",    "col": "sidewall_workcenter",        "name": "胎侧"},
    {"key": "breaker1",    "col": "first_breaker_workcenter",   "name": "带束层1"},
    {"key": "breaker2",    "col": "second_breaker_workcenter",  "name": "带束层2"},
    {"key": "ply1",        "col": "first_ply_workcenter",       "name": "帘布层1"},
    {"key": "cap1",        "col": "wound_cap_ply1_workcenter",  "name": "冠带层1"},
    {"key": "cap2",        "col": "wound_cap_ply2_workcenter",  "name": "冠带层2"},
    {"key": "gt",          "col": "gt_workcenter",              "name": "成型"},
    {"key": "ct",          "col": "ct_workcenter",              "name": "硫化"},
    {"key": "tu",          "col": "tu_first_workcenter",        "name": "终检"},
    {"key": "tb",          "col": "tb_first_workcenter",        "name": "动平衡"},
]

# 解耦同层服务间 import 的运行时动态提供者钩子
_top_warning_provider = None
_best_tu_provider = None
_cgrs_cpk_comparator = None
_machine_cpk_provider = None

def set_process_flow_helpers(top_warning_provider=None, best_tu_provider=None, cgrs_comparator=None, machine_cpk_provider=None):
    """注入跨服务计算能力 (由路由层或系统启动时组装)"""
    global _top_warning_provider, _best_tu_provider, _cgrs_cpk_comparator, _machine_cpk_provider
    if top_warning_provider:
        _top_warning_provider = top_warning_provider
    if best_tu_provider:
        _best_tu_provider = best_tu_provider
    if cgrs_comparator:
        _cgrs_cpk_comparator = cgrs_comparator
    if machine_cpk_provider:
        _machine_cpk_provider = machine_cpk_provider

def _get_machine_cpk_provider():
    global _machine_cpk_provider
    if _machine_cpk_provider is None:
        import sys
        mod = sys.modules.get("backend.services.machine_service")
        if mod:
            _machine_cpk_provider = getattr(mod, "get_machine_cpk", None)
    return _machine_cpk_provider

def _get_top_warning_provider():
    global _top_warning_provider
    if _top_warning_provider is None:
        import sys
        mod = sys.modules.get("backend.services.machine_service")
        if mod:
            _top_warning_provider = getattr(mod, "get_top_warning_machines", None)
    return _top_warning_provider

def _get_best_tu_provider():
    global _best_tu_provider
    if _best_tu_provider is None:
        import sys
        mod = sys.modules.get("backend.services.machine_service")
        if mod:
            _best_tu_provider = getattr(mod, "get_best_tu_machine_for_spec", None)
    return _best_tu_provider

def _get_cgrs_comparator():
    global _cgrs_cpk_comparator
    if _cgrs_cpk_comparator is None:
        import sys
        mod = sys.modules.get("backend.services.cgrs_service")
        if mod:
            _cgrs_cpk_comparator = getattr(mod, "calculate_cgrs_cpk_comparison", None)
    return _cgrs_cpk_comparator

def get_machine_combination_tree(
    spec: str,
    start_wc: Optional[str] = None,
    end_wc: Optional[str] = None,
    indicator: str = "rfpp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_date: Optional[str] = None,
    min_samples: int = 10,
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

        spec_cfg = INDICATORS_SPEC.get(indicator, INDICATORS_SPEC["rfpp"])
        if indicator == "weight":
            indicator_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        else:
            indicator_col = spec_cfg["col"]

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



def get_process_sankey(
    article10: str,
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 10,
    tolerance: float = 0.8
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

        spec_cfg = INDICATORS_SPEC.get(indicator, INDICATORS_SPEC["rfpp"])
        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        else:
            ind_col = spec_cfg["col"]
        
        warning_machines = {}
        machine_cpk_lookup_details = {}
        if target_date:
            _m_cpk_fn = _get_machine_cpk_provider()
            if _m_cpk_fn:
                cpk_res = _m_cpk_fn(
                    target_date=target_date,
                    article10=article10,
                    indicator=indicator,
                    start_date=start_date,
                    end_date=end_date,
                    min_samples=1,
                    tolerance=tolerance
                )
            else:
                cpk_res = {}
            if cpk_res.get("status") == "success":
                cpk_data = cpk_res.get("data", {})
                for wc_label, m_list in cpk_data.items():
                    for m_info in m_list:
                        m_name = str(m_info.get("machine"))
                        col_name = str(m_info.get("workcenter_col"))
                        machine_cpk_lookup_details[(col_name, m_name)] = m_info

        # 基于方案一（全局机台贡献分析）计算决策树中最核心负面影响机台并标红
        _tw = _get_top_warning_provider()
        top_warn_list = _tw(
            n=10,
            article10=article10,
            indicator=indicator,
            start_date=start_date,
            end_date=end_date,
            target_date=target_date,
            min_samples=min_samples
        ) if _tw else []
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
                _cc = _get_cgrs_comparator()
                cgrs_comp = _cc(
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



def get_best_process_sankey(
    article10: str,
    indicator: str = "rfpp",
    min_samples: int = 10,
):
    try:
        spec_cfg = INDICATORS_SPEC.get(indicator, INDICATORS_SPEC["rfpp"])
        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        else:
            ind_col = spec_cfg["col"]
        where_clause = "WHERE article10 = ?"
        params = [article10]

        global_usl = get_spec_usl(article10, indicator)

        _bt = _get_best_tu_provider()
        best_tu_machine, best_tu_value = _bt(article10, indicator, min_samples) if _bt else (None, None)
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







# 业务纯函数命名映射与别名兼容
get_machine_process_sankey = get_process_sankey
get_machine_best_process_sankey = get_best_process_sankey
