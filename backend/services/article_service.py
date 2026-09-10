# -*- coding: utf-8 -*-
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

def get_article_phase(article10: str):
    if not article10:
        return {"status": "success", "data": {"phase_label": "", "p3_count": 0, "p4_count": 0}}
    try:
        parquet_path = get_cleaned_data_path()
        con = duckdb.connect()
        sql = f"""
            SELECT 
                SUM(CASE WHEN LOWER(ct_shop) LIKE '%p4%' THEN 1 ELSE 0 END) as p4_cnt,
                SUM(CASE WHEN LOWER(ct_shop) NOT LIKE '%p4%' OR ct_shop IS NULL THEN 1 ELSE 0 END) as p3_cnt
            FROM read_parquet('{parquet_path}')
            WHERE article10 = '{article10}'
        """
        df_res = con.execute(sql).df()
        con.close()
        p4 = int(df_res.iloc[0]['p4_cnt'] or 0)
        p3 = int(df_res.iloc[0]['p3_cnt'] or 0)
        if p4 > 0 and p3 == 0:
            phase_label = "四期"
        elif p3 > 0 and p4 == 0:
            phase_label = "三期"
        elif p3 + p4 > 0:
            phase_label = "三期 & 四期"
        else:
            phase_label = ""
        return {
            "status": "success",
            "data": {
                "article10": article10,
                "phase_label": phase_label,
                "p3_count": p3,
                "p4_count": p4
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}



def get_all_articles():
    try:
        rows = qry("SELECT DISTINCT article10 FROM clean_yield WHERE article10 IS NOT NULL AND article10 != '' ORDER BY 1")
        articles_list = [r['article10'] for r in rows]
        return {"status": "success", "data": sanitize_data(articles_list)}
    except Exception as e:
        return {"status": "error", "message": str(e)}



def get_spec_warning_machines_detailed(item: dict, indicator: str, target_date: str, min_samples: int = 10) -> list:
    article10 = item.get("article10")
    if not article10 or not target_date:
        fallback_item = {
            **item,
            "warning_machine": "无",
            "warning_level": "none",
            "primary_dot": "",
            "cpk_pct_change": None,
            "action_text": "-",
            "action_type": "info",
            "action_tooltip": "",
            "can_click_recommend": False,
            "recommend_stage": "gt",
            "status_badges": []
        }
        return [fallback_item]

    try:
        _tw = _get_top_warning_provider()
        top_list = _tw(
            n=3,
            article10=article10,
            indicator=indicator,
            target_date=target_date,
            min_samples=min_samples,
            include_tu=True
        )
        if not top_list and min_samples > 1:
            _tw = _get_top_warning_provider()
        top_list = _tw(
                n=3,
                article10=article10,
                indicator=indicator,
                target_date=target_date,
                min_samples=1,
                include_tu=True
            )

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        d_start = (target_dt - timedelta(days=3)).strftime("%Y-%m-%d")

        if indicator == "weight":
            ind_col = "((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0)"
            usl, lsl = None, None
        elif indicator == "cony":
            ind_col = "cony_first"
            usl, lsl = get_spec_limits(article10, indicator)
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
            usl, lsl = get_spec_limits(article10, indicator)

        _bt = _get_best_tu_provider()
        best_tu, best_tu_val = _bt(article10, indicator, min_samples=1) if _bt else (None, None)

        valid_machines = []
        seen_machines = set()

        for m_item in top_list:
            mach = m_item["machine"]
            wc_col = m_item.get("workcenter_col") or ""
            seen_machines.add(mach)

            # 4 天历史数据查询
            hist_sql = f"""
                SELECT 
                    CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) as d,
                    COUNT(*) as cnt,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v
                FROM clean_yield
                WHERE article10 = ?
                  AND (gt_workcenter = ? OR ct_workcenter = ? OR tu_first_workcenter = ?)
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1
                ORDER BY 1
            """
            rows = qry(hist_sql, [article10, mach, mach, mach, d_start, target_date])

            t0_cpk = None
            prev_cpks = []
            for r in rows:
                d_str = str(r['d'])
                avg_v = float(r['avg_v'] or 0)
                std_v = float(r['std_v'] or 0)
                cpk_val = avg_v if indicator == "weight" else calc_cpk(avg_v, std_v, usl, lsl)
                if d_str == target_date:
                    t0_cpk = cpk_val
                else:
                    if cpk_val is not None:
                        prev_cpks.append(cpk_val)

            mu_3d = sum(prev_cpks) / len(prev_cpks) if prev_cpks else None
            is_new_online = bool(t0_cpk is not None and not prev_cpks)
            cpk_pct_change = None
            if t0_cpk is not None and mu_3d is not None and mu_3d > 0:
                cpk_pct_change = round(((t0_cpk - mu_3d) / mu_3d) * 100, 1)

            # 过滤逻辑：自动过滤当班 CPK 提升（> 0）的机台，仅保留恶化或新机台
            if cpk_pct_change is not None and cpk_pct_change > 0:
                continue

            # 多天在榜统计
            days_on_board = 1
            days_rank1 = 1 if m_item.get("rank") == 1 else 0
            for day_offset in (1, 2):
                prev_d = (target_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                _tw = _get_top_warning_provider()
                prev_top = _tw(n=3, article10=article10, indicator=indicator, target_date=prev_d, min_samples=1, include_tu=True)
                for idx, pm in enumerate(prev_top):
                    if pm["machine"] == mach:
                        days_on_board += 1
                        if idx == 0:
                            days_rank1 += 1
                        break

            # CGRS 调参恶化因果判定 (仅成型与硫化工段设备)
            has_degraded_tuning = False
            degraded_tooltip = ""
            if indicator != "weight" and not mach.startswith("TU"):
                try:
                    _cc = _get_cgrs_comparator()
                    cgrs_comp = _cc(
                        workcenter=mach,
                        article10=article10,
                        target_date=target_date,
                        indicator=indicator,
                        limit_n=20
                    )
                    if cgrs_comp and cgrs_comp.get("has_cgrs"):
                        ev_list = cgrs_comp.get("events_summary") or []
                        # 查找是否存在改后导致质量恶化 (cpk_diff < 0) 的有效调参事件
                        degraded_ev = next((ev for ev in ev_list if ev.get("cpk_diff") is not None and ev.get("cpk_diff") < 0), None)
                        if degraded_ev:
                            has_degraded_tuning = True
                            diff_val = degraded_ev.get('cpk_diff', 0.0)
                            yoy_val = degraded_ev.get('yoy_pct', 0.0)
                            degraded_tooltip = f"调参后恶化：CPK 变化 {diff_val:+.3f} ({yoy_val:+.1f}%)"
                except Exception as err:
                    print(f"[Warning] calculate_cgrs_cpk_comparison failed for {mach}: {err}")

            is_dominant_top1 = days_rank1 >= 2
            is_red = has_degraded_tuning or is_dominant_top1
            is_drop_35 = cpk_pct_change is not None and cpk_pct_change <= -35
            is_cont_top23 = days_on_board >= 3 and days_rank1 < 2
            is_orange = (not is_red) and (is_drop_35 or is_cont_top23)
            is_yellow = (not is_red and not is_orange)

            status_badges = []
            if is_red:
                warning_level = "red"
                primary_dot = "🔴"
                if has_degraded_tuning:
                    status_badges.append({"color": "red", "text": "🔴 调参恶化", "tooltip": degraded_tooltip or "检测到 CGRS 调参后 CPK 下降"})
                if is_dominant_top1:
                    status_badges.append({"color": "red", "text": "🔴 持续霸榜(#1)", "tooltip": f"在近 3 天中有 {days_rank1} 天位列负贡献榜第 1 名"})
            elif is_orange:
                warning_level = "orange"
                primary_dot = "🟠"
                if is_drop_35:
                    status_badges.append({"color": "orange", "text": "🟠 骤降超35%", "tooltip": f"当班 CPK 相比前 3 天均值降幅达 {abs(cpk_pct_change)}%"})
                if is_cont_top23:
                    status_badges.append({"color": "orange", "text": "🟠 持续在榜", "tooltip": "近 3 天均进入负贡献榜"})
                if not status_badges:
                    status_badges.append({"color": "orange", "text": "🟠 持续在榜", "tooltip": f"近 3 天有 {days_on_board} 天在榜"})
            else:
                warning_level = "yellow"
                primary_dot = "🟡"
                if is_new_online:
                    status_badges.append({"color": "yellow", "text": "🟡 新上线", "tooltip": "该机台在观察日前 3 天无生产记录，今日新换型上线排产，处于试产磨合阶段"})
                elif days_on_board >= 2:
                    status_badges.append({"color": "yellow", "text": "🟡 持续在榜", "tooltip": f"该机台近 3 天有 {days_on_board} 天进入负向贡献监控榜（CPK 偏低拉低质量）"})
                else:
                    status_badges.append({"color": "yellow", "text": "🟡 负贡献在榜", "tooltip": "当日单机 CPK 偏低，对该规格产生负向拉低贡献，位列拉低监控榜"})

            is_tu = wc_col == "tu_first_workcenter" or mach.startswith("TU")
            is_ct = wc_col == "ct_workcenter" or mach.startswith("CU") or mach.startswith("CT")
            stage = "ct" if is_ct else "gt"

            if is_tu:
                if best_tu:
                    action_text = f"推荐机台: {best_tu}"
                    action_type = "success"
                    action_tooltip = f"该规格全量最佳路径中的标杆终检机台为 {best_tu}。建议优先导流至该机台进行终检质量把关"
                else:
                    action_text = "-"
                    action_type = "info"
                    action_tooltip = "终检 TU 设备暂无标杆机台推荐"
                can_click_recommend = False
            else:
                action_text = "查看推荐参数"
                action_type = "primary"
                action_tooltip = "点击调取并深度分析该机台/工段历史最优工艺参数组合"
                can_click_recommend = True

            valid_machines.append({
                **item,
                "warning_machine": mach,
                "warning_level": warning_level,
                "primary_dot": primary_dot,
                "cpk_pct_change": cpk_pct_change,
                "is_new_online": is_new_online,
                "rank": m_item.get("rank", 99),
                "impact_score": m_item.get("impact_score", 0.0),
                "action_text": action_text,
                "action_type": action_type,
                "action_tooltip": action_tooltip,
                "can_click_recommend": can_click_recommend,
                "recommend_stage": stage,
                "status_badges": status_badges,
                "is_gt_special": False
            })

        # 检查成型机 (GT) 专项预警
        spec_prefix8 = article10[:8] if len(article10) >= 8 else article10
        gt_sql = f"""
            SELECT DISTINCT gt_workcenter
            FROM clean_yield
            WHERE TRY_CAST(article10 AS VARCHAR) LIKE '%{spec_prefix8}%'
              AND gt_workcenter IS NOT NULL
              AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) = ?::DATE
        """
        gt_candidates = qry(gt_sql, [target_date])
        for g_row in gt_candidates:
            g_mach = g_row.get("gt_workcenter")
            if not g_mach or g_mach in seen_machines:
                continue

            hist_sql = f"""
                SELECT 
                    CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) as d,
                    COUNT(*) as cnt,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v
                FROM clean_yield
                WHERE article10 = ?
                  AND gt_workcenter = ?
                  AND CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE) BETWEEN ?::DATE AND ?::DATE
                GROUP BY 1
                ORDER BY 1
            """
            g_rows = qry(hist_sql, [article10, g_mach, d_start, target_date])
            g_t0_cpk = None
            g_prev_cpks = []
            for r in g_rows:
                d_str = str(r['d'])
                avg_v = float(r['avg_v'] or 0)
                std_v = float(r['std_v'] or 0)
                c_val = avg_v if indicator == "weight" else calc_cpk(avg_v, std_v, usl, lsl)
                if d_str == target_date:
                    g_t0_cpk = c_val
                else:
                    if c_val is not None:
                        g_prev_cpks.append(c_val)

            g_mu_3d = sum(g_prev_cpks) / len(g_prev_cpks) if g_prev_cpks else None
            g_pct_chg = None
            if g_t0_cpk is not None and g_mu_3d is not None and g_mu_3d > 0:
                g_pct_chg = round(((g_t0_cpk - g_mu_3d) / g_mu_3d) * 100, 1)

            # 成型机 CPK 骤降专项预警门槛: <= -30%
            if g_pct_chg is not None and g_pct_chg <= -30:
                is_drop_35 = g_pct_chg <= -35
                w_level = "orange" if is_drop_35 else "yellow"
                p_dot = "🟠" if is_drop_35 else "🟡"

                valid_machines.append({
                    **item,
                    "warning_machine": g_mach,
                    "warning_level": w_level,
                    "primary_dot": p_dot,
                    "cpk_pct_change": g_pct_chg,
                    "rank": 99,
                    "impact_score": 0.0,
                    "action_text": "查看推荐参数",
                    "action_type": "primary",
                    "action_tooltip": "成型机专项预警：点击调取并深度分析该机台历史最优工艺参数",
                    "can_click_recommend": True,
                    "recommend_stage": "gt",
                    "status_badges": [{
                        "color": w_level,
                        "text": "🟠 成型骤降(>35%)" if is_drop_35 else "🟡 成型专项(>30%)",
                        "tooltip": f"成型机专项预警：当班 CPK 降幅达 {abs(g_pct_chg)}%"
                    }],
                    "is_gt_special": True
                })

        if not valid_machines:
            # 兜底：若均无恶化，保留 Top 1 作为信息行
            fallback_m = top_list[0]["machine"] if top_list else "无"
            fallback_wc = top_list[0].get("workcenter_col") if top_list else ""
            fallback_is_tu = fallback_wc == "tu_first_workcenter" or fallback_m.startswith("TU")
            fallback_stage = "tu" if fallback_is_tu else ("ct" if fallback_m.startswith("CU") or fallback_m.startswith("CT") else "gt")
            fallback_act = f"推荐机台: {best_tu}" if (fallback_is_tu and best_tu) else ("查看推荐参数" if not fallback_is_tu else "-")
            valid_machines.append({
                **item,
                "warning_machine": fallback_m,
                "warning_level": "yellow",
                "primary_dot": "🟡",
                "cpk_pct_change": None,
                "action_text": fallback_act,
                "action_type": "success" if (fallback_is_tu and best_tu) else "primary",
                "action_tooltip": "质量稳定",
                "can_click_recommend": not fallback_is_tu,
                "recommend_stage": fallback_stage,
                "status_badges": [{"color": "yellow", "text": "🟡 质量在榜", "tooltip": "当日入榜机台"}],
                "is_gt_special": False
            })

        return valid_machines
    except Exception as e:
        print(f"Error getting detailed machines for {article10}: {e}")
        fallback_item = {
            **item,
            "warning_machine": "无",
            "warning_level": "none",
            "primary_dot": "",
            "cpk_pct_change": None,
            "action_text": "-",
            "action_type": "info",
            "action_tooltip": "",
            "can_click_recommend": False,
            "recommend_stage": "gt",
            "status_badges": []
        }
        return [fallback_item]




def get_warning_cpk(
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
    try:
        if hasattr(min_samples, "default"): min_samples = min_samples.default
        if hasattr(indicator, "default"): indicator = indicator.default
        if hasattr(study_from, "default"): study_from = study_from.default
        if hasattr(study_to, "default"): study_to = study_to.default
        if hasattr(phase, "default"): phase = phase.default
        if hasattr(time_col, "default"): time_col = time_col.default
        if hasattr(max_cpk, "default"): max_cpk = max_cpk.default
        if hasattr(shift, "default"): shift = shift.default

        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 30
        parsed_max_cpk = None
        if max_cpk is not None:
            try:
                val = float(max_cpk)
                if val > 0 and val < 99:
                    parsed_max_cpk = val
            except (ValueError, TypeError):
                parsed_max_cpk = 0.9
        else:
            parsed_max_cpk = 0.9

        # 确定分析目标日期（取 study_to，单日点击时 study_from == study_to）
        target_date = study_to or study_from
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"

        # 探测数据库中的最新有效生产日 (08:00~次日08:00)
        date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"
        max_db_res = qry(f"SELECT MAX({date_col}) AS max_d FROM clean_yield")
        max_db_date = str(max_db_res[0]['max_d']) if (max_db_res and max_db_res[0].get('max_d')) else None

        if not target_date:
            valid_d_res = qry(f"""
                SELECT {date_col} AS d
                FROM clean_yield
                WHERE {date_col} IS NOT NULL
                GROUP BY 1, article10
                HAVING COUNT(*) >= ?
                ORDER BY 1 DESC
                LIMIT 1
            """, [min_samples])
            if valid_d_res and valid_d_res[0].get('d'):
                target_date = str(valid_d_res[0]['d'])
            else:
                target_date = max_db_date

        # 判断当前查看的日期是否为数据库中的最新一天
        is_latest_date = bool(target_date and max_db_date and str(target_date) == str(max_db_date))

        if not isinstance(phase, str):
            phase = "all"
        if not isinstance(article10, str):
            article10 = None

        phase_cond = get_phase_sql_condition(phase)
        article_cond = " AND article10 = ?" if article10 else ""
        shift_cond = f" AND {build_production_time_where(time_col=time_col, shift=shift)}" if (shift and shift != 'all') else ""

        if indicator == "weight":
            # 胎重指标下的单日偏差贡献度/CPK排行
            sql_overall = f"""
                SELECT
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_actual,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) AS sum_target
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                  {shift_cond}
            """
            overall_rows = qry(sql_overall, [target_date])
            overall_actual = float(overall_rows[0]['sum_actual'] or 0.0) if overall_rows else 0.0
            overall_target = float(overall_rows[0]['sum_target'] or 0.0) if overall_rows else 0.0
            overall_diff = (overall_actual - overall_target) / overall_target * 100.0 if overall_target > 0 else 0.0

            sql_target = f"""
                SELECT
                    article10,
                    COUNT(*) AS sample_size,
                    COUNT(CASE WHEN ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' THEN 1 END) AS p3_count,
                    COUNT(CASE WHEN ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 END) AS p4_count,
                    SUM(TRY_CAST(tire_weight_actual_first AS DOUBLE)) AS sum_actual,
                    SUM(TRY_CAST(tire_weight_target_first AS DOUBLE)) AS sum_target
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                  {article_cond}
                GROUP BY 1
                HAVING COUNT(*) >= ?
            """
            params = [target_date]
            if article10:
                params.append(article10)
            params.append(min_samples if not article10 else 1)

            rows = qry(sql_target, params)
            if not rows:
                return {"status": "success", "data": []}
                
            total_n = sum(int(r['sample_size']) for r in rows)
            if total_n == 0:
                return {"status": "success", "data": []}
            
            results = []
            for r in rows:
                art = r['article10']
                n = int(r['sample_size'])
                p3_cnt = int(r.get('p3_count') or 0)
                p4_cnt = int(r.get('p4_count') or 0)
                tot_p = p3_cnt + p4_cnt
                if p4_cnt > 0 and p3_cnt == 0:
                    phase_label = "四期"
                elif p3_cnt > 0 and p4_cnt == 0:
                    phase_label = "三期"
                elif tot_p > 0:
                    p3_pct = int(round(p3_cnt / tot_p * 100))
                    p4_pct = int(round(p4_cnt / tot_p * 100))
                    phase_label = f"三期 & 四期 (3期 {p3_pct}% | 4期 {p4_pct}%)"
                else:
                    phase_label = "三期"

                sum_act = float(r['sum_actual'])
                sum_tar = float(r['sum_target'])
                spec_diff = (sum_act - sum_tar) / sum_tar * 100.0 if sum_tar > 0 else 0.0
                contrib = (spec_diff - overall_diff) * (n / total_n) if total_n > 0 else 0.0
                
                results.append({
                    "article10": art,
                    "stable_score": round(contrib, 4), # 贡献度
                    "single_cpk": round(spec_diff, 4),   # 规格有符号偏差 %
                    "avg_cpk": round(overall_diff, 4),   # 全厂有符号偏差 %
                    "sample_size": n,
                    "p3_count": p3_cnt,
                    "p4_count": p4_cnt,
                    "phase_label": phase_label,
                })
                
            if is_latest_date:
                # 查看最新一天：在样本门槛过滤下，由最低到最高按照单规格 CPK (偏差率) 升序排列
                results.sort(key=lambda x: x['single_cpk'])
            else:
                # 查看历史记录：按负向贡献度绝对值倒序
                results.sort(key=lambda x: abs(x['stable_score']), reverse=True)

            top_results = results if article10 else results[:10]
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                spec_machine_groups = list(executor.map(
                    lambda it: get_spec_warning_machines_detailed(it, "weight", target_date, min_samples if not article10 else 1),
                    top_results
                ))

            level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
            processed_groups = []
            for g in spec_machine_groups:
                if not g:
                    continue
                # 规格内机台排序：预警颜色等级优先 (🔴 > 🟠 > 🟡) -> 负向贡献度排名优先 (Rank 1 > Rank 2 > Rank 3) -> 跌幅优先
                g.sort(key=lambda m: (
                    level_map.get(m.get("warning_level", "none"), 3),
                    m.get("rank", 99),
                    m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
                ))
                spec_max_level = g[0].get("warning_level", "none")
                stable_score = g[0].get("stable_score", 0)
                processed_groups.append({
                    "spec_max_level": spec_max_level,
                    "stable_score": stable_score,
                    "machines": g
                })

            # 规格两级排序：🔴 > 🟠 > 🟡，同级按负向贡献度绝对值从重到轻
            processed_groups.sort(key=lambda pg: (
                level_map.get(pg["spec_max_level"], 3),
                -abs(pg["stable_score"])
            ))

            final_rows = []
            for pg in processed_groups:
                machs = pg["machines"]
                span_count = len(machs)
                for idx, m in enumerate(machs):
                    m["row_span"] = span_count if idx == 0 else 0
                    final_rows.append(m)

            return {
                "status": "success",
                "is_latest_date": is_latest_date,
                "target_date": target_date,
                "data": sanitize_data(final_rows)
            }

        ind_col = "cony_first" if indicator == "cony" else ("rfppwc_first" if indicator == "rfpp" else "rfh1wc_first")
        
        # 1. 查询当天全厂所有规格数据，用于计算全厂加权系统 CPK 基准
        sql_all = f"""
            SELECT
                article10,
                COUNT(*) AS sample_size,
                COUNT(CASE WHEN ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' THEN 1 END) AS p3_count,
                COUNT(CASE WHEN ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 END) AS p4_count,
                AVG(TRY_CAST({ind_col} AS DOUBLE)) AS avg_v,
                STDDEV(TRY_CAST({ind_col} AS DOUBLE)) AS std_v,
                COALESCE(ANY_VALUE(standard_rfpp),
                         CASE ANY_VALUE("group")
                             WHEN 'GROUP 1'  THEN 10.5
                             WHEN 'GROUP 2A' THEN 11.5
                             WHEN 'GROUP 2B' THEN 12.5
                             WHEN 'GROUP 3'  THEN 12.5
                         END) * 10.0 AS usl_rfpp,
                COALESCE(ANY_VALUE(standard_rfh1),
                         CASE ANY_VALUE("group")
                             WHEN 'GROUP 1'  THEN 7.5
                             WHEN 'GROUP 2A' THEN 8.5
                             WHEN 'GROUP 2B' THEN 9.0
                             WHEN 'GROUP 3'  THEN 9.5
                         END) * 10.0 AS usl_rfh1
            FROM clean_yield
            WHERE {date_col} = ?::DATE
              AND {ind_col} IS NOT NULL
              {phase_cond}
            GROUP BY 1
            HAVING COUNT(*) >= 1
        """
        rows_all = qry(sql_all, [target_date])
        if not rows_all:
            return {"status": "success", "is_latest_date": is_latest_date, "data": []}

        valid_specs = []
        total_n = 0
        weighted_cpk_sum = 0.0

        for r in rows_all:
            art = r['article10']
            n = r['sample_size']
            p3_cnt = int(r.get('p3_count') or 0)
            p4_cnt = int(r.get('p4_count') or 0)
            tot_p = p3_cnt + p4_cnt
            if p4_cnt > 0 and p3_cnt == 0:
                phase_label = "四期"
            elif p3_cnt > 0 and p4_cnt == 0:
                phase_label = "三期"
            elif tot_p > 0:
                p3_pct = int(round(p3_cnt / tot_p * 100))
                p4_pct = int(round(p4_cnt / tot_p * 100))
                phase_label = f"三期 & 四期 (3期 {p3_pct}% | 4期 {p4_pct}%)"
            else:
                phase_label = "三期"

            avg_v = r['avg_v'] or 0.0
            std_v = r['std_v'] or 0.0
            
            if indicator == "cony":
                usl_v, lsl_v = get_spec_limits(art, "cony")
                val = calc_cpk(avg_v, std_v, usl_v, lsl_v)
            else:
                usl_v = r['usl_rfpp'] if indicator == "rfpp" else r['usl_rfh1']
                if std_v > 1e-6 and usl_v is not None:
                    val = calc_cpk(avg_v, std_v, usl_v, None)
                else:
                    val = 1.33
            
            if np.isnan(val) or np.isinf(val):
                continue
                
            valid_specs.append({
                "article10": art,
                "val": val,
                "n": n,
                "p3_count": p3_cnt,
                "p4_count": p4_cnt,
                "phase_label": phase_label
            })
            if n >= 5:
                weighted_cpk_sum += val * n
                total_n += n

        if total_n == 0 and valid_specs:
            total_n = sum(s['n'] for s in valid_specs)
            weighted_cpk_sum = sum(s['val'] * s['n'] for s in valid_specs)

        if total_n == 0:
            return {"status": "success", "is_latest_date": is_latest_date, "data": []}

        avg_cpk = weighted_cpk_sum / total_n

        # 如果指定了具体规格 article10
        if article10:
            target_spec = next((s for s in valid_specs if s['article10'] == article10), None)
            if not target_spec:
                return {"status": "success", "is_latest_date": is_latest_date, "data": []}
            
            neg_contrib = (avg_cpk - target_spec['val']) * target_spec['n']
            single_item = {
                "article10": target_spec['article10'],
                "stable_score": round(neg_contrib, 4),
                "single_cpk": round(target_spec['val'], 4),
                "avg_cpk": round(avg_cpk, 4),
                "sample_size": target_spec['n'],
                "p3_count": target_spec['p3_count'],
                "p4_count": target_spec['p4_count'],
                "phase_label": target_spec['phase_label'],
            }
            detailed_machines = get_spec_warning_machines_detailed(single_item, indicator, target_date, min_samples=1)
            level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
            detailed_machines.sort(key=lambda m: (
                level_map.get(m.get("warning_level", "none"), 3),
                m.get("rank", 99),
                m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
            ))
            span_count = len(detailed_machines)
            for idx, m in enumerate(detailed_machines):
                m["row_span"] = span_count if idx == 0 else 0
            return {
                "status": "success",
                "is_latest_date": is_latest_date,
                "target_date": target_date,
                "data": sanitize_data(detailed_machines)
            }

        # 未指定规格：全厂规格负向贡献/CPK 排行
        results = []
        for s in valid_specs:
            if s['n'] < min_samples:
                continue
            
            if not is_latest_date:
                # 历史日期：保持原逻辑，只展示高风险且有负向贡献的规格
                if parsed_max_cpk is not None and s['val'] >= parsed_max_cpk:
                    continue
                neg_contrib = (avg_cpk - s['val']) * s['n']
                if neg_contrib <= 0:
                    continue
            else:
                # 最新一天：计算负向贡献，保留符合样本门槛的所有规格以方便 CPK 从低到高展示
                neg_contrib = (avg_cpk - s['val']) * s['n']
            
            results.append({
                "article10": s['article10'],
                "stable_score": round(neg_contrib, 4),
                "single_cpk": round(s['val'], 4),
                "avg_cpk": round(avg_cpk, 4),
                "sample_size": s['n'],
                "p3_count": s['p3_count'],
                "p4_count": s['p4_count'],
                "phase_label": s['phase_label'],
            })

        if is_latest_date:
            # 查看最新一天：在样本门槛过滤下，由最低到最高按照 CPK 升序排行展示规格 (CPK 越低越靠前)
            results.sort(key=lambda x: x['single_cpk'])
        else:
            # 查看历史记录：按负向贡献度绝对值倒序
            results.sort(key=lambda x: abs(x['stable_score']), reverse=True)

        top_results = results[:10]

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            spec_machine_groups = list(executor.map(
                lambda it: get_spec_warning_machines_detailed(it, indicator, target_date, min_samples),
                top_results
            ))

        level_map = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
        processed_groups = []
        for g in spec_machine_groups:
            if not g:
                continue
            # 规格内机台排序：预警颜色等级优先 (🔴 > 🟠 > 🟡) -> 负向贡献度排名优先 (Rank 1 > Rank 2 > Rank 3) -> 跌幅优先
            g.sort(key=lambda m: (
                level_map.get(m.get("warning_level", "none"), 3),
                m.get("rank", 99),
                m.get("cpk_pct_change") if m.get("cpk_pct_change") is not None else 999
            ))
            spec_max_level = g[0].get("warning_level", "none")
            stable_score = g[0].get("stable_score", 0)
            processed_groups.append({
                "spec_max_level": spec_max_level,
                "stable_score": stable_score,
                "machines": g
            })

        # 规格两级排序：🔴 > 🟠 > 🟡，同级按负向贡献度绝对值从重到轻
        processed_groups.sort(key=lambda pg: (
            level_map.get(pg["spec_max_level"], 3),
            -abs(pg["stable_score"])
        ))

        final_rows = []
        for pg in processed_groups:
            machs = pg["machines"]
            span_count = len(machs)
            for idx, m in enumerate(machs):
                m["row_span"] = span_count if idx == 0 else 0
                final_rows.append(m)

        return {
            "status": "success",
            "is_latest_date": is_latest_date,
            "target_date": target_date,
            "data": sanitize_data(final_rows)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}





def get_barcode_measurements(
    article10: str,
    target_date: Optional[str] = None,
    indicator: str = "rfpp",
    time_col: Optional[str] = "tu_first_loc_timestamp",
    phase: Optional[str] = "all",
    shift: Optional[str] = "all",
    limit: int = 1000
):
    """
    获取指定规格在单日内全部单胎（Barcode）实际测量值的时序数据（Run Chart / I-Chart），按生产时序排列
    """
    try:
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"
            
        phase_cond = get_phase_sql_condition(phase)
        date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"
        shift_cond = f" AND {build_production_time_where(time_col=time_col, shift=shift)}" if (shift and shift != 'all') else ""
        
        if not target_date:
            res = qry(f"SELECT MAX({date_col}) AS max_d FROM clean_yield WHERE article10 = ?", [article10])
            if res and res[0]['max_d']:
                target_date = str(res[0]['max_d'])
            else:
                target_date = "2026-08-10"

        if indicator == "weight":
            sql = f"""
                SELECT 
                    barcode,
                    TRY_CAST(tire_weight_actual_first AS DOUBLE) AS actual_val,
                    TRY_CAST(tire_weight_target_first AS DOUBLE) AS target_val,
                    ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) AS val,
                    COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) AS prod_time,
                    gt_workcenter,
                    tu_first_workcenter,
                    "group"
                FROM clean_yield
                WHERE {date_col} = ?::DATE
                  AND article10 = ?
                  AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                  AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                  {phase_cond}
                ORDER BY prod_time ASC, barcode ASC
            """
            rows = qry(sql, [target_date, article10])
            if not rows:
                return {
                    "status": "success",
                    "summary": {
                        "article10": article10,
                        "target_date": target_date,
                        "indicator": indicator,
                        "indicator_label": "胎重 (实际值 / 偏差率)",
                        "unit": "kg",
                        "total_tires": 0,
                        "mean_val": 0,
                        "std_val": 0,
                        "usl": None,
                        "lsl": None,
                        "out_of_spec_count": 0,
                        "out_of_spec_rate": "0.00%",
                        "cpk": None
                    },
                    "data": []
                }
            
            vals = [float(r['actual_val']) for r in rows if r.get('actual_val') is not None]
            diff_vals = [float(r['val']) for r in rows if r.get('val') is not None]
            target_val = float(rows[0]['target_val']) if rows[0].get('target_val') else None
            
            mean_act = float(np.mean(vals)) if vals else 0.0
            std_act = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            mean_diff = float(np.mean(diff_vals)) if diff_vals else 0.0
            std_diff = float(np.std(diff_vals, ddof=1)) if len(diff_vals) > 1 else 0.0
            
            usl_tol = 0.8
            lsl_tol = -0.8
            out_count = sum(1 for d in diff_vals if d > usl_tol or d < lsl_tol)
            out_rate = round(out_count / len(diff_vals) * 100, 2) if diff_vals else 0.0
            
            data_list = []
            for r in rows:
                v = float(r['actual_val'])
                d = float(r['val']) if r.get('val') is not None else 0.0
                is_out = bool(d > usl_tol or d < lsl_tol)
                t_str = str(r['prod_time']) if r.get('prod_time') else ""
                data_list.append({
                    "barcode": str(r['barcode']),
                    "value": round(v, 3),
                    "diff_pct": round(d, 2),
                    "target_val": round(float(r['target_val']), 3) if r.get('target_val') else None,
                    "is_out_of_spec": is_out,
                    "prod_time": t_str,
                    "gt_workcenter": r.get('gt_workcenter') or "未知",
                    "tu_workcenter": r.get('tu_first_workcenter') or "未知"
                })
                
            return {
                "status": "success",
                "summary": {
                    "article10": article10,
                    "target_date": target_date,
                    "indicator": indicator,
                    "indicator_label": "胎重 (实际值 / 偏差率)",
                    "unit": "kg",
                    "total_tires": len(data_list),
                    "mean_val": round(mean_act, 3),
                    "std_val": round(std_act, 3),
                    "target_val": round(target_val, 3) if target_val else None,
                    "mean_diff_pct": round(mean_diff, 2),
                    "std_diff_pct": round(std_diff, 2),
                    "usl": round(target_val * (1 + usl_tol/100.0), 3) if target_val else None,
                    "lsl": round(target_val * (1 + lsl_tol/100.0), 3) if target_val else None,
                    "max_val": round(float(np.max(vals)), 3) if vals else 0.0,
                    "min_val": round(float(np.min(vals)), 3) if vals else 0.0,
                    "out_of_spec_count": out_count,
                    "out_of_spec_rate": f"{out_rate}%",
                    "cpk": None
                },
                "data": sanitize_data(data_list)
            }

        # RFPP / RFH1 / CONY 指标
        ind_col = "cony_first" if indicator == "cony" else ("rfppwc_first" if indicator == "rfpp" else "rfh1wc_first")
        ind_label = "CONY 锥度" if indicator == "cony" else ("RFPP 径向力峰峰值" if indicator == "rfpp" else "RFH1 径向力一次谐波")
        unit = "N"

        sql = f"""
            SELECT 
                barcode,
                TRY_CAST({ind_col} AS DOUBLE) AS val,
                COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) AS prod_time,
                gt_workcenter,
                tu_first_workcenter,
                "group",
                standard_rfpp,
                standard_rfh1,
                COALESCE(TRY_CAST(standard_rfpp AS DOUBLE), 
                         CASE "group" 
                             WHEN 'GROUP 1'  THEN 10.5 
                             WHEN 'GROUP 2A' THEN 11.5 
                             WHEN 'GROUP 2B' THEN 12.5 
                             WHEN 'GROUP 3'  THEN 12.5 
                         END) * 10.0 AS usl_rfpp,
                COALESCE(TRY_CAST(standard_rfh1 AS DOUBLE), 
                         CASE "group" 
                             WHEN 'GROUP 1'  THEN 7.5 
                             WHEN 'GROUP 2A' THEN 8.5 
                             WHEN 'GROUP 2B' THEN 9.0 
                             WHEN 'GROUP 3'  THEN 9.5 
                         END) * 10.0 AS usl_rfh1
            FROM clean_yield
            WHERE {date_col} = ?::DATE
              AND article10 = ?
              AND {ind_col} IS NOT NULL
              {phase_cond}
            ORDER BY prod_time ASC, barcode ASC
        """
        rows = qry(sql, [target_date, article10])
        if not rows:
            return {
                "status": "success",
                "summary": {
                    "article10": article10,
                    "target_date": target_date,
                    "indicator": indicator,
                    "indicator_label": ind_label,
                    "unit": unit,
                    "total_tires": 0,
                    "mean_val": 0,
                    "std_val": 0,
                    "usl": None,
                    "lsl": None,
                    "out_of_spec_count": 0,
                    "out_of_spec_rate": "0.00%",
                    "cpk": None
                },
                "data": []
            }

        vals = [float(r['val']) for r in rows if r.get('val') is not None]
        mean_v = float(np.mean(vals)) if vals else 0.0
        std_v = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        
        if indicator == "cony":
            usl_v, lsl_v = get_spec_limits(article10, "cony")
            cpk_v = calc_cpk(mean_v, std_v, usl_v, lsl_v)
            out_count = sum(1 for v in vals if (usl_v is not None and v > usl_v) or (lsl_v is not None and v < lsl_v))
        else:
            usl_v = float(rows[0]['usl_rfpp']) if indicator == "rfpp" and rows[0].get('usl_rfpp') is not None else (
                    float(rows[0]['usl_rfh1']) if indicator == "rfh1" and rows[0].get('usl_rfh1') is not None else 105.0)
            lsl_v = None
            cpk_v = (usl_v - mean_v) / (3.0 * std_v) if std_v > 1e-6 else 1.33
            out_count = sum(1 for v in vals if v > usl_v)

        out_rate = round(out_count / len(vals) * 100, 2) if vals else 0.0
        
        data_list = []
        for r in rows:
            v = float(r['val'])
            is_out = bool((usl_v is not None and v > usl_v) or (lsl_v is not None and v < lsl_v))
            t_str = str(r['prod_time']) if r.get('prod_time') else ""
            data_list.append({
                "barcode": str(r['barcode']),
                "value": round(v, 2),
                "is_out_of_spec": is_out,
                "prod_time": t_str,
                "gt_workcenter": r.get('gt_workcenter') or "未知",
                "tu_workcenter": r.get('tu_first_workcenter') or "未知"
            })

        return {
            "status": "success",
            "summary": {
                "article10": article10,
                "target_date": target_date,
                "indicator": indicator,
                "indicator_label": ind_label,
                "unit": unit,
                "total_tires": len(data_list),
                "mean_val": round(mean_v, 2),
                "std_val": round(std_v, 2),
                "usl": round(usl_v, 2) if usl_v is not None else None,
                "lsl": round(lsl_v, 2) if lsl_v is not None else None,
                "max_val": round(float(np.max(vals)), 2) if vals else 0.0,
                "min_val": round(float(np.min(vals)), 2) if vals else 0.0,
                "out_of_spec_count": out_count,
                "out_of_spec_rate": f"{out_rate}%",
                "cpk": round(float(cpk_v), 3) if cpk_v is not None and not (np.isnan(cpk_v) or np.isinf(cpk_v)) else None
            },
            "data": sanitize_data(data_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



def get_lot_cpk_trend(
    article10: str,
    target_date: Optional[str] = None,
    indicator: str = "rfpp",
    component: Optional[str] = None,
    time_col: Optional[str] = "gt_loc_timestamp",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_samples: int = 1
):
    try:
        if not isinstance(indicator, str):
            indicator = "rfpp"
        if not isinstance(article10, str):
            article10 = ""
        if not isinstance(target_date, str):
            target_date = None
        if not isinstance(start_date, str):
            start_date = None
        if not isinstance(end_date, str):
            end_date = None
        if not isinstance(component, str):
            component = None
        if not isinstance(time_col, str):
            time_col = "gt_loc_timestamp"
        try:
            min_samples = int(min_samples)
        except Exception:
            min_samples = 1
        if indicator == "weight":
            ind_col = "TRY_CAST(tire_weight_actual_first AS DOUBLE)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
        date_col = "tu_first_shift_date"

        # 1. 确定目标日期与日期范围
        if not target_date:
            max_dt_sql = f"SELECT MAX({date_col}::DATE) as max_d FROM clean_yield WHERE article10 = ? AND {ind_col} IS NOT NULL"
            res_dt = qry(max_dt_sql, [article10])
            if res_dt and res_dt[0]['max_d']:
                target_date = str(res_dt[0]['max_d'])
            else:
                target_date = "2026-07-07"

        if not end_date:
            end_date = target_date
        if not start_date:
            start_date = target_date

        # 2. 规格 USL/LSL 计算
        if indicator == "weight":
            sql_tw = "SELECT AVG(TRY_CAST(tire_weight_target_first AS DOUBLE)) as target_w FROM clean_yield WHERE article10 = ?"
            res_tw = qry(sql_tw, [article10])
            global_usl = float(res_tw[0]['target_w']) if (res_tw and res_tw[0]['target_w'] is not None) else 12.0
            global_lsl = None
        else:
            global_usl, global_lsl = get_spec_limits(article10, indicator)

        # 3. 动态识别 clean_yield 中所有的 `*_lot` 字段与时间戳字段
        cols_info = qry("DESCRIBE SELECT * FROM clean_yield")
        col_names = [r['column_name'] for r in cols_info]

        lot_cols = [c for c in col_names if c.endswith("_lot")]
        
        # 中文标签对照表
        label_map = {
            "tread": "胎面",
            "bead": "胎圈",
            "inner_liner": "内衬",
            "sidewall": "胎侧",
            "first_ply": "帘布层1",
            "first_breaker": "带束层1",
            "second_breaker": "带束层2",
            "wound_cap_ply1": "冠带层1",
            "wound_cap_ply2": "冠带层2",
            "gt": "生胎成型GT",
            "ct": "硫化CT",
            "tu_first": "终检TU",
            "tb_first": "动平衡TB"
        }

        # 判定选中的时间戳列是否存在 (如 gt_loc_timestamp, ct_loc_timestamp 等)，若未覆盖新 parquet 则降级为 tu_first_shift_date
        target_time_col = time_col or "gt_loc_timestamp"
        if target_time_col in col_names:
            time_expr = f"TRY_CAST({target_time_col} AS TIMESTAMP)"
        else:
            time_expr = f"{date_col}::DATE"

        # 如果传入了具体的工段 (component)，仅过滤该工段对应的 lot 字段
        if component and component != "全部工段":
            matched_cols = []
            for lc in lot_cols:
                bp = lc[:-4]
                cname = label_map.get(bp, bp.upper())
                if cname == component:
                    matched_cols.append(lc)
            if matched_cols:
                lot_cols = matched_cols

        lot_data_list = []

        for lot_col in lot_cols:
            base_prefix = lot_col[:-4] # e.g. "tread"
            wc_col = f"{base_prefix}_workcenter"
            if wc_col not in col_names:
                continue

            comp_name = label_map.get(base_prefix, base_prefix.upper())

            # 查询在 [start_date, end_date] 范围内，该 article10 使用的该工段所有 Lot 批次及其 Machine & 均值极值四分位统计值
            # 按照【机台升序, 指定时间戳 (first_date) 升序】排列，确保同一机台按加工时间先后（由早到晚）呈现
            spec_sql = f"""
                SELECT 
                    CAST({wc_col} AS VARCHAR) as machine,
                    CAST({lot_col} AS VARCHAR) as lot_code,
                    COUNT(*) as spec_n,
                    AVG(TRY_CAST({ind_col} AS DOUBLE)) as spec_mean,
                    STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as spec_std,
                    MIN(TRY_CAST({ind_col} AS DOUBLE)) as min_v,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY TRY_CAST({ind_col} AS DOUBLE)) as q1_v,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY TRY_CAST({ind_col} AS DOUBLE)) as q3_v,
                    MAX(TRY_CAST({ind_col} AS DOUBLE)) as max_v,
                    MIN({time_expr}) as first_date
                FROM clean_yield
                WHERE article10 = ?
                  AND {date_col}::DATE >= ?::DATE
                  AND {date_col}::DATE <= ?::DATE
                  AND {lot_col} IS NOT NULL AND CAST({lot_col} AS VARCHAR) != ''
                  AND {ind_col} IS NOT NULL
                GROUP BY 1, 2
                HAVING COUNT(*) >= ?
                ORDER BY machine ASC, first_date ASC, lot_code ASC
            """
            spec_rows = qry(spec_sql, [article10, start_date, end_date, min_samples])

            for r in spec_rows:
                m_code = str(r['machine']) if r['machine'] else "N/A"
                l_code = str(r['lot_code']) if r['lot_code'] else "N/A"

                # 检查是否需要插入切断占位点 (当工段或机台发生切换时)
                if lot_data_list and not lot_data_list[-1].get('is_break'):
                    last_item = lot_data_list[-1]
                    if last_item['component'] != comp_name or last_item['machine'] != m_code:
                        lot_data_list.append({
                            "component": last_item['component'],
                            "machine": last_item['machine'],
                            "lot": "",
                            "is_break": True,
                            "spec_n": 0,
                            "spec_cpk": None,
                            "multi_n": 0,
                            "multi_cpk": None,
                            "boxplot": None,
                            "mean_v": None,
                            "is_warning": False,
                            "building_machine": "N/A",
                            "gt_distribution": {}
                        })

                # 查询该批次在各个成型机台（gt_workcenter）中的消费占比
                dist_sql = f"""
                    SELECT 
                        CAST(gt_workcenter AS VARCHAR) as gt_mac,
                        COUNT(*) as cnt
                    FROM clean_yield
                    WHERE {lot_col} = ?
                      AND {date_col}::DATE >= ?::DATE
                      AND {date_col}::DATE <= ?::DATE
                      AND gt_workcenter IS NOT NULL
                    GROUP BY 1
                """
                dist_rows = qry(dist_sql, [l_code, start_date, end_date])
                total_cnt = sum(int(dr['cnt']) for dr in dist_rows)
                gt_dist = {}
                if total_cnt > 0:
                    for dr in dist_rows:
                        mac = str(dr['gt_mac'])
                        gt_dist[mac] = round(int(dr['cnt']) / total_cnt, 3)
                
                primary_gt = "N/A"
                if gt_dist:
                    primary_gt = max(gt_dist.keys(), key=lambda k: gt_dist[k])

                s_n = int(r['spec_n'])
                s_m = float(r['spec_mean']) if r['spec_mean'] is not None else 0.0
                s_s = float(r['spec_std']) if r['spec_std'] is not None else 0.0

                if indicator == "weight":
                    s_cpk = s_m
                else:
                    s_cpk = round(calc_cpk(s_m, s_s, global_usl, global_lsl), 2)

                min_v = round(float(r['min_v']), 2) if r['min_v'] is not None else 0.0
                mean_v = round(s_m, 2)
                q1_v = round(float(r['q1_v']), 2) if r['q1_v'] is not None else min_v
                q3_v = round(float(r['q3_v']), 2) if r['q3_v'] is not None else mean_v
                max_v = round(float(r['max_v']), 2) if r['max_v'] is not None else q3_v

                # 查询除当前选中单规格外的其它规格全加权 Lot CPK (排除 article10)
                multi_sql = f"""
                    SELECT 
                        COUNT(*) as multi_n,
                        AVG(TRY_CAST({ind_col} AS DOUBLE)) as multi_mean,
                        STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as multi_std
                    FROM clean_yield
                    WHERE {lot_col} = ?
                      AND {date_col}::DATE >= ?::DATE
                      AND {date_col}::DATE <= ?::DATE
                      AND {ind_col} IS NOT NULL
                """
                m_rows = qry(multi_sql, [l_code, start_date, end_date])
                if m_rows and m_rows[0]['multi_n']:
                    m_n = int(m_rows[0]['multi_n'])
                    m_m = float(m_rows[0]['multi_mean']) if m_rows[0]['multi_mean'] is not None else 0.0
                    m_s = float(m_rows[0]['multi_std']) if m_rows[0]['multi_std'] is not None else 0.0
                    if indicator == "weight":
                        m_cpk = m_m
                    else:
                        m_cpk = round(calc_cpk(m_m, m_s, global_usl, global_lsl), 2)
                else:
                    m_n = s_n
                    m_cpk = s_cpk

                # 判定预警条件
                if indicator == "weight":
                    is_warn = (abs(s_m - global_usl) / global_usl * 100.0) > 0.8
                else:
                    is_warn = (s_cpk < 1.33 and m_cpk < 1.33 and m_n > s_n)

                lot_data_list.append({
                    "component": comp_name,
                    "machine": m_code,
                    "lot": l_code,
                    "is_break": False,
                    "spec_n": s_n,
                    "spec_cpk": s_cpk,
                    "multi_n": m_n,
                    "multi_cpk": m_cpk,
                    "boxplot": [min_v, q1_v, mean_v, q3_v, max_v],
                    "mean_v": mean_v,
                    "is_warning": is_warn,
                    "building_machine": primary_gt,
                    "gt_distribution": gt_dist
                })

        return {
            "status": "success",
            "target_date": target_date,
            "start_date": start_date,
            "end_date": end_date,
            "article10": article10,
            "indicator": indicator,
            "time_col": target_time_col,
            "usl": round(global_usl, 2),
            "lsl": round(global_lsl, 2) if global_lsl is not None else None,
            "data": sanitize_data(lot_data_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ── 6.6. 选中物料批次 (Lot) 下属 Barcode 级测量实际值分布接口 ────────────────


def get_lot_barcode_detail(
    article10: str,
    lot: str,
    component: Optional[str] = None,
    indicator: str = "rfpp"
):
    try:
        if indicator == "weight":
            ind_col = "TRY_CAST(tire_weight_actual_first AS DOUBLE)"
        elif indicator == "cony":
            ind_col = "cony_first"
        else:
            ind_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"

        # 中文工段名称映射到数据库 _lot 字段前缀
        prefix_map = {
            "胎面": "tread",
            "胎圈": "bead",
            "内衬": "inner_liner",
            "胎侧": "sidewall",
            "帘布层1": "first_ply",
            "带束层1": "first_breaker",
            "带束层2": "second_breaker",
            "冠带层1": "wound_cap_ply1",
            "冠带层2": "wound_cap_ply2"
        }

        # 识别具体的 lot_col
        lot_col = None
        if component and component in prefix_map:
            lot_col = f"{prefix_map[component]}_lot"
        else:
            # 动态检查 clean_yield 包含的 *_lot 字段
            cols_info = qry("DESCRIBE SELECT * FROM clean_yield")
            col_names = [r['column_name'] for r in cols_info]
            lot_cols = [c for c in col_names if c.endswith("_lot")]
            
            # 找到匹配当前 lot 值的列
            for lc in lot_cols:
                check_sql = f"SELECT COUNT(*) as cnt FROM clean_yield WHERE article10 = ? AND {lc} = ?"
                c_res = qry(check_sql, [article10, lot])
                if c_res and c_res[0]['cnt'] > 0:
                    lot_col = lc
                    break

        if not lot_col:
            lot_col = "tread_lot"

        sql = f"""
            SELECT 
                CAST(barcode AS VARCHAR) as barcode,
                AVG(TRY_CAST({ind_col} AS DOUBLE)) as val,
                MAX(CAST(ct_workcenter AS VARCHAR)) as ct_workcenter,
                MAX(CAST(tu_first_workcenter AS VARCHAR)) as tu_first_workcenter,
                COUNT(*) as cnt
            FROM clean_yield
            WHERE article10 = ?
              AND {lot_col} = ?
              AND {ind_col} IS NOT NULL
              AND barcode IS NOT NULL AND CAST(barcode AS VARCHAR) != ''
            GROUP BY 1
            ORDER BY barcode ASC
        """
        rows = qry(sql, [article10, lot])

        barcode_list = []
        for r in rows:
            b_code = str(r['barcode']) if r['barcode'] else ""
            if not b_code: continue
            v = round(float(r['val']), 2) if r['val'] is not None else 0.0
            ct_wc = str(r['ct_workcenter']) if r['ct_workcenter'] else "N/A"
            tu_wc = str(r['tu_first_workcenter']) if r['tu_first_workcenter'] else "N/A"

            barcode_list.append({
                "barcode": b_code,
                "val": v,
                "ct_workcenter": ct_wc,
                "tu_workcenter": tu_wc,
                "count": int(r['cnt'])
            })

        return {
            "status": "success",
            "article10": article10,
            "lot": lot,
            "component": component,
            "indicator": indicator,
            "data": sanitize_data(barcode_list)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}



# ── 11. 过滤选项：规格列表 ────────────────────────────────────




# 业务纯函数命名映射与别名兼容
get_article_phase_endpoint = get_article_phase
get_articles_warning_cpk = get_warning_cpk
get_article_barcode_measurements = get_barcode_measurements
get_article_lot_cpk_trend = get_lot_cpk_trend
