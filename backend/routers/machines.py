# -*- coding: utf-8 -*-
"""
机台质量与工序流转 API 路由 (Machines Router)
包含机台 CPK、机台趋势下钻、Top3 负贡献预警机台、最优 TU、多机对比、全流程组合树、桑基图与最优路径
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.services.machine_service import (
    get_machine_cpk as svc_get_machine_cpk,
    get_machine_cpk_trend as svc_get_machine_cpk_trend,
    get_top_warning as svc_get_top_warning,
    get_best_tu as svc_get_best_tu,
    get_cpk_trend_comparison as svc_get_cpk_trend_comparison,
    get_top_warning_machines,
    get_best_tu_machine_for_spec,
    set_cgrs_comparator
)
from backend.services.process_flow_service import (
    get_machine_combination_tree as svc_get_machine_combination_tree,
    get_process_sankey as svc_get_process_sankey,
    get_best_process_sankey as svc_get_best_process_sankey,
    set_process_flow_helpers
)
from backend.services.cgrs_service import calculate_cgrs_cpk_comparison

# 路由初始化时注入跨服务计算能力
set_cgrs_comparator(calculate_cgrs_cpk_comparison)
set_process_flow_helpers(
    top_warning_provider=get_top_warning_machines,
    best_tu_provider=get_best_tu_machine_for_spec,
    cgrs_comparator=calculate_cgrs_cpk_comparison,
    machine_cpk_provider=svc_get_machine_cpk
)

router = APIRouter()


@router.get("/machines/cpk")
def get_machines_cpk(
    target_date: str = Query(...),
    article10: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
    tolerance: float = Query(0.8),
):
    """机台生产质量 CPK 列表"""
    return svc_get_machine_cpk(
        target_date=target_date,
        article10=article10,
        indicator=indicator,
        start_date=start_date,
        end_date=end_date,
        min_samples=min_samples,
        tolerance=tolerance
    )


@router.get("/machines/cpk/trend")
def get_machine_cpk_trend(
    machine: str = Query(...),
    workcenter_col: str = Query(...),
    indicator: str = Query("rfpp"), # "rfpp" | "rfh1"
    article10: Optional[str] = Query(None),
    mode: Optional[str] = Query(None), # "single" | "multi"
    tolerance: float = Query(0.8)
):
    """指定机台历史 CPK 趋势下钻"""
    return svc_get_machine_cpk_trend(
        machine=machine,
        workcenter_col=workcenter_col,
        indicator=indicator,
        article10=article10,
        mode=mode,
        tolerance=tolerance
    )


@router.get("/machines/combination-tree")
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
    """机台全工序组合关系拓扑树"""
    return svc_get_machine_combination_tree(
        spec=spec,
        start_wc=start_wc,
        end_wc=end_wc,
        indicator=indicator,
        start_date=start_date,
        end_date=end_date,
        target_date=target_date,
        min_samples=min_samples
    )


@router.get("/machines/process-sankey")
def get_machine_process_sankey(
    article10: str = Query(...),
    indicator: str = Query("rfpp"),
    target_date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(10),
    tolerance: float = Query(0.8)
):
    """全工序流转桑基图数据 (Sankey Flow Diagram)"""
    return svc_get_process_sankey(
        article10=article10,
        indicator=indicator,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        min_samples=min_samples,
        tolerance=tolerance
    )


@router.get("/machines/best-process-sankey")
def get_machine_best_process_sankey(
    article10: str = Query(...),
    indicator: str = Query("rfpp"),
    min_samples: int = Query(10),
):
    """全量数据集下的全流程标杆/最优工序流转路径"""
    return svc_get_best_process_sankey(
        article10=article10,
        indicator=indicator,
        min_samples=min_samples
    )


@router.get("/machines/top-warning")
def get_top_warning_api(
    spec: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    target_date: str = Query(..., description="target date YYYY-MM-DD"),
    n: int = Query(3, description="Top N count"),
    days: int = Query(3, description="days window"),
    min_samples: int = Query(1, description="min samples threshold"),
):
    """返回目标日期下负向贡献度 Top N 机台列表"""
    return svc_get_top_warning(
        spec=spec,
        indicator=indicator,
        target_date=target_date,
        n=n,
        days=days,
        min_samples=min_samples
    )


@router.get("/machines/best-tu")
def get_best_tu_api(
    article10: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    min_samples: int = Query(10, description="min samples threshold"),
):
    """查询指定规格在全量数据集下的最佳 TU (终检) 机台"""
    return svc_get_best_tu(
        article10=article10,
        indicator=indicator,
        min_samples=min_samples
    )


@router.get("/machines/cpk-trend-comparison")
def get_machine_cpk_trend_comparison(
    workcenter_type: str = Query("gt", description="机台工段类型：'gt' 或 'ct'/'cu'"),
    machines: str = Query(..., description="机台编号列表，逗号分隔，如 TB285,TB286"),
    article10: str = Query(..., description="当前选中规格代码 article10"),
    indicator: str = Query("rfpp", description="质量指标，如 rfpp, rfh1, cony, weight"),
    target_date: Optional[str] = Query(None, description="基准日期 YYYY-MM-DD，默认最新日期"),
    days: int = Query(14, description="对比天数，默认 14 天"),
    min_samples: int = Query(3, description="单日最低样本数门槛")
):
    """多机台 CPK 时序趋势对比及工艺调参叠加分析"""
    return svc_get_cpk_trend_comparison(
        workcenter_type=workcenter_type,
        machines=machines,
        article10=article10,
        target_date=target_date,
        indicator=indicator,
        days=days,
        min_samples=min_samples
    )
