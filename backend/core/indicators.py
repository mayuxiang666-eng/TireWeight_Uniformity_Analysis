# -*- coding: utf-8 -*-
"""
轮胎四大指标集中配置表与纯函数工具库
消灭全项目所有散落的 if indicator == '...' 分支
⚠️ 依赖边界：本模块仅允许 import backend/core (cpk/db)，严禁反向依赖 services。
"""
from typing import Optional, Tuple
from backend.core.cpk import calc_cpk, get_spec_limits, get_spec_usl

# 真实口径核对：与 main.py get_spec_usl(405)/get_spec_limits(490) 完全一致
INDICATOR_CONFIG = {
    "rfpp": {
        "label": "RFPP 径向力峰峰值",
        "raw_col": "rfppwc_first",
        "target_col": None,
        "limit_type": "single_sided",     # 单侧上限 USL
        "metric_type": "cpk",             # 走标准 CPK
        "lookup_unscaled_col": "standard_rfpp",   # 查库列 (基准值*10 = USL)
        "group_fallback_base": {          # 查不到标准值时按 GROUP 回退 (基准值*10)
            "GROUP 1": 10.5, "GROUP 2A": 11.5, "GROUP 2B": 12.5,
            "GROUP 3": 12.5, "GROUP 4": 14.5,
        },
        "default_usl": 100.0,             # 无 article10 / 库全空 → 兜底
        "default_lsl": None,
    },
    "rfh1": {
        "label": "RFH1 径向力一次谐波",
        "raw_col": "rfh1wc_first",
        "target_col": None,
        "limit_type": "single_sided",
        "metric_type": "cpk",
        "lookup_unscaled_col": "standard_rfh1",
        "group_fallback_base": {
            "GROUP 1": 7.5, "GROUP 2A": 8.5, "GROUP 2B": 9.0,
            "GROUP 3": 9.5, "GROUP 4": 10.0,
        },
        "default_usl": 100.0,             # 注意：真实兜底是 100.0 而非 75.0
        "default_lsl": None,
    },
    "cony": {
        "label": "CONY 锥度力",
        "raw_col": "cony_first",
        "target_col": None,
        "limit_type": "double_sided",     # 双侧上下限 [LSL, USL]
        "metric_type": "cpk",             # 走标准 CPK
        "lookup_usl_col": "conny_usl",    # 查库双侧限
        "lookup_lsl_col": "conny_lsl",
        "default_usl": 95.0,
        "default_lsl": -95.0,
    },
    "weight": {
        "label": "胎重",
        "raw_col": "tire_weight_actual_first",
        "target_col": "tire_weight_target_first",
        "limit_type": "deviation_pct",    # 均值偏差百分比
        "metric_type": "deviation",       # 维持车间看盘习惯（非 CPK）
        "default_usl": None,              # 无查库，固定 ±0.28%（硬编码于下限函数）
        "default_lsl": None,
    }
}


def resolve_col_name(indicator: str, use_target: bool = False) -> str:
    """获取指定指标对应的 DuckDB 数据列名"""
    cfg = INDICATOR_CONFIG.get(indicator, INDICATOR_CONFIG["rfpp"])
    return cfg["target_col"] if (use_target and cfg["target_col"]) else cfg["raw_col"]


def get_tolerance(indicator: str, article10: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    """统一获取指标的公差限制 (USL, LSL)——原样保留查库与兜底口径。
    等价于旧 get_spec_limits (490)。weight 固定 ±0.28%，rfpp/rfh1 查库+group 回退+100 兜底，
    cony 查 conny_usl/conny_lsl 单侧回退 ±95。
    """
    if indicator == "weight":
        return 0.28, -0.28
    if article10:
        return get_spec_limits(article10, indicator)
    cfg = INDICATOR_CONFIG.get(indicator, INDICATOR_CONFIG["rfpp"])
    return cfg["default_usl"], cfg["default_lsl"]


def calc_metric(
    indicator: str,
    mean_val: float,
    std_val: float,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    target_val: Optional[float] = None
) -> float:
    """根据指标配置，自动路由是计算标准 CPK 还是均值偏差率"""
    cfg = INDICATOR_CONFIG.get(indicator, INDICATOR_CONFIG["rfpp"])
    if cfg["metric_type"] == "deviation":
        if target_val and abs(target_val) > 1e-6:
            return round((mean_val - target_val) / target_val * 100.0, 4)
        return 0.0
    return calc_cpk(mean_val, std_val, usl, lsl)
