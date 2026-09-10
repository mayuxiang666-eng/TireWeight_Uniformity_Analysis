# -*- coding: utf-8 -*-
"""
趋势与筛选 API 路由 (Trend & Filter Router)
处理全局规格列表、日期范围查询及宏观多维度 CPK 趋势统计请求
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.services.trend_service import (
    get_filter_articles as svc_get_filter_articles,
    get_filter_daterange as svc_get_filter_daterange,
    get_trend_cpk as svc_get_trend_cpk
)

router = APIRouter()


@router.get("/filters/articles")
def get_filter_articles(min_yield: int = Query(0)):
    """获取全量规格列表及各规格产量统计"""
    return svc_get_filter_articles(min_yield=min_yield)


@router.get("/filters/daterange")
def get_date_range():
    """获取当前数据的最小与最大生产日期范围"""
    return svc_get_filter_daterange()


@router.get("/trend/cpk")
def get_cpk_trend(
    grain: str = Query("daily"),     # "daily" | "hourly" | "minute" | "weekly"
    article10: Optional[str] = Query(None),
    exclude_articles: Optional[str] = Query(None), # 英文逗号分割的需剔除规格代码列表
    time_col: Optional[str] = Query("tu_first_loc_timestamp"),
    phase: Optional[str] = Query("all"),
    shift: Optional[str] = Query("all"),
    exclude_outliers: bool = Query(False)
):
    """获取宏观 CPK 趋势统计数据 (支持多时间粒度、全厂加权与单规格池化、三班与期别过滤)"""
    return svc_get_trend_cpk(
        grain=grain,
        article10=article10,
        exclude_articles=exclude_articles,
        time_col=time_col,
        phase=phase,
        shift=shift,
        exclude_outliers=exclude_outliers
    )
