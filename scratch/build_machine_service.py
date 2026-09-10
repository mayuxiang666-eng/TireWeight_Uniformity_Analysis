# -*- coding: utf-8 -*-
"""
Helper script to assemble backend/services/machine_service.py from scratch/baseline_main.py
"""
with open("scratch/baseline_main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

header = '''# -*- coding: utf-8 -*-
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

'''

# Function 1: get_machines_cpk (lines 2252 to 2687)
# Signature in baseline: lines 2253 to 2261
fn1_sig = '''def get_machine_cpk(
    target_date: str,
    article10: str,
    indicator: str = "rfpp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 10,
    tolerance: float = 0.8,
):
'''
part1 = fn1_sig + "".join(lines[2261:2687])

# Function 2: get_machine_cpk_trend (lines 2688 to 2830)
# Signature in baseline: lines 2689 to 2696
fn2_sig = '''def get_machine_cpk_trend(
    machine: str,
    workcenter_col: str,
    indicator: str = "rfpp",
    article10: Optional[str] = None,
    mode: Optional[str] = None,
    tolerance: float = 0.8
):
'''
part2 = fn2_sig + "".join(lines[2696:2830])

# Function 3: get_top_warning_machines (lines 2969 to 3217)
part3 = "".join(lines[2969:3217])

# Function 4: get_best_tu_machine_for_spec (lines 3948 to 4030)
part4 = "".join(lines[3948:4030])

# Function 5: get_top_warning_api (lines 5161 to 5208)
fn5_sig = '''def get_top_warning(
    spec: str,
    indicator: str = "rfpp",
    target_date: str = None,
    n: int = 3,
    days: int = 3,
    min_samples: int = 1
):
'''
part5 = fn5_sig + "".join(lines[5170:5208])

# Function 6: get_best_tu_api (lines 5209 to 5224)
fn6_sig = '''def get_best_tu(
    article10: str,
    indicator: str = "rfpp",
    min_samples: int = 10
):
'''
part6 = fn6_sig + "".join(lines[5215:5224])

# Function 7: get_machine_cpk_trend_comparison (lines 5225 to 5548)
fn7_sig = '''def get_cpk_trend_comparison(
    workcenter_type: str = "gt",
    machines: str = "",
    article10: str = "",
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    days: int = 14,
    min_samples: int = 3
):
'''
part7_raw = "".join(lines[5235:5548])

part7_raw = part7_raw.replace(
    "cgrs_res = calculate_cgrs_cpk_comparison(",
    "_cgrs_calc = _get_cgrs_comparator()\n            cgrs_res = _cgrs_calc(" if "_cgrs_calc = _get_cgrs_comparator()" not in part7_raw else "cgrs_res = _cgrs_calc("
)

part7 = fn7_sig + part7_raw

aliases = '''

# 业务纯函数命名映射与别名兼容
get_machines_cpk = get_machine_cpk
get_top_warning_api = get_top_warning
get_best_tu_api = get_best_tu
get_machine_cpk_trend_comparison = get_cpk_trend_comparison
'''

full_code = header + part1 + "\n\n" + part2 + "\n\n" + part3 + "\n\n" + part4 + "\n\n" + part5 + "\n\n" + part6 + "\n\n" + part7 + "\n\n" + aliases

with open("backend/services/machine_service.py", "w", encoding="utf-8") as f:
    f.write(full_code)

print("Successfully regenerated backend/services/machine_service.py!")
