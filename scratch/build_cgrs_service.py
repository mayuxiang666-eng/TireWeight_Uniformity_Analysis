# -*- coding: utf-8 -*-
"""
Helper script to assemble backend/services/cgrs_service.py from scratch/baseline_main.py
"""
import os

with open("scratch/baseline_main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

header = '''# -*- coding: utf-8 -*-
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
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl
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

'''

# Function 1: get_cgrs_records
# lines[225] is @app.get...
# lines[226:231] is def get_cgrs_records(...)
# lines[231:389] is body
fn1_sig = '''def get_cgrs_records(
    workcenter: str,
    date: str,
    article: Optional[str] = None,
    indicator: Optional[str] = "rfpp"
):
'''
part1 = fn1_sig + "".join(lines[231:389])

# Function 2: compute_cgrs_controlled_analysis_data + calculate_cgrs_cpk_comparison + get_cgrs_controlled_analysis
# lines[528:1455]
# lines[1455] is @app.get("/api/cgrs/controlled-analysis")
# lines[1456:1488] is get_cgrs_controlled_analysis
part2_a = "".join(lines[528:1455])
fn2_sig = '''def get_cgrs_controlled_analysis(
    workcenter: str,
    date: str,
    article: Optional[str] = None,
    indicator: str = "rfpp",
    top_machines: Optional[str] = None,
    same_day_only: bool = False,
    limit_per_path: int = 20,
    min_samples_threshold: int = 1
):
'''
part2_b = fn2_sig + "".join(lines[1465:1488])

# Function 3: get_cgrs_recommended_params
# lines[5548] is @app.get("/api/cgrs/recommended-params")
# lines[5549:5557] is signature
fn3_sig = '''def get_cgrs_recommended_params(
    machine: str,
    article10: str,
    workcenter_type: str = "gt",
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    reason: str = "degradation"
):
'''
part3 = fn3_sig + "".join(lines[5557:6000])

helper_code = '''

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

'''

# Function 4: get_param_recommendation
# lines[5110] is @app.get("/api/cgrs/param-recommendation")
# lines[5111:5116] is signature
fn4_sig = '''def get_param_recommendation(
    article: str,
    indicator: str = "rfpp",
    target_date: Optional[str] = None
):
'''
part4 = fn4_sig + "".join(lines[5116:5160])

aliases = '''

# 业务纯函数命名映射与别名兼容
recommend_for_machine = get_cgrs_recommended_params
recommend_best_for_spec = get_param_recommendation
'''

full_code = header + part1 + "\n\n" + part2_a + "\n\n" + part2_b + "\n\n" + part3 + "\n\n" + helper_code + "\n\n" + part4 + "\n\n" + aliases

with open("backend/services/cgrs_service.py", "w", encoding="utf-8") as f:
    f.write(full_code)

print("Successfully regenerated backend/services/cgrs_service.py!")
