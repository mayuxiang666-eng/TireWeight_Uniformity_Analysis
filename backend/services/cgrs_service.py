# -*- coding: utf-8 -*-
"""
CGRS 工艺调参分析与智能推荐服务模块 (CGRS Service)
包含 CGRS 调参记录检索、受控变量时序对照分析、单机台推荐与全厂双工段最佳扫描推荐
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
from backend.core.cache_utils import (
    recommend_cache_key,
    recommend_cache_get,
    recommend_cache_set,
    _recommend_cache_key,
    _recommend_cache_get,
    _recommend_cache_set
)
from backend.core.time_utils import build_production_time_where, get_phase_sql_condition

def get_cgrs_records(
    workcenter: str,
    date: Optional[str] = None,
    article: Optional[str] = None,
    indicator: Optional[str] = "rfpp",
    event_time: Optional[str] = None
):
    """根据成型机台编号、日期以及规格代码查询 CGRS 参数修改记录（支持按精确调参时间戳定位，支持精确匹配与一段/二段机台编号兼容映射、规格7位/10位代码兼容匹配，并附带修改前后 50 条 CPK 对比数据）"""
    try:
        if hasattr(workcenter, "default"):
            workcenter = workcenter.default if workcenter.default is not ... else ""
        if hasattr(date, "default"):
            date = date.default if date.default is not ... else ""
        if hasattr(article, "default"):
            article = article.default if article.default is not ... else None
        if hasattr(indicator, "default"):
            indicator = indicator.default if indicator.default is not ... else "rfpp"
        if hasattr(event_time, "default"):
            event_time = event_time.default if event_time.default is not ... else None
        
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

        # 若提供了精确的调参时间戳，直接定位该次调参事件记录（无需依赖 TU 完检日期）
        if event_time and str(event_time).strip():
            ev_ts_clean = str(event_time).strip()
            sql_ev = f"""
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
                  AND abs(epoch(TRY_CAST(event_timestamp AS TIMESTAMP)) - epoch(?::TIMESTAMP)) <= 600
            """
            params_ev = list(cgrs_candidates) + [ev_ts_clean]
            if not is_cu and article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                sql_ev += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ? OR RecipeDescription LIKE ?)"
                params_ev.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%", f"%{prefix7}%"])
            elif is_cu and article and article.strip():
                art_clean = article.strip()
                prefix7 = art_clean[:7]
                sql_ev += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
                params_ev.extend([prefix7, f"%{prefix7}%"])
            sql_ev += " ORDER BY event_timestamp DESC, TechOffsetHistoryLocalDate DESC"
            try:
                ev_rows = qry(sql_ev, params_ev)
            except Exception:
                ev_rows = []

            # 计算基准日期对比
            target_calc_date = date or ev_ts_clean[:10]
            comparison = calculate_cgrs_cpk_comparison(
                workcenter=workcenter,
                article10=article,
                target_date=target_calc_date,
                indicator=indicator or "rfpp",
                limit_n=20
            )
            return {
                "status": "success",
                "data": sanitize_data(ev_rows),
                "comparison": sanitize_data(comparison),
                "meta": {
                    "workcenter": workcenter,
                    "date": target_calc_date,
                    "event_time": ev_ts_clean,
                    "article": article,
                    "indicator": indicator,
                    "count": len(ev_rows),
                    "matched_candidates": cgrs_candidates
                }
            }
        
        # 常规模式：按当天 TU 终检轮胎的成型(GT)/硫化(CT)生产时间区间 [min_time, max_time] 圈定调参
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
        elif is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            sql += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
            params.extend([prefix7, f"%{prefix7}%"])
        
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



def compute_cgrs_controlled_analysis_data(
    workcenter: str,
    date: Optional[str] = None,
    article: Optional[str] = None,
    indicator: str = "rfpp",
    top_machines: Optional[str] = None,
    same_day_only: bool = False,
    limit_per_path: int = 20,
    min_samples_threshold: int = 1,
    event_time: Optional[str] = None
):
    """
    成型机 CGRS 控制变量分析核心计算引擎（成型 GT ➔ 硫化 CT ➔ 终检 TU 全流程路径拆分与有效路径加总 CPK 对照，支持按精确调参时间戳直接锚定）
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

    # 若提供了精确的调参时间戳 event_time，直接按该次调参事件检索（解除 TU 终检完检日期强绑定）
    if event_time and str(event_time).strip():
        same_day_only = False
        ev_ts_clean = str(event_time).strip()
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
              AND abs(epoch(TRY_CAST(event_timestamp AS TIMESTAMP)) - epoch(?::TIMESTAMP)) <= 600
        """
        cgrs_params = list(cgrs_candidates) + [ev_ts_clean]
        if not is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            cgrs_sql += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ?)"
            cgrs_params.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%"])
        elif is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            cgrs_sql += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
            cgrs_params.extend([prefix7, f"%{prefix7}%"])
        cgrs_sql += " ORDER BY event_timestamp DESC, TechOffsetHistoryLocalDate DESC"
        try:
            cgrs_rows = qry(cgrs_sql, cgrs_params)
        except Exception:
            cgrs_rows = []

        if not cgrs_rows:
            # 放宽至该天
            cgrs_sql_day = f"""
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
                  AND TRY_CAST(event_timestamp AS DATE) = TRY_CAST(? AS DATE)
            """
            cgrs_params_day = list(cgrs_candidates) + [ev_ts_clean[:10]]
            if not is_cu and article and article.strip():
                cgrs_sql_day += " AND (ProdSpecific2 IS NULL OR ProdSpecific2 = '' OR ProdSpecific2 = ? OR ProdSpecific2 LIKE ? OR ProdSpecific1 = ? OR ProdSpecific1 LIKE ?)"
                cgrs_params_day.extend([art_clean, f"{prefix7}%", art_clean, f"{prefix7}%"])
            elif is_cu and article and article.strip():
                cgrs_sql_day += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
                cgrs_params_day.extend([prefix7, f"%{prefix7}%"])
            cgrs_sql_day += " ORDER BY event_timestamp DESC, TechOffsetHistoryLocalDate DESC"
            try:
                cgrs_rows = qry(cgrs_sql_day, cgrs_params_day)
            except Exception:
                cgrs_rows = []

        if not cgrs_rows:
            return {
                "status": "success",
                "has_cgrs": False,
                "events_count": 0,
                "message": f"机台 [{workcenter}] 在调参时刻 [{ev_ts_clean}] 未查询到 CGRS 调参记录",
                "conclusion_type": "no_cgrs",
                "conclusion_title": "未查询到调参记录",
                "conclusion_text": f"机台 [{workcenter}] 在调参时刻 [{ev_ts_clean}] 未查询到 CGRS 调参记录，无法执行控制变量排查",
                "events": []
            }
        if not date:
            date = str(cgrs_rows[0].get('event_timestamp'))[:10]
    else:
        # 常规模式：根据 tu_first_shift_date = 目标日期 圈选
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
        elif is_cu and article and article.strip():
            art_clean = article.strip()
            prefix7 = art_clean[:7]
            cgrs_sql += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
            cgrs_params.extend([prefix7, f"%{prefix7}%"])

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
    elif is_cu and article and article.strip():
        art_clean = article.strip()
        prefix7 = art_clean[:7]
        all_ts_sql += " AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = ? OR CAST(MaterialMasterID AS VARCHAR) LIKE ?)"
        all_ts_params.extend([prefix7, f"%{prefix7}%"])
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
    spec_cfg = INDICATORS_SPEC.get(indicator, INDICATORS_SPEC["rfpp"])
    if indicator == "weight":
        ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
        usl, lsl = None, None
    else:
        col_field = spec_cfg["col"]
        ind_col = f"TRY_CAST({col_field} AS DOUBLE)"
        usl, lsl = get_spec_limits(article, indicator) if article else (None, None)

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
            if article and article.strip():
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

        # 界定边界 t_prev 与 t_next (优先从全量调参时间线定位物理生效区间，严格不越界)
        t_prev = None
        t_next = None
        for t_item in all_timestamps:
            if t_item < start_ts and (start_ts - t_item).total_seconds() > 300:
                t_prev = t_item
            elif t_item > end_ts and (t_item - end_ts).total_seconds() > 300:
                if t_next is None:
                    t_next = t_item
                    break
        # 若历史库未扫出，再参考当前合并组相邻组边界
        orig_idx = tot_groups - 1 - g_idx
        if not t_prev and orig_idx > 0:
            t_prev = merged_groups[orig_idx - 1][-1]["timestamp"]
        if not t_next and orig_idx < tot_groups - 1:
            t_next = merged_groups[orig_idx + 1][0]["timestamp"]

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
            else:
                combo_where.append(f"{time_expr} >= ?::TIMESTAMP - INTERVAL 7 DAY")
                combo_params.append(start_ts)

            if t_next:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP")
                combo_params.append(t_next)
            else:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP + INTERVAL 7 DAY")
                combo_params.append(end_ts)

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
            else:
                combo_where.append(f"{time_expr} >= ?::TIMESTAMP - INTERVAL 7 DAY")
                combo_params.append(start_ts)

            if t_next:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP")
                combo_params.append(t_next)
            else:
                combo_where.append(f"{time_expr} < ?::TIMESTAMP + INTERVAL 7 DAY")
                combo_params.append(end_ts)

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

            # 1. 调参前样本 (Before)：向前最多 limit_per_path 条，只取 start_ts 之前的样本，严格不越过上一批调参生效边界 t_prev
            BEFORE_FETCH_LIMIT = limit_per_path
            before_conds = [
                f"{time_expr} < ?::TIMESTAMP",
                f"{time_expr} IS NOT NULL"
            ]
            before_params = list(path_base_params) + [start_ts]
            if t_prev:
                before_conds.append(f"{time_expr} >= ?::TIMESTAMP")
                before_params.append(t_prev)
            else:
                before_conds.append(f"{time_expr} >= ?::TIMESTAMP - INTERVAL 7 DAY")
                before_params.append(start_ts)

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

            # 3. 调参后样本 (After)：向后最多 limit_per_path 条，只取 end_ts 之后的样本，严格不越过下一批调参生效边界 t_next
            after_conds = [
                f"{time_expr} >= ?::TIMESTAMP",
                f"{time_expr} IS NOT NULL"
            ]
            after_params = list(path_base_params) + [end_ts]
            if t_next:
                after_conds.append(f"{time_expr} < ?::TIMESTAMP")
                after_params.append(t_next)
            else:
                after_conds.append(f"{time_expr} < ?::TIMESTAMP + INTERVAL 7 DAY")
                after_params.append(end_ts)

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
                # 调参前最多 50 条 (严格在 [t_prev, start_ts) 边界内)
                fb_before_where = [
                    f"{wc_col} IN ({mach_placeholders})",
                    f"{ind_col} IS NOT NULL",
                    f"{time_expr} < ?::TIMESTAMP"
                ]
                fb_params_b = list(mach_candidates) + [start_ts]
                if article and article.strip():
                    art_clean = article.strip()
                    prefix7 = art_clean[:7]
                    fb_before_where.append("(article10 = ? OR article10 LIKE ?)")
                    fb_params_b.extend([art_clean, f"{prefix7}%"])
                if t_prev:
                    fb_before_where.append(f"{time_expr} >= ?::TIMESTAMP")
                    fb_params_b.append(t_prev)
                else:
                    fb_before_where.append(f"{time_expr} >= ?::TIMESTAMP - INTERVAL 7 DAY")
                    fb_params_b.append(start_ts)
                
                sql_fb_b = f"""
                    SELECT {ind_col} as val
                    FROM clean_yield
                    WHERE {" AND ".join(fb_before_where)}
                    ORDER BY {time_expr} DESC
                    LIMIT 50
                """
                rows_fb_b = qry(sql_fb_b, fb_params_b)
                eff_before_vals = [float(r['val']) for r in rows_fb_b if r.get('val') is not None]

                # 调参后最多 50 条 (严格在 [end_ts, t_next) 边界内)
                fb_after_where = [
                    f"{wc_col} IN ({mach_placeholders})",
                    f"{ind_col} IS NOT NULL",
                    f"{time_expr} >= ?::TIMESTAMP"
                ]
                fb_params_a = list(mach_candidates) + [end_ts]
                if article and article.strip():
                    art_clean = article.strip()
                    prefix7 = art_clean[:7]
                    fb_after_where.append("(article10 = ? OR article10 LIKE ?)")
                    fb_params_a.extend([art_clean, f"{prefix7}%"])
                if t_next:
                    fb_after_where.append(f"{time_expr} < ?::TIMESTAMP")
                    fb_params_a.append(t_next)
                else:
                    fb_after_where.append(f"{time_expr} < ?::TIMESTAMP + INTERVAL 7 DAY")
                    fb_params_a.append(end_ts)

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



def get_cgrs_controlled_analysis(
    workcenter: str,
    date: Optional[str] = None,
    article: Optional[str] = None,
    indicator: str = "rfpp",
    top_machines: Optional[str] = None,
    same_day_only: bool = False,
    limit_per_path: int = 20,
    min_samples_threshold: int = 1,
    event_time: Optional[str] = None
):
    try:
        return compute_cgrs_controlled_analysis_data(
            workcenter=workcenter,
            date=date,
            article=article,
            indicator=indicator,
            top_machines=top_machines,
            same_day_only=same_day_only,
            limit_per_path=limit_per_path,
            min_samples_threshold=min_samples_threshold,
            event_time=event_time
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


def _eval_machine_cgrs_strictly_plan_b(
    target_mach: str,
    article10: str,
    ref_date_str: str,
    indicator_name: str,
    is_curing: bool
) -> Optional[Dict[str, Any]]:
    """
    针对单台机台执行过去 30 天严密 CGRS 控制变量窗口评估与方案 B 选拔:
    1. 封闭样本时间窗口 [t_prev, start_ts) 与 [end_ts, min(t_next, ref_date 23:59:59))，绝不跨相邻调参生效区
    2. 5分钟微调聚类 + 相邻 < 15 胎连续震荡微调合并 (同参数取最早 From ➔ 最新 To)
    3. 方案 B 选拔: 在正向改善 (diff > 0 且 改后样本 >= 5) 中，按改后绝对水平最高 (cpk_after DESC, diff DESC) 锁定黄金方案
    """
    try:
        spec_prefix7 = article10[:7] if len(article10) >= 7 else article10
        spec_cfg = INDICATORS_SPEC.get(indicator_name, INDICATORS_SPEC["rfpp"])
        ind_col = f"TRY_CAST({spec_cfg['col']} AS DOUBLE)"
        usl, lsl = get_spec_limits(article10, indicator_name) if article10 else (None, None)

        candidates = [target_mach]
        if is_curing:
            clean_wc_col = "ct_workcenter"
            clean_time_col = "ct_loc_timestamp"
            if target_mach.startswith("CU") and not target_mach.startswith("CUG"):
                candidates.append(f"CUG{target_mach[2:]}")
            elif target_mach.startswith("CUG"):
                candidates.append(f"CU{target_mach[3:]}")
            spec_filter_cgrs = f"AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = '{spec_prefix7}' OR CAST(MaterialMasterID AS VARCHAR) LIKE '%{spec_prefix7}%')"
        else:
            clean_wc_col = "gt_workcenter"
            clean_time_col = "gt_loc_timestamp"
            if target_mach.startswith("TB2"):
                candidates.append(f"TB1{target_mach[3:]}")
            elif target_mach.startswith("TB1"):
                candidates.append(f"TB2{target_mach[3:]}")
            spec_filter_cgrs = f"AND (ProdSpecific2 = '{article10}' OR ProdSpecific2 LIKE '{spec_prefix7}%')"

        cands_sql = "', '".join(candidates)

        sql_cgrs = f"""
            SELECT
                event_timestamp,
                TechOffsetHistoryLocalDate,
                Workcenter,
                ParameterLocalName,
                ParameterName,
                ParameterValue,
                TechOffsetHistoryValueFrom,
                TechOffsetHistoryValueTo,
                TechOffsetValue,
                ParameterUnitSymbol,
                Priority,
                UserName
            FROM cgrs_records
            WHERE Workcenter IN ('{cands_sql}')
              AND TRY_CAST(event_timestamp AS DATE) <= '{ref_date_str}'::DATE
              AND TRY_CAST(event_timestamp AS DATE) >= ('{ref_date_str}'::DATE - INTERVAL 30 DAY)
              {spec_filter_cgrs}
            ORDER BY event_timestamp ASC
        """
        raw_rows = qry(sql_cgrs)
        if not raw_rows:
            return None

        # 1. 5分钟微调聚类
        clustered = []
        for r in raw_rows:
            ts = r.get('event_timestamp')
            if not ts:
                continue
            matched = None
            for c in clustered:
                if abs((ts - c['timestamp']).total_seconds()) <= 300:
                    matched = c
                    break
            
            p_val = float(r.get('ParameterValue') or 0.0)
            v_from = float(r.get('TechOffsetHistoryValueFrom') or 0.0)
            v_to = float(r.get('TechOffsetHistoryValueTo') or r.get('TechOffsetValue') or 0.0)
            
            p_info = {
                "ParameterName": r.get('ParameterName'),
                "ParameterLocalName": r.get('ParameterLocalName') or r.get('ParameterName'),
                "ParameterValue": p_val,
                "TechOffsetHistoryValueFrom": v_from,
                "TechOffsetHistoryValueTo": v_to,
                "final_value": round(p_val + v_to, 4),
                "ParameterUnitSymbol": r.get('ParameterUnitSymbol') or "",
                "Priority": r.get('Priority') or 3,
                "UserName": r.get('UserName') or "工艺员",
                "event_time": str(r.get('TechOffsetHistoryLocalDate') or ts)
            }
            if matched:
                matched['params'].append(p_info)
            else:
                clustered.append({
                    "timestamp": ts,
                    "date_str": str(r.get('TechOffsetHistoryLocalDate') or ts),
                    "params": [p_info]
                })

        # 2. 相邻两次调参生产样本 < 15 胎合并 (防止频繁震荡微调)
        merged_groups = []
        curr_group = []
        for ev in clustered:
            if not curr_group:
                curr_group.append(ev)
            else:
                prev_ts = curr_group[-1]['timestamp']
                curr_ts = ev['timestamp']
                cnt_sql = f"""
                    SELECT COUNT(*) as cnt FROM clean_yield
                    WHERE {clean_wc_col} IN ('{cands_sql}')
                      AND article10 LIKE '{spec_prefix7}%'
                      AND TRY_CAST({clean_time_col} AS TIMESTAMP) >= '{prev_ts}'::TIMESTAMP
                      AND TRY_CAST({clean_time_col} AS TIMESTAMP) < '{curr_ts}'::TIMESTAMP
                """
                cnt_res = qry(cnt_sql)
                cnt = cnt_res[0]['cnt'] if cnt_res else 0
                if cnt < 15:
                    curr_group.append(ev)
                else:
                    merged_groups.append(curr_group)
                    curr_group = [ev]
        if curr_group:
            merged_groups.append(curr_group)

        # 3. 严格封闭窗口 CGRS 评估
        scored_events = []
        tot_g = len(merged_groups)
        ref_limit_dt = datetime.strptime(f"{ref_date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")

        for idx, g in enumerate(merged_groups):
            start_ts = g[0]['timestamp']
            end_ts = g[-1]['timestamp']
            t_prev = merged_groups[idx - 1][-1]['timestamp'] if idx > 0 else None
            t_next = merged_groups[idx + 1][0]['timestamp'] if idx < tot_g - 1 else None

            # 改前样本窗口 [t_prev, start_ts)
            sql_b_where = [
                f"{clean_wc_col} IN ('{cands_sql}')",
                f"article10 LIKE '{spec_prefix7}%'",
                f"TRY_CAST({clean_time_col} AS TIMESTAMP) < '{start_ts}'::TIMESTAMP"
            ]
            if t_prev:
                sql_b_where.append(f"TRY_CAST({clean_time_col} AS TIMESTAMP) >= '{t_prev}'::TIMESTAMP")
            sql_b = f"SELECT {ind_col} as val FROM clean_yield WHERE {' AND '.join(sql_b_where)} ORDER BY {clean_time_col} DESC LIMIT 50"
            vals_b = [float(x['val']) for x in qry(sql_b) if x.get('val') is not None]

            # 改后样本窗口 [end_ts, min(t_next, ref_limit_dt))
            next_limit = min(t_next, ref_limit_dt) if t_next else ref_limit_dt
            sql_a_where = [
                f"{clean_wc_col} IN ('{cands_sql}')",
                f"article10 LIKE '{spec_prefix7}%'",
                f"TRY_CAST({clean_time_col} AS TIMESTAMP) >= '{end_ts}'::TIMESTAMP",
                f"TRY_CAST({clean_time_col} AS TIMESTAMP) <= '{next_limit}'::TIMESTAMP"
            ]
            sql_a = f"SELECT {ind_col} as val FROM clean_yield WHERE {' AND '.join(sql_a_where)} ORDER BY {clean_time_col} ASC LIMIT 50"
            vals_a = [float(x['val']) for x in qry(sql_a) if x.get('val') is not None]

            cpk_b = calc_cpk(float(np.mean(vals_b)), float(np.std(vals_b, ddof=1)), usl, lsl) if len(vals_b) > 1 else None
            cpk_a = calc_cpk(float(np.mean(vals_a)), float(np.std(vals_a, ddof=1)), usl, lsl) if len(vals_a) > 1 else None
            diff = (cpk_a - cpk_b) if (cpk_a is not None and cpk_b is not None) else None

            # 同参数吸收合并 (取最早 From ➔ 最新 To)
            p_map = {}
            for ev_item in g:
                for p in ev_item['params']:
                    p_k = p['ParameterName'] or p['ParameterLocalName']
                    if p_k not in p_map:
                        p_map[p_k] = dict(p)
                    else:
                        p_map[p_k]['TechOffsetHistoryValueTo'] = p['TechOffsetHistoryValueTo']
                        p_map[p_k]['final_value'] = p['final_value']

            scored_events.append({
                "machine": target_mach,
                "event_time": str(g[-1]['date_str'])[:16],
                "nb": len(vals_b),
                "na": len(vals_a),
                "cpk_b": round(cpk_b, 3) if cpk_b else None,
                "cpk_a": round(cpk_a, 3) if cpk_a else None,
                "diff": round(diff, 3) if diff else None,
                "params": list(p_map.values())
            })

        # 4. 方案 B 黄金方案选拔 (正向改善 diff > 0 且 改后样本 >= 5，优先改后 CPK 最高)
        improved = [
            e for e in scored_events 
            if e['diff'] is not None and e['diff'] > 0 and e['na'] >= 5 and e['cpk_a'] is not None
        ]
        if improved:
            improved.sort(key=lambda x: (x['cpk_a'], x['diff']), reverse=True)
            return improved[0]
        return None
    except Exception as e:
        print(f"Error evaluating machine CGRS {target_mach}: {e}")
        return None


def _get_machine_current_param_offsets(machine: str, ref_date_str: str, is_curing: bool, article10: Optional[str] = None) -> Dict[str, float]:
    """获取机台在观察基准日当前最近一次生效的偏置值快照 (机台 + 规格 + 时间 三元匹配)"""
    candidates = [machine]
    if is_curing:
        if machine.startswith("CU") and not machine.startswith("CUG"):
            candidates.append(f"CUG{machine[2:]}")
        elif machine.startswith("CUG"):
            candidates.append(f"CU{machine[3:]}")
    else:
        if machine.startswith("TB2"):
            candidates.append(f"TB1{machine[3:]}")
        elif machine.startswith("TB1"):
            candidates.append(f"TB2{machine[3:]}")
    cands_sql = "', '".join(candidates)

    spec_cond = ""
    if article10 and article10.strip():
        spec_prefix7 = article10.strip()[:7]
        if is_curing:
            spec_cond = f"AND (RIGHT(CAST(MaterialMasterID AS VARCHAR), 7) = '{spec_prefix7}' OR CAST(MaterialMasterID AS VARCHAR) LIKE '%{spec_prefix7}%')"
        else:
            spec_cond = f"AND (ProdSpecific2 = '{article10.strip()}' OR ProdSpecific2 LIKE '{spec_prefix7}%')"

    sql = f"""
        SELECT 
            ParameterName,
            ParameterLocalName,
            ParameterValue,
            TechOffsetHistoryValueTo,
            TechOffsetValue,
            event_timestamp
        FROM cgrs_records
        WHERE Workcenter IN ('{cands_sql}')
          AND TRY_CAST(event_timestamp AS TIMESTAMP) <= '{ref_date_str} 23:59:59'::TIMESTAMP
          {spec_cond}
        ORDER BY event_timestamp DESC
    """
    rows = qry(sql)
    curr_map = {}
    for r in rows:
        p_name = r.get('ParameterName')
        p_local = r.get('ParameterLocalName')
        off_to = float(r.get('TechOffsetHistoryValueTo') or r.get('TechOffsetValue') or 0.0)
        if p_name and p_name not in curr_map:
            curr_map[p_name] = off_to
        if p_local and p_local not in curr_map:
            curr_map[p_local] = off_to

    # 若成型特定规格未查到偏置，回退到机台通用偏置（CU 硫化工序严禁跨规格混用）
    if not curr_map and spec_cond and not is_curing:
        sql_fallback = f"""
            SELECT 
                ParameterName,
                ParameterLocalName,
                ParameterValue,
                TechOffsetHistoryValueTo,
                TechOffsetValue,
                event_timestamp
            FROM cgrs_records
            WHERE Workcenter IN ('{cands_sql}')
              AND TRY_CAST(event_timestamp AS TIMESTAMP) <= '{ref_date_str} 23:59:59'::TIMESTAMP
            ORDER BY event_timestamp DESC
        """
        rows_fb = qry(sql_fallback)
        for r in rows_fb:
            p_name = r.get('ParameterName')
            p_local = r.get('ParameterLocalName')
            off_to = float(r.get('TechOffsetHistoryValueTo') or r.get('TechOffsetValue') or 0.0)
            if p_name and p_name not in curr_map:
                curr_map[p_name] = off_to
            if p_local and p_local not in curr_map:
                curr_map[p_local] = off_to

    return curr_map


def get_cgrs_recommended_params(
    machine: str,
    article10: str,
    workcenter_type: str = "gt",
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    reason: str = "degradation"
):
    """
    智能机台调参推荐核心服务 (严格复用 CGRS 计算窗口 + 方案 B 黄金方案选拔 + 全0自动跨机台穿透)
    """
    try:
        ref_date = target_date.strip() if target_date and target_date.strip() else datetime.now().strftime('%Y-%m-%d')
        spec_prefix7 = article10[:7] if len(article10) >= 7 else article10
        is_cu = machine.startswith("CU") or machine.startswith("CT") or workcenter_type.lower() in ("ct", "cu")
        stage_name_cn = "硫化 CT" if is_cu else "成型 GT"

        # 1. 第一阶段：严密评估本机台过去 30 天方案 B 黄金调参事件
        same_best = _eval_machine_cgrs_strictly_plan_b(
            target_mach=machine,
            article10=article10,
            ref_date_str=ref_date,
            indicator_name=indicator,
            is_curing=is_cu
        )

        # 获取本机当前偏置快照 (机台 + 规格 + 时间)
        curr_offsets = _get_machine_current_param_offsets(machine, ref_date, is_cu, article10)

        # 判断本机台是否与推荐方案完全一致 (全 0 变化判定)
        is_same_all_zero = True
        if same_best and same_best.get('params'):
            for p in same_best['params']:
                p_code = p.get('ParameterName')
                p_local = p.get('ParameterLocalName')
                rec_to = float(p.get('TechOffsetHistoryValueTo') or 0.0)
                curr_to = curr_offsets.get(p_code, curr_offsets.get(p_local, 0.0))
                if abs(rec_to - curr_to) >= 0.0001:
                    is_same_all_zero = False
                    break
        else:
            is_same_all_zero = True

        chosen_event = None
        source_type = "same_machine_best"
        source_mach = machine
        matched_spec_level = "exact"
        is_optimal_no_diff = False

        if same_best and not is_same_all_zero:
            # 本机有有效改进空间：直接采用本机方案
            chosen_event = same_best
            source_type = "same_machine_best"
            source_mach = machine
        else:
            # 2. 第二阶段：本机无正向调参 或 本机当前已稳定在历史最佳 (变化全为0) -> 自动启动同工段跨机台穿透
            candidates = [machine]
            if is_cu:
                if machine.startswith("CU") and not machine.startswith("CUG"):
                    candidates.append(f"CUG{machine[2:]}")
                elif machine.startswith("CUG"):
                    candidates.append(f"CU{machine[3:]}")
                cands_sql = "', '".join(candidates)
                sql_peers = f"""
                    SELECT DISTINCT ct_workcenter as wc
                    FROM clean_yield
                    WHERE article10 LIKE '{spec_prefix7}%'
                      AND ct_workcenter IS NOT NULL AND ct_workcenter != ''
                      AND ct_workcenter NOT IN ('{cands_sql}')
                      AND TRY_CAST(ct_loc_timestamp AS DATE) <= '{ref_date}'::DATE
                      AND TRY_CAST(ct_loc_timestamp AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                """
            else:
                if machine.startswith("TB2"):
                    candidates.append(f"TB1{machine[3:]}")
                elif machine.startswith("TB1"):
                    candidates.append(f"TB2{machine[3:]}")
                cands_sql = "', '".join(candidates)
                sql_peers = f"""
                    SELECT DISTINCT gt_workcenter as wc
                    FROM clean_yield
                    WHERE article10 LIKE '{spec_prefix7}%'
                      AND gt_workcenter IS NOT NULL AND gt_workcenter != ''
                      AND gt_workcenter NOT IN ('{cands_sql}')
                      AND TRY_CAST(tu_first_shift_date AS DATE) <= '{ref_date}'::DATE
                      AND TRY_CAST(tu_first_shift_date AS DATE) >= ('{ref_date}'::DATE - INTERVAL 30 DAY)
                """

            peer_machines = [r['wc'] for r in qry(sql_peers) if r.get('wc')]
            peer_results = []

            for p_mach in peer_machines:
                p_res = _eval_machine_cgrs_strictly_plan_b(
                    target_mach=p_mach,
                    article10=article10,
                    ref_date_str=ref_date,
                    indicator_name=indicator,
                    is_curing=is_cu
                )
                if p_res:
                    peer_results.append(p_res)

            if peer_results:
                # 方案 B 决出全工段第一标杆机
                peer_results.sort(key=lambda x: (x['cpk_a'], x['diff']), reverse=True)
                top_peer = peer_results[0]

                # 检查标杆机参数与当前机台是否存在实际差异
                is_peer_all_zero = True
                for p in top_peer['params']:
                    p_code = p.get('ParameterName')
                    p_local = p.get('ParameterLocalName')
                    rec_to = float(p.get('TechOffsetHistoryValueTo') or 0.0)
                    curr_to = curr_offsets.get(p_code, curr_offsets.get(p_local, 0.0))
                    if abs(rec_to - curr_to) >= 0.0001:
                        is_peer_all_zero = False
                        break

                if not is_peer_all_zero:
                    # 跨机台存在差异：推荐全工段标杆机台参数
                    chosen_event = top_peer
                    source_type = "same_stage_best"
                    source_mach = top_peer['machine']
                    matched_spec_level = "fixed_spec_producer" if is_cu else "same_spec"
                else:
                    # 跨机台比对后依然全为 0：说明当前机台已处于全工段最佳基准状态
                    chosen_event = top_peer if (not same_best or top_peer['cpk_a'] > same_best['cpk_a']) else same_best
                    source_type = "same_stage_best" if (chosen_event == top_peer) else "same_machine_best"
                    source_mach = chosen_event['machine']
                    is_optimal_no_diff = True
            elif same_best:
                # 兄弟机台无更好方案，退守本机历史最优
                chosen_event = same_best
                source_type = "same_machine_best"
                source_mach = machine
                is_optimal_no_diff = is_same_all_zero

        if not chosen_event:
            return {
                "status": "success",
                "has_recommendation": False,
                "reason": reason,
                "recommend_title": f"未查询到【{stage_name_cn}】工艺调参修改记录",
                "message": f"在观察日 [{ref_date}] 前 30 天内，未查询到生产规格 [{article10}] 带来质量改善的工艺调参修改记录。",
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
            if delta_str in ("+0", "-0"):
                delta_str = "0"

            p_val = p.get("ParameterValue")
            unit_str = p.get("ParameterUnitSymbol") or ""
            final_val = p.get("final_value") if p.get("final_value") is not None else (float(p_val or 0.0) + v_to)

            ev_time = str(p.get("event_time", "") or chosen_event['event_time'])[:19]

            formatted_params.append({
                "param_name": p.get("ParameterName", ""),
                "param_local_name": p.get("ParameterLocalName") or p.get("ParameterName"),
                "event_time": ev_time,
                "val_from": fmt_num(v_from),
                "val_to": fmt_num(v_to),
                "delta": delta_str,
                "final_value": fmt_num(final_val),
                "setting_from": fmt_num(float(p_val or 0.0) + v_from) if p_val is not None else fmt_num(v_from),
                "setting_to": fmt_num(final_val),
                "unit": unit_str,
                "priority": p.get("Priority") or 3,
                "operator": p.get("UserName") or "工艺员"
            })

        cb = chosen_event.get('cpk_b')
        ca = chosen_event.get('cpk_a')
        diff = chosen_event.get('diff')
        yoy = round((ca - cb) / cb * 100.0, 1) if (cb and ca and cb > 0) else None

        recommend_category = "same_machine" if source_type == "same_machine_best" else "cross_machine"

        if is_optimal_no_diff:
            rec_title = f"机台工艺参数已达到历史最佳基准 ({chosen_event['event_time']})"
            rec_desc = f"比对本机台及同工段兄弟机台后，当前参数已与历史最佳水平 (CPK: {ca:.2f}) 保持一致，未查询到差异，建议维持现有稳定工艺。"
        elif source_type == "same_machine_best":
            rec_title = f"建议复原至本机台 [{machine}] 历史最佳调参 ({chosen_event['event_time']})"
            rec_desc = f"在观察日 [{ref_date}] 前 30 天内，本机台曾于 {chosen_event['event_time']} 进行工艺优化，调参后 CPK 达到 {ca:.2f}（提升 {yoy:+.1f}%）。" if (ca and yoy) else f"在观察日 [{ref_date}] 前 30 天内匹配到本机台优化调参版本。"
        else:
            rec_title = f"推荐参考生产该规格的标杆机台 [{source_mach}] 历史最佳参数 ({chosen_event['event_time']})"
            rec_desc = f"本机台当前参数已到位，系统为您自动穿透匹配到生产该规格的工段标杆机台 [{source_mach}] 最佳工艺设定，调参后该机台 CPK 达到 {ca:.2f}。"

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
            "is_optimal_no_diff": is_optimal_no_diff,
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





def _get_same_section_machines(article: str, target_date: str, days: int = 30, section: str = "gt") -> list:
    """获取过去 30 天生产过该规格的机台列表 (严格强规格锁定)"""
    wc_col = "ct_workcenter" if section.lower() in ("cu", "ct") else "gt_workcenter"
    spec_prefix7 = article[:7] if len(article) >= 7 else article
    sql = f"""
        SELECT DISTINCT {wc_col} as wc
        FROM clean_yield
        WHERE (article10 = ? OR article10 LIKE ?)
          AND {wc_col} IS NOT NULL
          AND {wc_col} != ''
          AND TRY_CAST(tu_first_shift_date AS DATE) <= ?::DATE
          AND TRY_CAST(tu_first_shift_date AS DATE) >= (?::DATE - INTERVAL {days} DAY)
    """
    rows = qry(sql, [article, f"{spec_prefix7}%", target_date, target_date])
    return [r['wc'] for r in rows if r.get('wc')]


def _find_best_event_for_machines(machines: list, target_date: str, article: str, indicator: str, section: str = "gt"):
    """
    为指定机台列表扫描过去 30 天的最佳调参事件：
    - 针对成型机台 (GT)：利用 recommend_for_machine 逻辑获取机台最佳提升事件
    - 针对硫化机台 (CU)：利用 recommend_for_machine 逻辑获取硫化最佳提升事件
    返回 (best_event_dict, scanned_events_count)
    """
    if not machines:
        return None, 0

    best_event = None
    best_improvement = -999.0
    total_scanned = 0

    for m in machines:
        res = recommend_for_machine(
            machine=m,
            article10=article,
            workcenter_type=section,
            indicator=indicator,
            target_date=target_date,
            reason="benchmark"
        )
        if res.get("status") == "success" and res.get("has_recommendation"):
            total_scanned += 1
            diff = res.get("cpk_diff") or 0.0
            if diff > best_improvement:
                best_improvement = diff
                best_event = res

    # 仅当存在正向改善 (diff > 0) 或有有效调参时才采纳
    if best_event and (best_improvement > 0 or best_event.get("cpk_after") is not None):
        return best_event, total_scanned
    return None, total_scanned



def get_param_recommendation(
    article: str,
    indicator: str = "rfpp",
    target_date: Optional[str] = None
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





# 业务纯函数命名映射与别名兼容
recommend_for_machine = get_cgrs_recommended_params
recommend_best_for_spec = get_param_recommendation
