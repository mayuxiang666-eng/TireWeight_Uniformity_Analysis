# -*- coding: utf-8 -*-
"""
Helper script to assemble backend/services/article_service.py from scratch/baseline_main.py
"""
with open("scratch/baseline_main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

header = '''# -*- coding: utf-8 -*-
"""
轮胎规格看板服务模块 (Article Service)
包含规格型号期别归属、全量规格列表、预警规格排行、条码散点 Run Chart、批次 CPK 趋势与批次条码明细
"""
from typing import Optional, List, Dict, Any, Tuple
import os
import sys
import json
import math
import traceback
import concurrent.futures
from datetime import datetime, timedelta
import numpy as np
import duckdb

from backend.core.config import get_cleaned_data_path
from backend.core.db import qry
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl
from backend.core.serializer import sanitize_data
from backend.core.time_utils import build_production_time_where, get_phase_sql_condition

# 解耦同层服务间 import 的运行时动态提供者钩子
_top_warning_provider = None
_best_tu_provider = None
_cgrs_cpk_comparator = None

def set_article_helpers(top_warning_provider=None, best_tu_provider=None, cgrs_comparator=None):
    """注入跨服务计算能力 (由路由层或系统启动时组装)"""
    global _top_warning_provider, _best_tu_provider, _cgrs_cpk_comparator
    if top_warning_provider:
        _top_warning_provider = top_warning_provider
    if best_tu_provider:
        _best_tu_provider = best_tu_provider
    if cgrs_comparator:
        _cgrs_cpk_comparator = cgrs_comparator

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

'''

# Function 1: get_article_phase (lines 452 to 488)
fn1_sig = '''def get_article_phase(article10: str):
'''
part1 = fn1_sig + "".join(lines[452:488])

# Function 2: get_all_articles (lines 1568 to 1575)
part2 = "".join(lines[1567:1575])

# Function 3: get_spec_warning_machines_detailed (lines 3241 to 3563)
part3_raw = "".join(lines[3240:3563])

# Replace top_warning call
part3_raw = part3_raw.replace(
    "top_list = get_top_warning_machines(",
    "_tw = _get_top_warning_provider()\n        top_list = _tw("
)
part3_raw = part3_raw.replace(
    "prev_top = get_top_warning_machines(",
    "_tw = _get_top_warning_provider()\n                prev_top = _tw("
)

# Replace best_tu call
part3_raw = part3_raw.replace(
    "best_tu, best_tu_val = get_best_tu_machine_for_spec(article10, indicator, min_samples=1)",
    "_bt = _get_best_tu_provider()\n        best_tu, best_tu_val = _bt(article10, indicator, min_samples=1) if _bt else (None, None)"
)

# Replace calculate_cgrs_cpk_comparison call
part3_raw = part3_raw.replace(
    "cgrs_comp = calculate_cgrs_cpk_comparison(",
    "_cc = _get_cgrs_comparator()\n                    cgrs_comp = _cc("
)

part3 = part3_raw

# Function 4: get_articles_warning_cpk (lines 1579 to 2009)
fn4_sig = '''def get_warning_cpk(
    indicator: str = "rfpp",
    study_from: Optional[str] = None,
    study_to: Optional[str] = None,
    only_declining: bool = False,
    min_samples: int = 30,
    phase: Optional[str] = "all",
    article10: Optional[str] = None,
    time_col: Optional[str] = "tu_first_loc_timestamp",
    max_cpk: Optional[float] = 0.9,
    shift: Optional[str] = "all"
):
'''
part4 = fn4_sig + "".join(lines[1590:2009])

# Function 5: get_article_barcode_measurements (lines 2011 to 2250)
fn5_sig = '''def get_barcode_measurements(
    article10: str,
    target_date: Optional[str] = None,
    indicator: str = "rfpp",
    time_col: Optional[str] = "tu_first_loc_timestamp",
    phase: Optional[str] = "all",
    shift: Optional[str] = "all",
    limit: int = 1000
):
'''
part5 = fn5_sig + "".join(lines[2018:2250])

# Function 6: get_article_lot_cpk_trend (lines 4331 to 4596)
fn6_sig = '''def get_lot_cpk_trend(
    article10: str,
    target_date: Optional[str] = None,
    indicator: str = "rfpp",
    component: Optional[str] = None,
    time_col: Optional[str] = "gt_loc_timestamp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 1
):
'''
part6 = fn6_sig + "".join(lines[4340:4596])

# Function 7: get_lot_barcode_detail (lines 4598 to 4694)
fn7_sig = '''def get_lot_barcode_detail(
    article10: str,
    lot: str,
    component: Optional[str] = None,
    indicator: str = "rfpp"
):
'''
part7 = fn7_sig + "".join(lines[4603:4694])

aliases = '''

# 业务纯函数命名映射与别名兼容
get_article_phase_endpoint = get_article_phase
get_articles_warning_cpk = get_warning_cpk
get_article_barcode_measurements = get_barcode_measurements
get_article_lot_cpk_trend = get_lot_cpk_trend
'''

full_code = header + part1 + "\n\n" + part2 + "\n\n" + part3 + "\n\n" + part4 + "\n\n" + part5 + "\n\n" + part6 + "\n\n" + part7 + "\n\n" + aliases

with open("backend/services/article_service.py", "w", encoding="utf-8") as f:
    f.write(full_code)

print("Successfully generated backend/services/article_service.py!")
