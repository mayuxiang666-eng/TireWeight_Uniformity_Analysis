# -*- coding: utf-8 -*-
"""
标准 CPK 计算与规格公差查询模块
"""
from typing import Optional, Tuple
from backend.core.db import qry


def get_spec_usl(article10: str, indicator: str) -> float:
    """获取指定规格在数据库中的规格上限值 (标准值 * 10)"""
    if not article10:
        return 100.0
    if indicator == "weight":
        return 0.28
    if indicator == "rfpp":
        sql = """
            SELECT COALESCE(ANY_VALUE(standard_rfpp),
                            CASE ANY_VALUE("group")
                                WHEN 'GROUP 1'  THEN 10.5
                                WHEN 'GROUP 2A' THEN 11.5
                                WHEN 'GROUP 2B' THEN 12.5
                                WHEN 'GROUP 3'  THEN 12.5
                                WHEN 'GROUP 4'  THEN 14.5
                            END) * 10.0 AS usl
            FROM clean_yield
            WHERE article10 = ?
        """
    elif indicator == "cony":
        sql = """
            SELECT ANY_VALUE(conny_usl) AS usl
            FROM clean_yield
            WHERE article10 = ? AND conny_usl IS NOT NULL
        """
        res = qry(sql, [article10])
        if res and res[0]['usl'] is not None:
            return float(res[0]['usl'])
        return 95.0
    else:
        sql = """
            SELECT COALESCE(ANY_VALUE(standard_rfh1),
                            CASE ANY_VALUE("group")
                                WHEN 'GROUP 1'  THEN 7.5
                                WHEN 'GROUP 2A' THEN 8.5
                                WHEN 'GROUP 2B' THEN 9.0
                                WHEN 'GROUP 3'  THEN 9.5
                                WHEN 'GROUP 4'  THEN 10.0
                            END) * 10.0 AS usl
            FROM clean_yield
            WHERE article10 = ?
        """
    res = qry(sql, [article10])
    if res and res[0]['usl'] is not None:
        return float(res[0]['usl'])
    return 100.0


def get_spec_limits(article10: str, indicator: str) -> Tuple[float, Optional[float]]:
    """获取指定规格的上下限元组 (usl, lsl)
    - rfpp/rfh1: 返回 (usl, None)  — 单侧上限
    - cony:      返回 (conny_usl, conny_lsl) — 从数据库取双侧限
    - weight:    返回 (0.28, -0.28) — 固定 ±0.28% 公差
    """
    if indicator == "weight":
        return 0.28, -0.28
    if indicator in ("rfpp", "rfh1"):
        return get_spec_usl(article10, indicator), None
    if indicator == "cony":
        if not article10:
            return 95.0, -95.0
        sql = """
            SELECT ANY_VALUE(conny_usl) as usl_v, ANY_VALUE(conny_lsl) as lsl_v
            FROM clean_yield
            WHERE article10 = ? AND conny_usl IS NOT NULL AND conny_lsl IS NOT NULL
        """
        res = qry(sql, [article10])
        if res and res[0]['usl_v'] is not None and res[0]['lsl_v'] is not None:
            return float(res[0]['usl_v']), float(res[0]['lsl_v'])
        return 95.0, -95.0
    return 100.0, None


def calc_cpk(mean: float, std: float, usl: float, lsl=None) -> float:
    """统一计算单侧或双侧 CPK (支持负值以真实反映超差程度)
    - lsl 为 None 时：单侧上限 CPK = (usl - mean) / (3 * std)
    - lsl 存在时：  双侧 CPK = min((usl - mean)/(3*std), (mean - lsl)/(3*std))
    """
    if std <= 1e-6:
        return 1.33
    if lsl is None:
        return max(-5.0, min(5.0, (usl - mean) / (3.0 * std)))
    cpu = (usl - mean) / (3.0 * std)
    cpl = (mean - lsl) / (3.0 * std)
    return max(-5.0, min(5.0, min(cpu, cpl)))
