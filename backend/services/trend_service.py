# -*- coding: utf-8 -*-
"""
趋势分析与全局筛选服务模块 (Trend & Filter Service)
提供全局规格列表、日期范围、宏观 CPK 趋势计算服务
"""
from typing import Optional, List
import numpy as np
import traceback

from backend.core.db import qry
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
    article10: Optional[str] = None,
    exclude_articles: Optional[str] = None, # 英文逗号分割的需剔除规格代码列表
    time_col: Optional[str] = "tu_first_loc_timestamp",
    phase: Optional[str] = "all",
    shift: Optional[str] = "all",
    exclude_outliers: bool = False
) -> dict:
    """获取宏观 CPK 趋势统计数据 (支持多时间粒度、全厂加权与单规格池化、三班与期别过滤)"""
    try:
        if not isinstance(exclude_articles, str):
            exclude_articles = None
        if not isinstance(article10, str):
            article10 = None
        if not isinstance(time_col, str):
            time_col = "tu_first_loc_timestamp"
        if not isinstance(phase, str):
            phase = "all"

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

        cond_rfpp = "AND b.v_rfpp <= q.up_rfpp" if exclude_outliers else ""
        cond_rfh1 = "AND b.v_rfh1 <= q.up_rfh1" if exclude_outliers else ""
        cond_cony = "AND b.v_cony <= q.up_cony" if exclude_outliers else ""
        cond_weight = "AND b.v_weight <= q.up_weight" if exclude_outliers else ""

        if article10:
            # 单规格：池化计算，直接计算均值与标准差，不区分 group，不加权；使用 CTE 计算上四分位界线异常值条数
            sql = f"""
                WITH base_filtered AS (
                    SELECT
                        {time_expr} AS time_period,
                        article10,
                        TRY_CAST(rfppwc_first AS DOUBLE) AS v_rfpp,
                        TRY_CAST(rfh1wc_first AS DOUBLE) AS v_rfh1,
                        TRY_CAST(cony_first AS DOUBLE) AS v_cony,
                        CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                        tire_weight_actual_first,
                        tire_weight_target_first,
                        conny_usl,
                        conny_lsl,
                        standard_rfpp,
                        standard_rfh1,
                        "group"
                    FROM clean_yield
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      {time_null_clause}
                      {phase_cond}
                      AND article10 = ?
                ),
                q_bounds AS (
                    SELECT
                        time_period,
                        (2.5 * QUANTILE_CONT(v_rfpp, 0.75) - 1.5 * QUANTILE_CONT(v_rfpp, 0.25)) AS up_rfpp,
                        (2.5 * QUANTILE_CONT(v_rfh1, 0.75) - 1.5 * QUANTILE_CONT(v_rfh1, 0.25)) AS up_rfh1,
                        (2.5 * QUANTILE_CONT(v_cony, 0.75) - 1.5 * QUANTILE_CONT(v_cony, 0.25)) AS up_cony,
                        (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                    FROM base_filtered
                    GROUP BY 1
                ),
                spec_daily_stats AS (
                    SELECT
                        b.time_period,
                        b.article10,
                        COUNT(CASE WHEN 1=1 {cond_rfpp} THEN 1 END) AS sample_size,
                        AVG(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS avg_rfpp,
                        STDDEV(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS std_rfpp,
                        SUM(CASE WHEN b.v_rfpp > q.up_rfpp THEN 1 ELSE 0 END) AS outliers_rfpp,
                        AVG(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS avg_rfh1,
                        STDDEV(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS std_rfh1,
                        SUM(CASE WHEN b.v_rfh1 > q.up_rfh1 THEN 1 ELSE 0 END) AS outliers_rfh1,
                        AVG(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS avg_cony,
                        STDDEV(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS std_cony,
                        SUM(CASE WHEN b.v_cony > q.up_cony THEN 1 ELSE 0 END) AS outliers_cony,
                        COALESCE(ANY_VALUE(b.conny_usl), 95.0) AS usl_cony,
                        COALESCE(ANY_VALUE(b.conny_lsl), -95.0) AS lsl_cony,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
                        STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                        SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight,
                        COALESCE(ANY_VALUE(b.standard_rfpp), 
                                 CASE ANY_VALUE(b."group") 
                                     WHEN 'GROUP 1'  THEN 10.5 
                                     WHEN 'GROUP 2A' THEN 11.5 
                                     WHEN 'GROUP 2B' THEN 12.5 
                                     WHEN 'GROUP 3'  THEN 12.5 
                                 END) * 10.0 AS usl_rfpp,
                        COALESCE(ANY_VALUE(b.standard_rfh1), 
                                 CASE ANY_VALUE(b."group") 
                                     WHEN 'GROUP 1'  THEN 7.5 
                                     WHEN 'GROUP 2A' THEN 8.5 
                                     WHEN 'GROUP 2B' THEN 9.0 
                                     WHEN 'GROUP 3'  THEN 9.5 
                                 END) * 10.0 AS usl_rfh1
                    FROM base_filtered b
                    JOIN q_bounds q ON b.time_period = q.time_period
                    GROUP BY 1, 2
                    HAVING COUNT(*) >= 10
                )
                SELECT
                    time_period,
                    sample_size AS total_n,
                    CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS weighted_cpk_rfpp,
                    avg_rfpp AS weighted_avg_rfpp,
                    std_rfpp AS weighted_std_rfpp,
                    outliers_rfpp,
                    CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS weighted_cpk_rfh1,
                    avg_rfh1 AS weighted_avg_rfh1,
                    std_rfh1 AS weighted_std_rfh1,
                    outliers_rfh1,
                    CASE WHEN std_cony > 1e-6 THEN LEAST((usl_cony - avg_cony) / (3.0 * std_cony), (avg_cony - lsl_cony) / (3.0 * std_cony)) ELSE NULL END AS weighted_cpk_cony,
                    avg_cony AS weighted_avg_cony,
                    std_cony AS weighted_std_cony,
                    outliers_cony,
                    (sum_act_w - sum_tar_w) / NULLIF(sum_tar_w, 0.0) * 100.0 as weighted_diff_weight,
                    std_w AS weighted_std_weight,
                    outliers_weight
                FROM spec_daily_stats
                ORDER BY 1
            """
            params = [article10]
        else:
            # 全厂综合：各规格按生产组别计算独立 CPK，然后通过日产量加权平均；基于全厂样本计算当天的 IQR 异常值
            sql = f"""
                WITH base_filtered AS (
                    SELECT
                        {time_expr} AS time_period,
                        "group",
                        article10,
                        TRY_CAST(rfppwc_first AS DOUBLE) AS v_rfpp,
                        TRY_CAST(rfh1wc_first AS DOUBLE) AS v_rfh1,
                        TRY_CAST(cony_first AS DOUBLE) AS v_cony,
                        CASE WHEN tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0 AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0 THEN ((TRY_CAST(tire_weight_actual_first AS DOUBLE) - TRY_CAST(tire_weight_target_first AS DOUBLE)) / NULLIF(TRY_CAST(tire_weight_target_first AS DOUBLE), 0.0) * 100.0) ELSE NULL END AS v_weight,
                        tire_weight_actual_first,
                        tire_weight_target_first,
                        conny_usl,
                        conny_lsl,
                        standard_rfpp,
                        standard_rfh1
                    FROM clean_yield
                    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
                      {time_null_clause}
                      {phase_cond}
                      {exclude_clause}
                ),
                q_bounds AS (
                    SELECT
                        time_period,
                        (2.5 * QUANTILE_CONT(v_rfpp, 0.75) - 1.5 * QUANTILE_CONT(v_rfpp, 0.25)) AS up_rfpp,
                        (2.5 * QUANTILE_CONT(v_rfh1, 0.75) - 1.5 * QUANTILE_CONT(v_rfh1, 0.25)) AS up_rfh1,
                        (2.5 * QUANTILE_CONT(v_cony, 0.75) - 1.5 * QUANTILE_CONT(v_cony, 0.25)) AS up_cony,
                        (2.5 * QUANTILE_CONT(v_weight, 0.75) - 1.5 * QUANTILE_CONT(v_weight, 0.25)) AS up_weight
                    FROM base_filtered
                    GROUP BY 1
                ),
                spec_daily_stats AS (
                    SELECT
                        b.time_period,
                        b."group",
                        b.article10,
                        COUNT(CASE WHEN 1=1 {cond_rfpp} THEN 1 END) AS sample_size,
                        AVG(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS avg_rfpp,
                        STDDEV(CASE WHEN 1=1 {cond_rfpp} THEN b.v_rfpp END) AS std_rfpp,
                        SUM(CASE WHEN b.v_rfpp > q.up_rfpp THEN 1 ELSE 0 END) AS outliers_rfpp,
                        AVG(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS avg_rfh1,
                        STDDEV(CASE WHEN 1=1 {cond_rfh1} THEN b.v_rfh1 END) AS std_rfh1,
                        SUM(CASE WHEN b.v_rfh1 > q.up_rfh1 THEN 1 ELSE 0 END) AS outliers_rfh1,
                        AVG(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS avg_cony,
                        STDDEV(CASE WHEN 1=1 {cond_cony} THEN b.v_cony END) AS std_cony,
                        SUM(CASE WHEN b.v_cony > q.up_cony THEN 1 ELSE 0 END) AS outliers_cony,
                        COALESCE(ANY_VALUE(b.conny_usl), 95.0) AS usl_cony,
                        COALESCE(ANY_VALUE(b.conny_lsl), -95.0) AS lsl_cony,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_actual_first AS DOUBLE) ELSE NULL END) as sum_act_w,
                        SUM(CASE WHEN 1=1 {cond_weight} AND b.tire_weight_actual_first IS NOT NULL AND TRY_CAST(b.tire_weight_actual_first AS DOUBLE) > 0.0 AND b.tire_weight_target_first IS NOT NULL AND TRY_CAST(b.tire_weight_target_first AS DOUBLE) > 0.0 THEN TRY_CAST(b.tire_weight_target_first AS DOUBLE) ELSE NULL END) as sum_tar_w,
                        STDDEV(CASE WHEN 1=1 {cond_weight} THEN b.v_weight END) AS std_w,
                        SUM(CASE WHEN b.v_weight > q.up_weight THEN 1 ELSE 0 END) AS outliers_weight,
                        COALESCE(ANY_VALUE(b.standard_rfpp), 
                                 CASE b."group" 
                                     WHEN 'GROUP 1'  THEN 10.5 
                                     WHEN 'GROUP 2A' THEN 11.5 
                                     WHEN 'GROUP 2B' THEN 12.5 
                                     WHEN 'GROUP 3'  THEN 12.5 
                                 END) * 10.0 AS usl_rfpp,
                        COALESCE(ANY_VALUE(b.standard_rfh1), 
                                 CASE b."group" 
                                     WHEN 'GROUP 1'  THEN 7.5 
                                     WHEN 'GROUP 2A' THEN 8.5 
                                     WHEN 'GROUP 2B' THEN 9.0 
                                     WHEN 'GROUP 3'  THEN 9.5 
                                 END) * 10.0 AS usl_rfh1
                    FROM base_filtered b
                    JOIN q_bounds q ON b.time_period = q.time_period
                    GROUP BY 1, 2, 3
                    HAVING COUNT(*) >= 10
                ),
                spec_cpk AS (
                    SELECT
                        time_period,
                        sample_size,
                        CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp,
                        avg_rfpp,
                        std_rfpp,
                        outliers_rfpp,
                        CASE WHEN std_rfh1 > 1e-6 THEN (usl_rfh1 - avg_rfh1) / (3.0 * std_rfh1) ELSE NULL END AS cpk_rfh1,
                        avg_rfh1,
                        std_rfh1,
                        outliers_rfh1,
                        CASE WHEN std_cony > 1e-6 THEN LEAST((usl_cony - avg_cony) / (3.0 * std_cony), (avg_cony - lsl_cony) / (3.0 * std_cony)) ELSE NULL END AS cpk_cony,
                        avg_cony,
                        std_cony,
                        outliers_cony,
                        sum_act_w,
                        sum_tar_w,
                        std_w,
                        outliers_weight
                    FROM spec_daily_stats
                )
                SELECT
                    time_period,
                    SUM(sample_size) AS total_n,
                    SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfpp,
                    SUM(avg_rfpp * sample_size) / NULLIF(SUM(CASE WHEN avg_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_avg_rfpp,
                    SQRT(SUM(POWER(COALESCE(std_rfpp, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_rfpp,
                    SUM(outliers_rfpp) AS outliers_rfpp,
                    SUM(cpk_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_rfh1,
                    SUM(avg_rfh1 * sample_size) / NULLIF(SUM(CASE WHEN avg_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_avg_rfh1,
                    SQRT(SUM(POWER(COALESCE(std_rfh1, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_rfh1 IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_rfh1,
                    SUM(outliers_rfh1) AS outliers_rfh1,
                    SUM(cpk_cony * sample_size) / NULLIF(SUM(CASE WHEN cpk_cony IS NOT NULL THEN sample_size ELSE 0 END), 0) AS weighted_cpk_cony,
                    SUM(avg_cony * sample_size) / SUM(sample_size) AS weighted_avg_cony,
                    SQRT(SUM(POWER(COALESCE(std_cony, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_cony IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_cony,
                    SUM(outliers_cony) AS outliers_cony,
                    (SUM(sum_act_w) - SUM(sum_tar_w)) / NULLIF(SUM(sum_tar_w), 0.0) * 100.0 as weighted_diff_weight,
                    SQRT(SUM(POWER(COALESCE(std_w, 0), 2) * sample_size) / NULLIF(SUM(CASE WHEN std_w IS NOT NULL THEN sample_size ELSE 0 END), 0)) AS weighted_std_weight,
                    SUM(outliers_weight) AS outliers_weight
                FROM spec_cpk
                GROUP BY 1
                ORDER BY 1
            """
            params = exclude_params
        rows = qry(sql, params)

        periods = sorted(list(set(str(r['time_period']) for r in rows)))
        period_idx = {p: i for i, p in enumerate(periods)}

        cpk_trends = {
            "RFPP 综合 CPK": [None] * len(periods),
            "RFH1 综合 CPK": [None] * len(periods)
        }
        stats_by_date = {}

        for r in rows:
            p_str = str(r['time_period'])
            idx = period_idx[p_str]

            total_n = int(r['total_n']) if r.get('total_n') is not None else 0
            cpk_rfpp = r['weighted_cpk_rfpp']
            avg_rfpp = r.get('weighted_avg_rfpp')
            std_rfpp = r.get('weighted_std_rfpp')
            outliers_rfpp = int(r['outliers_rfpp']) if r.get('outliers_rfpp') is not None else None

            cpk_rfh1 = r['weighted_cpk_rfh1']
            avg_rfh1 = r.get('weighted_avg_rfh1')
            std_rfh1 = r.get('weighted_std_rfh1')
            outliers_rfh1 = int(r['outliers_rfh1']) if r.get('outliers_rfh1') is not None else None

            cpk_cony = r.get('weighted_cpk_cony')
            avg_cony = r['weighted_avg_cony']
            std_cony = r.get('weighted_std_cony')
            outliers_cony = int(r['outliers_cony']) if r.get('outliers_cony') is not None else None

            avg_weight = r['weighted_diff_weight']
            std_weight = r.get('weighted_std_weight')
            outliers_weight = int(r['outliers_weight']) if r.get('outliers_weight') is not None else None

            p_stats = {
                "total_n": total_n,
                "rfpp": {
                    "cpk": round(float(cpk_rfpp), 4) if cpk_rfpp is not None and not (np.isnan(cpk_rfpp) or np.isinf(cpk_rfpp)) else None,
                    "mean": round(float(avg_rfpp), 3) if avg_rfpp is not None and not (np.isnan(avg_rfpp) or np.isinf(avg_rfpp)) else None,
                    "std": round(float(std_rfpp), 3) if std_rfpp is not None and not (np.isnan(std_rfpp) or np.isinf(std_rfpp)) else None,
                    "outliers": outliers_rfpp
                },
                "rfh1": {
                    "cpk": round(float(cpk_rfh1), 4) if cpk_rfh1 is not None and not (np.isnan(cpk_rfh1) or np.isinf(cpk_rfh1)) else None,
                    "mean": round(float(avg_rfh1), 3) if avg_rfh1 is not None and not (np.isnan(avg_rfh1) or np.isinf(avg_rfh1)) else None,
                    "std": round(float(std_rfh1), 3) if std_rfh1 is not None and not (np.isnan(std_rfh1) or np.isinf(std_rfh1)) else None,
                    "outliers": outliers_rfh1
                },
                "cony": {
                    "cpk": round(float(cpk_cony), 4) if cpk_cony is not None and not (np.isnan(cpk_cony) or np.isinf(cpk_cony)) else None,
                    "mean": round(float(avg_cony), 3) if avg_cony is not None and not (np.isnan(avg_cony) or np.isinf(avg_cony)) else None,
                    "std": round(float(std_cony), 3) if std_cony is not None and not (np.isnan(std_cony) or np.isinf(std_cony)) else None,
                    "outliers": outliers_cony
                },
                "weight": {
                    "cpk": round(float(avg_weight), 4) if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)) else None,
                    "mean": round(float(avg_weight), 3) if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)) else None,
                    "std": round(float(std_weight), 3) if std_weight is not None and not (np.isnan(std_weight) or np.isinf(std_weight)) else None,
                    "outliers": outliers_weight
                }
            }
            stats_by_date[p_str] = p_stats

            if cpk_rfpp is not None and not (np.isnan(cpk_rfpp) or np.isinf(cpk_rfpp)):
                cpk_trends["RFPP 综合 CPK"][idx] = round(float(cpk_rfpp), 4)
            if cpk_rfh1 is not None and not (np.isnan(cpk_rfh1) or np.isinf(cpk_rfh1)):
                cpk_trends["RFH1 综合 CPK"][idx] = round(float(cpk_rfh1), 4)
            if cpk_cony is not None and not (np.isnan(cpk_cony) or np.isinf(cpk_cony)):
                cpk_trends["CONY 综合 CPK"] = cpk_trends.get("CONY 综合 CPK", [None] * len(periods))
                cpk_trends["CONY 综合 CPK"][idx] = round(float(cpk_cony), 4)
            if avg_cony is not None and not (np.isnan(avg_cony) or np.isinf(avg_cony)):
                cpk_trends["CONY 综合 实际值"] = cpk_trends.get("CONY 综合 实际值", [None] * len(periods))
                cpk_trends["CONY 综合 实际值"][idx] = round(float(avg_cony), 4)
            if avg_weight is not None and not (np.isnan(avg_weight) or np.isinf(avg_weight)):
                cpk_trends["胎重 综合 偏差"] = cpk_trends.get("胎重 综合 偏差", [None] * len(periods))
                cpk_trends["胎重 综合 偏差"][idx] = round(float(avg_weight), 4)

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
