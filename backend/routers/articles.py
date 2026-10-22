# -*- coding: utf-8 -*-
"""
轮胎规格看板 API 路由 (Articles Router)
处理规格期别、全量规格查询、预警看板、条码明细散点图、批次 CPK 趋势与批次条码明细
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.services.article_service import (
    get_article_phase as svc_get_article_phase,
    get_all_articles as svc_get_all_articles,
    get_warning_cpk as svc_get_warning_cpk,
    get_barcode_measurements as svc_get_barcode_measurements,
    get_lot_cpk_trend as svc_get_lot_cpk_trend,
    get_lot_barcode_detail as svc_get_lot_barcode_detail,
    set_article_helpers
)
from backend.services.machine_service import get_top_warning_machines, get_best_tu_machine_for_spec
from backend.services.cgrs_service import calculate_cgrs_cpk_comparison

# 路由初始化时注入跨服务计算能力
set_article_helpers(
    top_warning_provider=get_top_warning_machines,
    best_tu_provider=get_best_tu_machine_for_spec,
    cgrs_comparator=calculate_cgrs_cpk_comparison
)

router = APIRouter()


@router.get("/article/phase")
def get_article_phase_endpoint(article10: str = Query(...)):
    """查询指定规格的期别归属（三期、四期、三期&四期）"""
    return svc_get_article_phase(article10=article10)


@router.get("/articles/all")
def get_all_articles():
    """获取全量规格型号列表"""
    return svc_get_all_articles()


@router.get("/articles/warning-cpk")
def get_articles_warning_cpk(
    indicator: str = Query("rfpp"),       # "rfpp" | "rfh1" | "cony" | "weight"
    study_from: Optional[str] = Query(None),  # 仅作为分析目标日期使用
    study_to: Optional[str] = Query(None),
    only_declining: bool = Query(False),
    min_samples: int = Query(30),
    phase: Optional[str] = Query("all"),
    article10: Optional[str] = Query(None),
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    max_cpk: Optional[float] = Query(0.9),  # CPK 门槛上限过滤，默认只展示 CPK < max_cpk 的恶化规格
    shift: Optional[str] = Query("all")
):
    """预警规格型号排行 (全局 CPK 统计及恶化因果下钻)"""
    return svc_get_warning_cpk(
        indicator=indicator,
        study_from=study_from,
        study_to=study_to,
        only_declining=only_declining,
        min_samples=min_samples,
        phase=phase,
        article10=article10,
        time_col=time_col,
        max_cpk=max_cpk,
        shift=shift
    )


@router.get("/articles/barcode-measurements")
def get_article_barcode_measurements(
    article10: str = Query(..., description="选中的规格型号"),
    target_date: Optional[str] = Query(None, description="观察目标日期，如 2026-08-17"),
    indicator: str = Query("rfpp", description="指标类型：rfpp | rfh1 | cony | weight"),
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    phase: Optional[str] = Query("all"),
    shift: Optional[str] = Query("all")
):
    """获取指定规格在单日内全部单胎（Barcode）实际测量值的时序数据（Run Chart / I-Chart）"""
    return svc_get_barcode_measurements(
        article10=article10,
        target_date=target_date,
        indicator=indicator,
        time_col=time_col,
        phase=phase,
        shift=shift
    )


@router.get("/articles/lot-cpk-trend")
def get_article_lot_cpk_trend(
    article10: str = Query(...),
    target_date: Optional[str] = Query(None),
    indicator: str = Query("rfpp"),
    component: Optional[str] = Query(None),
    time_col: Optional[str] = Query("gt_loc_timestamp"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_samples: int = Query(1)
):
    """获取选中批次 (Lot) 溯源趋势数据"""
    return svc_get_lot_cpk_trend(
        article10=article10,
        target_date=target_date,
        indicator=indicator,
        component=component,
        time_col=time_col,
        start_date=start_date,
        end_date=end_date,
        min_samples=min_samples
    )


@router.get("/articles/lot-barcode-detail")
def get_lot_barcode_detail(
    article10: str = Query(...),
    lot: str = Query(...),
    component: Optional[str] = Query(None),
    indicator: str = Query("rfpp")
):
    """获取指定工序批次下各轮胎的条码明细测量值分布"""
    return svc_get_lot_barcode_detail(
        article10=article10,
        lot=lot,
        component=component,
        indicator=indicator
    )
