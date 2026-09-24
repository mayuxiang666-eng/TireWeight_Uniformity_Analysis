# -*- coding: utf-8 -*-
"""
CGRS 工艺调参 API 路由 (CGRS Router)
包含调参记录检索、受控变量时序对照分析、全厂双工段最佳扫描推荐与单机台两级兜底参数推荐
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.services.cgrs_service import (
    get_cgrs_records as svc_get_cgrs_records,
    get_cgrs_controlled_analysis as svc_get_cgrs_controlled_analysis,
    recommend_best_for_spec as svc_recommend_best_for_spec,
    recommend_for_machine as svc_recommend_for_machine
)

router = APIRouter()


@router.get("/cgrs/records")
def get_cgrs_records(
    workcenter: str = Query(..., description="成型机台编号，如 TB122 或 TB283"),
    date: Optional[str] = Query(None, description="查询日期，格式 YYYY-MM-DD"),
    article: Optional[str] = Query(None, description="规格代码 article10 (可选，支持精确与7位前缀匹配)"),
    indicator: Optional[str] = Query("rfpp", description="指标类型，如 rfpp, rfh1, cony, weight"),
    event_time: Optional[str] = Query(None, description="精确调参时间戳，如 2026-09-16 23:13:21")
):
    """根据成型机台编号、日期以及规格代码查询 CGRS 参数修改记录（支持按具体调参事件时间戳精确定位）"""
    return svc_get_cgrs_records(
        workcenter=workcenter,
        date=date,
        article=article,
        indicator=indicator,
        event_time=event_time
    )


@router.get("/cgrs/controlled-analysis")
def get_cgrs_controlled_analysis(
    workcenter: str = Query(..., description="成型机台编号，如 TB122 或 TB243"),
    date: Optional[str] = Query(None, description="查询日期，格式 YYYY-MM-DD"),
    article: Optional[str] = Query(None, description="规格代码 article10 (可选)"),
    indicator: Optional[str] = Query("rfpp", description="指标类型，如 rfpp, rfh1, cony, weight"),
    top_machines: Optional[str] = Query(None, description="前端传入的全局影响度<0的Top 3嫌疑机台列表，逗号分隔，如 TU6,CU718,TU3"),
    same_day_only: bool = Query(False, description="是否仅看调参当天样本，False为允许跨天取样"),
    min_samples: int = Query(1, description="每条路径改前/改后最低样本门槛，低于此值的路径将被过滤，默认 1"),
    event_time: Optional[str] = Query(None, description="精确调参时间戳，如 2026-09-16 23:13:21")
):
    """成型机 CGRS 控制变量分析（成型 GT ➔ 硫化 CT ➔ 终检 TU 全流程路径拆分与有效路径加总 CPK 对照，支持按调参时间戳直接锚定）"""
    return svc_get_cgrs_controlled_analysis(
        workcenter=workcenter,
        date=date,
        article=article,
        indicator=indicator,
        top_machines=top_machines,
        same_day_only=same_day_only,
        min_samples_threshold=min_samples,
        event_time=event_time
    )


@router.get("/cgrs/param-recommendation")
def get_param_recommendation(
    article: str = Query(..., description="article10 spec code"),
    indicator: str = Query("rfpp", description="indicator"),
    target_date: Optional[str] = Query(None, description="target date YYYY-MM-DD")
):
    """全厂成型 (GT) 与硫化 (CU) 双工段近 30 天最佳工艺调参扫描推荐 (驱动全流程桑基图卡片)"""
    return svc_recommend_best_for_spec(
        article=article,
        indicator=indicator,
        target_date=target_date
    )


@router.get("/cgrs/recommended-params")
def get_cgrs_recommended_params(
    machine: str = Query(..., description="机台编号，如 TB262 或 CUM03"),
    article10: str = Query(..., description="10位轮胎规格，如 0315567079"),
    workcenter_type: str = Query("gt", description="工段类型: gt 或 ct"),
    indicator: str = Query("rfpp", description="指标"),
    target_date: Optional[str] = Query(None, description="观察基准日期，如 2026-08-17"),
    reason: str = Query("degradation", description="推荐原因: degradation 或 new_machine")
):
    """单机台智能调参推荐（强规格锁定 + 两级兜底推荐引擎，驱动机台弹窗推荐）"""
    res = svc_recommend_for_machine(
        machine=machine,
        article10=article10,
        workcenter_type=workcenter_type,
        indicator=indicator,
        target_date=target_date,
        reason=reason
    )

    # 针对成型机台 (TB/GT) 与 硫化机台 (CU/CT)，挂载对应工序核心工艺参数四列状态对比表
    if isinstance(res, dict):
        try:
            from backend.services.status_cgrs_service import calculate_status_recommendation_comparison
            rec_params = res.get("params", [])
            # 若 params 内部没有事件全局时间，将 best_event_time 随路注入
            best_t = res.get("best_event_time")
            rec_events_payload = []
            for rp in rec_params:
                item_dict = dict(rp)
                if best_t and not item_dict.get("event_time"):
                    item_dict["event_time"] = best_t
                rec_events_payload.append(item_dict)

            comp_res = calculate_status_recommendation_comparison(
                machine=machine,
                article10=article10,
                workcenter_type=workcenter_type,
                target_date=target_date,
                recommendation_events=rec_events_payload
            )
            has_snap = comp_res.get("has_status_snapshot", False)
            res["has_status_snapshot"] = has_snap
            res["process_type"] = comp_res.get("process_type", "")
            res["process_type_id"] = comp_res.get("process_type_id", "")
            res["changed_params_count"] = comp_res.get("changed_params_count", 0)
            res["total_params"] = comp_res.get("total_params", 0)
            res["current_base_date"] = comp_res.get("current_base_date", target_date or "")
            res["recommend_event_date"] = comp_res.get("recommend_event_date", best_t or "")
            res["has_current_snapshot"] = comp_res.get("has_current_snapshot", False)
            res["has_event_snapshot"] = comp_res.get("has_event_snapshot", False)
            res["recommend_machine"] = res.get("source_machine") or comp_res.get("recommend_machine") or machine
            res["is_optimal_no_diff"] = res.get("is_optimal_no_diff", False) or comp_res.get("is_optimal_no_diff", False)
            res["status_comparison"] = comp_res.get("status_comparison", [])
        except Exception as e:
            res["status_comparison_error"] = str(e)

    return res
