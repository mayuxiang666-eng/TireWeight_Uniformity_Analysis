# -*- coding: utf-8 -*-
"""
轮胎 17 项质检指标集中配置表与纯函数工具库
⚠️ 依赖边界：本模块仅允许 import backend/core (cpk/db)，严禁反向依赖 services。
"""
from typing import Optional, Tuple
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl, INDICATORS_SPEC

INDICATOR_CONFIG = INDICATORS_SPEC


def resolve_col_name(indicator: str, use_target: bool = False) -> str:
    """获取指定指标对应的 DuckDB 数据列名"""
    cfg = INDICATOR_CONFIG.get(indicator, INDICATOR_CONFIG["rfpp"])
    return cfg["col"]


def get_tolerance(indicator: str, article10: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    """统一获取指标的公差限制 (USL, LSL)——严格以 Recipes 配方为准"""
    if indicator == "weight":
        return 0.028, -0.028
    if article10:
        return get_spec_limits(article10, indicator)
    return None, None


def calc_metric(
    indicator: str,
    mean_val: float,
    std_val: float,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    target_val: Optional[float] = None
) -> Optional[float]:
    """根据指标配置，自动路由是计算标准 CPK 还是均值偏差率"""
    if indicator == "weight":
        if target_val and abs(target_val) > 1e-6:
            return round((mean_val - target_val) / target_val * 100.0, 4)
        return 0.0
    return calc_cpk(mean_val, std_val, usl, lsl)
