# -*- coding: utf-8 -*-
"""
Helper script to assemble backend/services/process_flow_service.py from scratch/baseline_main.py
"""
with open("scratch/baseline_main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

header = '''# -*- coding: utf-8 -*-
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
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl
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

def set_process_flow_helpers(top_warning_provider=None, best_tu_provider=None, cgrs_comparator=None):
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

# Function 1: get_machine_combination_tree (lines 2832 to 2968)
fn1_sig = '''def get_machine_combination_tree(
    spec: str,
    start_wc: Optional[str] = None,
    end_wc: Optional[str] = None,
    indicator: str = "rfpp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_date: Optional[str] = None,
    min_samples: int = 10,
):
'''
part1 = fn1_sig + "".join(lines[2841:2968])

# Function 2: get_machine_process_sankey (lines 3565 to 3947)
fn2_sig = '''def get_process_sankey(
    article10: str,
    indicator: str = "rfpp",
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 10,
    tolerance: float = 0.8
):
'''
part2_raw = "".join(lines[3573:3947])

# Replace top_warning call
part2_raw = part2_raw.replace(
    "warning_list = get_top_warning_machines(",
    "_tw = _get_top_warning_provider()\n        warning_list = _tw(" if "_tw = _get_top_warning_provider()" not in part2_raw else "warning_list = _tw("
)

# Replace calculate_cgrs_cpk_comparison call
part2_raw = part2_raw.replace(
    "cgrs_comp = calculate_cgrs_cpk_comparison(",
    "_cc = _get_cgrs_comparator()\n                cgrs_comp = _cc(" if "_cc = _get_cgrs_comparator()" not in part2_raw else "cgrs_comp = _cc("
)

part2 = fn2_sig + part2_raw

# Function 3: get_machine_best_process_sankey (lines 4032 to 4328)
fn3_sig = '''def get_best_process_sankey(
    article10: str,
    indicator: str = "rfpp",
    min_samples: int = 10,
):
'''
part3_raw = "".join(lines[4036:4328])

# Replace best_tu call
part3_raw = part3_raw.replace(
    "best_tu_mach, best_tu_val = get_best_tu_machine_for_spec(article10, indicator, min_samples=min_samples)",
    "_bt = _get_best_tu_provider()\n        best_tu_mach, best_tu_val = _bt(article10, indicator, min_samples=min_samples) if _bt else (None, None)"
)

part3 = fn3_sig + part3_raw

aliases = '''

# 业务纯函数命名映射与别名兼容
get_machine_process_sankey = get_process_sankey
get_machine_best_process_sankey = get_best_process_sankey
'''

full_code = header + part1 + "\n\n" + part2 + "\n\n" + part3 + "\n\n" + aliases

with open("backend/services/process_flow_service.py", "w", encoding="utf-8") as f:
    f.write(full_code)

print("Successfully generated backend/services/process_flow_service.py!")
