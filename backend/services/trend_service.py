# -*- coding: utf-8 -*-
"""
趋势分析与全局筛选服务模块 (Trend & Filter Service)
提供全局规格列表、日期范围、宏观 CPK 趋势计算服务
"""
from typing import Optional, List
import numpy as np
import traceback

from backend.core.db import qry
from backend.core.cpk import INDICATORS_SPEC
from backend.core.time_utils import build_production_time_where, get_phase_sql_condition


def get_filter_articles(min_yield: int = 0) -> dict:
    """获取全量规格列表及各规格产量统计"""
    try:
        having_clause = "HAVING COUNT(*) > ?" if min_yield else ""
        sql = f"""
            SELECT article10, COUNT(*) AS cnt
            FROM clean_yield
            GROUP BY article10
            {having_clause}
            ORDER BY cnt DESC
            LIMIT 100
        """
        params = [min_yield] if min_yield else None
        return {"status": "success", "data": qry(sql, params)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_filter_daterange() -> dict:
    """获取当前数据的最小与最大生产日期范围"""
    try:
        sql = """
            SELECT
                MIN(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)) AS date_min,
                MAX(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)) AS date_max
            FROM clean_yield
            WHERE tu_first_loc_timestamp IS NOT NULL
        """
        rows = qry(sql)
        if not rows:
            return {"status": "error", "message": "无可用生产日期记录"}
        row = rows[0]
        row["date_min"] = str(row["date_min"])
        row["date_max"] = str(row["date_max"])
        return {"status": "success", "data": row}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 别名兼容原命名
get_date_range = get_filter_daterange


def get_trend_cpk(
    grain: str = "daily",     # "daily" | "hourly" | "minute" | "weekly"
    indicator: str = "rfpp",
    article10: Optional[str] = None,
    exclude_articles: Optional[str] = None, # 英文逗号分割的需剔除规格代码列表
    time_col: Optional[str] = "tu_first_loc_timestamp",
    phase: Optional[str] = "all",
    shift: Optional[str] = "all",
    exclude_outliers: bool = False
) -> dict:
    """获取宏观 CPK 趋势统计数据 (支持 17 项指标全量计算、多时间粒度、全厂加权与单规格池化、三班与期别过滤)"""
    try:
        if not isinstance(indicator, str) or not indicator:
            indicator = "rfpp"
        indicator = indicator.lower().strip()
        if not isinstance(exclude_articles, str):
            exclude_articles = None
        if not isinstance(article10, str):
            article10 = None
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"

        # 获取当前指标元数据
        spec = INDICATORS_SPEC.get(indicator, INDICATORS_SPEC["rfpp"])
        col_name = spec["col"]
        usl_col = spec.get("usl_col")
        lsl_col = spec.get("lsl_col")
        scale = spec.get("scale", 1.0)
        is_double = spec.get("is_double", False)
        ind_label = spec.get("label", indicator.upper())
        unit = spec.get("unit", "")

        # Select time expression
        col_ref = time_col if time_col else "tu_first_loc_timestamp"
        date_cast = f"STRFTIME(CAST((TRY_CAST({col_ref} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')"
        if grain == "daily":
            time_expr = date_cast
        elif grain == "hourly":
            time_expr = f"STRFTIME(DATE_TRUNC('hour', TRY_CAST({col_ref} AS TIMESTAMP)), '%Y-%m-%d %H:00')"
        elif grain == "minute":
            time_expr = f"STRFTIME(DATE_TRUNC('minute', TRY_CAST({col_ref} AS TIMESTAMP)), '%Y-%m-%d %H:%M')"
        elif grain == "weekly":
            time_expr = f"DATE_TRUNC('week', CAST(TRY_CAST({col_ref} AS TIMESTAMP) AS DATE))"
        else:
            time_expr = date_cast

        exclude_clause = ""
        exclude_params = []
        if exclude_articles:
            ex_list = [x.strip() for x in exclude_articles.split(",") if x.strip()]
            if ex_list:
                placeholders = ",".join(["?"] * len(ex_list))
                exclude_clause = f" AND article10 NOT IN ({placeholders})"
                exclude_params = ex_list

        time_null_clause = f"AND {build_production_time_where(col_ref, shift=shift)}"
        phase_cond = get_phase_sql_condition(phase)

        if indicator == "weight":
            # 胎重指标维持均值偏差率计算逻辑
            cond_weight = "AND b.v_weight <= q.up_weight" if exclude_outliers else ""
            if article10:
                sql = f"""
                    WITH base_filtered AS (
                        SELECT
                            {time_expr} AS time_period,
                            article10,
                            CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                            TRY_CAST(tire_weight_actual_first AS DOUBLE) as act_w,
                            TRY_CAST(tire_weight_target_first AS DOUBLE) as tar_w
                        FROM clean_yield
                        WHERE article10 = ?
                          {time_null_clause}
                          {phase_cond}
                    ),
                    q_bounds AS (
                        SELECT
                            time_period,
                            (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                        FROM base_filtered
                        GROUP BY 1
                    ),
                    spec_daily_stats AS (
                        SELECT
                            b.time_period,
                            b.article10,
                            COUNT(CASE WHEN 1=1 {cond_weight} THEN 1 END) AS sample_size,
                            SUM(CASE WHEN 1=1 {cond_weight} THEN b.act_w ELSE NULL END) as sum_act_w,
                            SUM(CASE WHEN 1=1 {cond_weight} THEN b.tar_w ELSE NULL END) as sum_tar_w,
                            STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                            SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight
                        FROM base_filtered b
                        JOIN q_bounds q ON b.time_period = q.time_period
                        GROUP BY 1, 2
                        HAVING COUNT(*) >= 5
                    )
                    SELECT
                        time_period,
                        sample_size AS total_n,
                        (sum_act_w - sum_tar_w) / NULLIF(sum_tar_w, 0.0) * 100.0 as weighted_cpk,
                        (sum_act_w - sum_tar_w) / NULLIF(sum_tar_w, 0.0) * 100.0 as weighted_avg,
                        std_w AS weighted_std,
                        outliers_weight AS total_outliers
                    FROM spec_daily_stats
                    ORDER BY 1
                """
                params = [article10]
            else:
                sql = f"""
                    WITH base_filtered AS (
                        SELECT
                            {time_expr} AS time_period,
                            article10,
                            CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                            TRY_CAST(tire_weight_actual_first AS DOUBLE) as act_w,
                            TRY_CAST(tire_weight_target_first AS DOUBLE) as tar_w
                        FROM clean_yield
                        WHERE article10 IS NOT NULL AND article10 != ''
                          {time_null_clause}
                          {phase_cond}
                          {exclude_clause}
                    ),
                    q_bounds AS (
                        SELECT
                            time_period,
                            (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                        FROM base_filtered
                        GROUP BY 1
                    ),
                    spec_daily_stats AS (
                        SELECT
                            b.time_period,
                            b.article10,
                            COUNT(CASE WHEN 1=1 {cond_weight} THEN 1 END) AS sample_size,
                            SUM(CASE WHEN 1=1 {cond_weight} THEN b.act_w ELSE NULL END) as sum_act_w,
                            SUM(CASE WHEN 1=1 {cond_weight} THEN b.tar_w ELSE NULL END) as sum_tar_w,
                            STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                            SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight
                        FROM base_filtered b
                        JOIN q_bounds q ON b.time_period = q.time_period
                        GROUP BY 1, 2
                        HAVING COUNT(*) >= 5
                    )
                    SELECT
                        time_period,
                        SUM(sample_size) AS total_n,
                        (SUM(sum_act_w) - SUM(sum_tar_w)) / NULLIF(SUM(sum_tar_w), 0.0) * 100.0 as weighted_cpk,
                        (SUM(sum_act_w) - SUM(sum_tar_w)) / NULLIF(SUM(sum_tar_w), 0.0) * 100.0 as weighted_avg,
                        SQRT(SUM(POWER(COALESCE(std_w, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_w IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std,
                        SUM(outliers_weight) AS total_outliers
                    FROM spec_daily_stats
                    GROUP BY 1
                    ORDER BY 1
                """
                params = exclude_params
        else:
            # 17 项工序指标通用加权 CPK 计算
            v_expr = f"TRY_CAST({col_name} AS DOUBLE)"
            usl_expr = f"TRY_CAST({usl_col} AS DOUBLE) * {scale}" if usl_col else "NULL::DOUBLE"
            lsl_expr = f"TRY_CAST({lsl_col} AS DOUBLE) * {scale}" if (is_double and lsl_col) else "NULL::DOUBLE"
            cond_outliers = "AND b.v_measure <= q.up_measure" if exclude_outliers else ""

            if article10:
                sql = f"""
                    WITH base_filtered AS (
                        SELECT
                            {time_expr} AS time_period,
                            article10,
                            {v_expr} AS v_measure,
                            {usl_expr} AS usl_val,
                            {lsl_expr} AS lsl_val
                        FROM clean_yield
                        WHERE article10 = ?
                          AND {col_name} IS NOT NULL
                          {time_null_clause}
                          {phase_cond}
                    ),
                    q_bounds AS (
                        SELECT
                            time_period,
                            (2.5 * QUANTILE_CONT(v_measure, 0.75) - 1.5 * QUANTILE_CONT(v_measure, 0.25)) AS up_measure
                        FROM base_filtered
                        GROUP BY 1
                    ),
                    spec_daily_stats AS (
                        SELECT
                            b.time_period,
                            b.article10,
                            COUNT(CASE WHEN 1=1 {cond_outliers} THEN 1 END) AS sample_size,
                            AVG(CASE WHEN 1=1 {cond_outliers} THEN b.v_measure END) AS avg_v,
                            STDDEV(CASE WHEN 1=1 {cond_outliers} THEN b.v_measure END) AS std_v,
                            SUM(CASE WHEN b.v_measure > q.up_measure THEN 1 ELSE 0 END) AS outliers_count,
                            ANY_VALUE(b.usl_val) AS usl_val,
                            ANY_VALUE(b.lsl_val) AS lsl_val
                        FROM base_filtered b
                        JOIN q_bounds q ON b.time_period = q.time_period
                        GROUP BY 1, 2
                        HAVING COUNT(*) >= 5
                    )
                    SELECT
                        time_period,
                        sample_size AS total_n,
                        CASE 
                            WHEN std_v <= 1e-6 THEN 1.33
                            WHEN usl_val IS NULL AND lsl_val IS NULL THEN NULL
                            WHEN lsl_val IS NULL THEN (usl_val - avg_v) / (3.0 * std_v)
                            ELSE LEAST((usl_val - avg_v) / (3.0 * std_v), (avg_v - lsl_val) / (3.0 * std_v))
                        END AS weighted_cpk,
                        avg_v AS weighted_avg,
                        std_v AS weighted_std,
                        outliers_count AS total_outliers
                    FROM spec_daily_stats
                    ORDER BY 1
                """
                params = [article10]
            else:
                sql = f"""
                    WITH base_filtered AS (
                        SELECT
                            {time_expr} AS time_period,
                            article10,
                            {v_expr} AS v_measure,
                            {usl_expr} AS usl_val,
                            {lsl_expr} AS lsl_val
                        FROM clean_yield
                        WHERE article10 IS NOT NULL AND article10 != ''
                          AND {col_name} IS NOT NULL
                          {time_null_clause}
                          {phase_cond}
                          {exclude_clause}
                    ),
                    q_bounds AS (
                        SELECT
                            time_period,
                            (2.5 * QUANTILE_CONT(v_measure, 0.75) - 1.5 * QUANTILE_CONT(v_measure, 0.25)) AS up_measure
                        FROM base_filtered
                        GROUP BY 1
                    ),
                    spec_daily_stats AS (
                        SELECT
                            b.time_period,
                            b.article10,
                            COUNT(CASE WHEN 1=1 {cond_outliers} THEN 1 END) AS sample_size,
                            AVG(CASE WHEN 1=1 {cond_outliers} THEN b.v_measure END) AS avg_v,
                            STDDEV(CASE WHEN 1=1 {cond_outliers} THEN b.v_measure END) AS std_v,
                            SUM(CASE WHEN b.v_measure > q.up_measure THEN 1 ELSE 0 END) AS outliers_count,
                            ANY_VALUE(b.usl_val) AS usl_val,
                            ANY_VALUE(b.lsl_val) AS lsl_val
                        FROM base_filtered b
                        JOIN q_bounds q ON b.time_period = q.time_period
                        GROUP BY 1, 2
                        HAVING COUNT(*) >= 5
                    ),
                    spec_cpk AS (
                        SELECT
                            time_period,
                            sample_size,
                            avg_v,
                            std_v,
                            outliers_count,
                            CASE 
                                WHEN std_v <= 1e-6 THEN 1.33
                                WHEN usl_val IS NULL AND lsl_val IS NULL THEN NULL
                                WHEN lsl_val IS NULL THEN (usl_val - avg_v) / (3.0 * std_v)
                                ELSE LEAST((usl_val - avg_v) / (3.0 * std_v), (avg_v - lsl_val) / (3.0 * std_v))
                            END AS cpk_val
                        FROM spec_daily_stats
                    )
                    SELECT
                        time_period,
                        SUM(sample_size) AS total_n,
                        SUM(cpk_val * sample_size) / NULLIF(SUM(CASE WHEN cpk_val IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk,
                        SUM(avg_v * sample_size) / NULLIF(SUM(sample_size), 0) AS weighted_avg,
                        SQRT(SUM(POWER(COALESCE(std_v, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_v IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std,
                        SUM(outliers_count) AS total_outliers
                    FROM spec_cpk
                    GROUP BY 1
                    ORDER BY 1
                """
                params = exclude_params

        rows = qry(sql, params)

        periods = sorted(list(set(str(r['time_period']) for r in rows)))
        period_idx = {p: i for i, p in enumerate(periods)}

        # 趋势输出字典
        trend_key = f"{ind_label} 综合 CPK"
        cpk_trends = {
            trend_key: [None] * len(periods),
            "current_cpk": [None] * len(periods)
        }

        # 历史别名兼容
        if indicator == "cony":
            cpk_trends["CONY 综合 实际值"] = [None] * len(periods)
            cpk_trends["CONY 综合 CPK"] = [None] * len(periods)
        elif indicator == "weight":
            cpk_trends["胎重 综合 偏差"] = [None] * len(periods)
        elif indicator == "rfpp":
            cpk_trends["RFPP 综合 CPK"] = [None] * len(periods)
        elif indicator == "rfh1":
            cpk_trends["RFH1 综合 CPK"] = [None] * len(periods)

        stats_by_date = {}

        for r in rows:
            p_str = str(r['time_period'])
            idx = period_idx[p_str]

            total_n = int(r['total_n']) if r.get('total_n') is not None else 0
            cpk_raw = r.get('weighted_cpk')
            cpk_v = round(float(cpk_raw), 4) if cpk_raw is not None and not (np.isnan(cpk_raw) or np.isinf(cpk_raw)) else None
            avg_raw = r.get('weighted_avg')
            avg_v = round(float(avg_raw), 3) if avg_raw is not None and not (np.isnan(avg_raw) or np.isinf(avg_raw)) else None
            std_raw = r.get('weighted_std')
            std_v = round(float(std_raw), 3) if std_raw is not None and not (np.isnan(std_raw) or np.isinf(std_raw)) else None
            outliers_v = int(r['total_outliers']) if r.get('total_outliers') is not None else None

            cpk_trends[trend_key][idx] = cpk_v
            cpk_trends["current_cpk"][idx] = cpk_v

            if indicator == "cony":
                cpk_trends["CONY 综合 实际值"][idx] = avg_v
                cpk_trends["CONY 综合 CPK"][idx] = cpk_v
            elif indicator == "weight":
                cpk_trends["胎重 综合 偏差"][idx] = avg_v
            elif indicator == "rfpp":
                cpk_trends["RFPP 综合 CPK"][idx] = cpk_v
            elif indicator == "rfh1":
                cpk_trends["RFH1 综合 CPK"][idx] = cpk_v

            stats_by_date[p_str] = {
                "total_n": total_n,
                "cpk": cpk_v,
                "mean": avg_v,
                "std": std_v,
                "outliers": outliers_v,
                "indicator": indicator,
                "label": ind_label,
                "unit": unit,
                # 兼容旧组件取 stats_by_date[d][indicator]
                indicator: {
                    "cpk": cpk_v,
                    "mean": avg_v,
                    "std": std_v,
                    "outliers": outliers_v
                }
            }

        return {
            "status": "success",
            "data": {
                "dates": periods,
                "cpk_trends": cpk_trends,
                "stats_by_date": stats_by_date
            }
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# 别名兼容原命名
get_cpk_trend = get_trend_cpk


def get_trend_production_anomaly(
    grain: str = "daily",
    article10: Optional[str] = None,
    time_col: Optional[str] = "tu_first_loc_timestamp",
    phase: Optional[str] = "all",
    shift: Optional[str] = "all"
) -> dict:
    """获取每日/每周生产总量、正常量、TU/TG/TB 异常量及异常率聚合统计"""
    try:
        if not isinstance(article10, str):
            article10 = None
        if not isinstance(time_col, str) or not time_col:
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"
        if not isinstance(shift, str):
            shift = "all"
        if not isinstance(grain, str):
            grain = "daily"

        col_ref = time_col
        date_cast = f"STRFTIME(CAST((TRY_CAST({col_ref} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')"
        if grain == "weekly":
            time_expr = f"STRFTIME(DATE_TRUNC('week', CAST(TRY_CAST({col_ref} AS TIMESTAMP) AS DATE)), '%Y-%m-%d')"
        else:
            time_expr = date_cast


        where_conds = [
            f"{col_ref} IS NOT NULL",
            build_production_time_where(col_ref, shift=shift)
        ]
        params = []

        phase_cond = get_phase_sql_condition(phase).strip()
        if phase_cond:
            if phase_cond.startswith("AND "):
                phase_cond = phase_cond[4:].strip()
            where_conds.append(phase_cond)


        if article10:
            where_conds.append("article10 = ?")
            params.append(article10)

        where_str = " AND ".join(where_conds)

        # 检查 clean_yield 是否包含 is_anomaly_overall
        desc_rows = qry("DESCRIBE clean_yield")
        cols = [r.get('column_name') or r.get('Field') or list(r.values())[0] for r in desc_rows]
        has_anomaly_cols = 'is_anomaly_overall' in cols

        # 17 项指标配置定义 (TU 7项, TG 7项, TB 3项)
        indicators_by_process = {
            "TU": [
                {"key": "rfpp", "label": "RFPP", "col": "grade_rfppwc_first"},
                {"key": "rfh1", "label": "RFH1", "col": "grade_rfh1wc_first"},
                {"key": "rfh2", "label": "RFH2", "col": "grade_rfh2wc_first"},
                {"key": "lfpp", "label": "LFPP", "col": "grade_lfppwc_first"},
                {"key": "lfh1", "label": "LFH1", "col": "grade_lfh1wc_first"},
                {"key": "cony", "label": "CONY", "col": "grade_cony_first"},
                {"key": "plys", "label": "PLYS", "col": "grade_plys_first"},
            ],
            "TG": [
                {"key": "tbul", "label": "TBUL", "col": "grade_tbul_first"},
                {"key": "bbul", "label": "BBUL", "col": "grade_bbul_first"},
                {"key": "tdep", "label": "TDEP", "col": "grade_tdep_first"},
                {"key": "bdep", "label": "BDEP", "col": "grade_bdep_first"},
                {"key": "tlro", "label": "TLRO", "col": "grade_tlro_first"},
                {"key": "blro", "label": "BLRO", "col": "grade_blro_first"},
                {"key": "crro", "label": "CRRO", "col": "grade_crro_first"},
            ],
            "TB": [
                {"key": "tbalw", "label": "TBALW", "col": "grade_tbalw_first"},
                {"key": "bbalw", "label": "BBALW", "col": "grade_bbalw_first"},
                {"key": "sbalw", "label": "SBALW", "col": "grade_sbalw_first"},
            ]
        }

        detail_selects = []
        for proc, items in indicators_by_process.items():
            for it in items:
                k = it["key"]
                c = it["col"]
                if c in cols:
                    detail_selects.append(f"COALESCE(SUM(CASE WHEN {c} != 'A' AND {c} IS NOT NULL AND {c} != '' THEN 1 ELSE 0 END), 0) AS {k}_anomalies")
                else:
                    detail_selects.append(f"0 AS {k}_anomalies")
        detail_selects_str = ",\n                    " + ",\n                    ".join(detail_selects)

        if has_anomaly_cols:
            sql = f"""
                SELECT 
                    {time_expr} AS date_str,
                    COUNT(*) AS total_tires,
                    COALESCE(SUM(is_anomaly_overall), 0) AS anomaly_tires,
                    COALESCE(SUM(CASE WHEN is_anomaly_overall = 0 THEN 1 ELSE 0 END), 0) AS normal_tires,
                    COALESCE(SUM(is_anomaly_tu), 0) AS tu_anomalies,
                    COALESCE(SUM(is_anomaly_tg), 0) AS tg_anomalies,
                    COALESCE(SUM(is_anomaly_tb), 0) AS tb_anomalies,
                    COALESCE(SUM(CASE WHEN is_anomaly_tu = 1 AND is_anomaly_tg = 0 AND is_anomaly_tb = 0 THEN 1 ELSE 0 END), 0) AS tu_only_anomalies,
                    COALESCE(SUM(CASE WHEN is_anomaly_tu = 0 AND is_anomaly_tg = 1 AND is_anomaly_tb = 0 THEN 1 ELSE 0 END), 0) AS tg_only_anomalies,
                    COALESCE(SUM(CASE WHEN is_anomaly_tu = 0 AND is_anomaly_tg = 0 AND is_anomaly_tb = 1 THEN 1 ELSE 0 END), 0) AS tb_only_anomalies,
                    COALESCE(SUM(CASE WHEN (is_anomaly_tu + is_anomaly_tg + is_anomaly_tb) > 1 THEN 1 ELSE 0 END), 0) AS multi_anomalies,
                    ROUND(COALESCE(SUM(is_anomaly_overall), 0) * 100.0 / NULLIF(COUNT(*), 0), 2) AS anomaly_rate,
                    ROUND(COALESCE(SUM(is_anomaly_tu), 0) * 100.0 / NULLIF(COUNT(*), 0), 2) AS tu_anomaly_rate,
                    ROUND(COALESCE(SUM(is_anomaly_tg), 0) * 100.0 / NULLIF(COUNT(*), 0), 2) AS tg_anomaly_rate,
                    ROUND(COALESCE(SUM(is_anomaly_tb), 0) * 100.0 / NULLIF(COUNT(*), 0), 2) AS tb_anomaly_rate{detail_selects_str}
                FROM clean_yield
                WHERE {where_str}
                GROUP BY 1
                ORDER BY 1 ASC
            """
        else:
            sql = f"""
                SELECT 
                    {time_expr} AS date_str,
                    COUNT(*) AS total_tires,
                    0 AS anomaly_tires,
                    COUNT(*) AS normal_tires,
                    0 AS tu_anomalies,
                    0 AS tg_anomalies,
                    0 AS tb_anomalies,
                    0 AS tu_only_anomalies,
                    0 AS tg_only_anomalies,
                    0 AS tb_only_anomalies,
                    0 AS multi_anomalies,
                    0.0 AS anomaly_rate,
                    0.0 AS tu_anomaly_rate,
                    0.0 AS tg_anomaly_rate,
                    0.0 AS tb_anomaly_rate{detail_selects_str}
                FROM clean_yield
                WHERE {where_str}
                GROUP BY 1
                ORDER BY 1 ASC
            """

        rows = qry(sql, params if params else None)
        
        # 格式化日期与数值
        res_data = []
        for r in rows:
            if not r.get('date_str'):
                continue
            
            raw_counts = {}
            for proc, items in indicators_by_process.items():
                for it in items:
                    k = it["key"]
                    raw_counts[k] = int(r.get(f"{k}_anomalies") or 0)

            res_data.append({
                "date": str(r['date_str']),
                "total_tires": int(r['total_tires'] or 0),
                "normal_tires": int(r['normal_tires'] or 0),
                "anomaly_tires": int(r['anomaly_tires'] or 0),
                "tu_anomalies": int(r['tu_anomalies'] or 0),
                "tg_anomalies": int(r['tg_anomalies'] or 0),
                "tb_anomalies": int(r['tb_anomalies'] or 0),
                "tu_only_anomalies": int(r.get('tu_only_anomalies') or 0),
                "tg_only_anomalies": int(r.get('tg_only_anomalies') or 0),
                "tb_only_anomalies": int(r.get('tb_only_anomalies') or 0),
                "multi_anomalies": int(r.get('multi_anomalies') or 0),
                "anomaly_rate": float(r['anomaly_rate'] or 0.0),
                "tu_anomaly_rate": float(r['tu_anomaly_rate'] or 0.0),
                "tg_anomaly_rate": float(r['tg_anomaly_rate'] or 0.0),
                "tb_anomaly_rate": float(r['tb_anomaly_rate'] or 0.0),
                "indicator_counts": raw_counts
            })

        # 计算相较于前一天的综合及工序异常率增长比例 (%) 与绝对变动点，以及 17 项详细指标日环比增幅
        for idx, item in enumerate(res_data):
            tot = max(item["total_tires"], 1)
            # 计算当日各指标异常率 (%)
            curr_ind_rates = {k: (item["indicator_counts"][k] * 100.0 / tot) for k in item["indicator_counts"]}
            item["indicator_rates"] = curr_ind_rates

            if idx == 0:
                item["anomaly_growth_rate"] = None
                item["anomaly_rate_diff"] = 0.0
                item["tu_growth_rate"] = None
                item["tg_growth_rate"] = None
                item["tb_growth_rate"] = None
                prev_ind_rates = None
            else:
                prev_item = res_data[idx - 1]
                prev_ind_rates = prev_item["indicator_rates"]

                # 综合异常率日环比
                prev_rate = prev_item["anomaly_rate"]
                curr_rate = item["anomaly_rate"]
                item["anomaly_rate_diff"] = round(curr_rate - prev_rate, 2)
                if prev_rate > 1e-6:
                    item["anomaly_growth_rate"] = round((curr_rate - prev_rate) / prev_rate * 100.0, 2)
                else:
                    item["anomaly_growth_rate"] = 0.0 if curr_rate == 0 else 100.0

                # TU 均匀性异常率日环比
                prev_tu = prev_item["tu_anomaly_rate"]
                curr_tu = item["tu_anomaly_rate"]
                if prev_tu > 1e-6:
                    item["tu_growth_rate"] = round((curr_tu - prev_tu) / prev_tu * 100.0, 2)
                else:
                    item["tu_growth_rate"] = 0.0 if curr_tu == 0 else 100.0

                # TG 几何尺寸异常率日环比
                prev_tg = prev_item["tg_anomaly_rate"]
                curr_tg = item["tg_anomaly_rate"]
                if prev_tg > 1e-6:
                    item["tg_growth_rate"] = round((curr_tg - prev_tg) / prev_tg * 100.0, 2)
                else:
                    item["tg_growth_rate"] = 0.0 if curr_tg == 0 else 100.0

                # TB 动平衡异常率日环比
                prev_tb = prev_item["tb_anomaly_rate"]
                curr_tb = item["tb_anomaly_rate"]
                if prev_tb > 1e-6:
                    item["tb_growth_rate"] = round((curr_tb - prev_tb) / prev_tb * 100.0, 2)
                else:
                    item["tb_growth_rate"] = 0.0 if curr_tb == 0 else 100.0

            prev_item = res_data[idx - 1] if idx > 0 else None
            next_item = res_data[idx + 1] if idx + 1 < len(res_data) else None

            # 统计各工序下详细指标日环比增幅，并按增幅降序排序
            detail_indicators = {}
            for proc, items in indicators_by_process.items():
                proc_ind_list = []
                for it in items:
                    k = it["key"]
                    c_rate = curr_ind_rates[k]
                    cnt = item["indicator_counts"][k]

                    # 前一日与后一日指标数据
                    prev_cnt = prev_item["indicator_counts"][k] if prev_item else None
                    prev_date = prev_item["date"] if prev_item else None
                    next_cnt = next_item["indicator_counts"][k] if next_item else None
                    next_date = next_item["date"] if next_item else None

                    if prev_ind_rates is None:
                        g_rate = None
                        d_diff = 0.0
                    else:
                        p_rate = prev_ind_rates.get(k, 0.0)
                        d_diff = round(c_rate - p_rate, 4)
                        if p_rate > 1e-6:
                            g_rate = round((c_rate - p_rate) / p_rate * 100.0, 2)
                        else:
                            g_rate = 0.0 if c_rate == 0 else 100.0
                    proc_ind_list.append({
                        "key": k,
                        "label": it["label"],
                        "count": cnt,
                        "rate": round(c_rate, 4),
                        "growth_rate": g_rate,
                        "diff": d_diff,
                        "date": item["date"],
                        "prev_count": prev_cnt,
                        "prev_date": prev_date,
                        "next_count": next_cnt,
                        "next_date": next_date
                    })
                # 按照增幅降序排序 (growth_rate 降序，其次当日异常率/数量降序)
                proc_ind_list.sort(key=lambda x: (
                    x["growth_rate"] if x["growth_rate"] is not None else -99999,
                    x["rate"],
                    x["count"]
                ), reverse=True)
                detail_indicators[proc] = proc_ind_list

            item["detail_indicators"] = detail_indicators

            # 计算当日日环比增幅排行第一的工序 (与悬浮卡片中工序排序严格 100% 一致)
            process_rank = [
                {"name": "TB", "growth": item["tb_growth_rate"], "rate": item["tb_anomaly_rate"]},
                {"name": "TU", "growth": item["tu_growth_rate"], "rate": item["tu_anomaly_rate"]},
                {"name": "TG", "growth": item["tg_growth_rate"], "rate": item["tg_anomaly_rate"]},
            ]
            process_rank.sort(key=lambda x: (
                x["growth"] if x["growth"] is not None else -99999,
                x["rate"]
            ), reverse=True)
            top_proc = process_rank[0]["name"]
            item["top_process"] = top_proc

            # 统计该第一工序下增幅最大的详细指标
            top_ind = detail_indicators[top_proc][0]["key"] if detail_indicators.get(top_proc) else None
            item["top_indicator"] = top_ind

        # 清理临时字段以精简数据传输体积
        for item in res_data:
            item.pop("indicator_counts", None)
            item.pop("indicator_rates", None)

        return {
            "status": "success",
            "data": res_data
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

