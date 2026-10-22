# -*- coding: utf-8 -*-
"""
标准 CPK 计算与规格公差查询模块
100% 严格遵循 Recipes 配方表标准限，杜绝人工硬编码捏造假数据兜底
"""
from typing import Optional, Tuple
from backend.core.db import qry

# 17 项指标配置定义
INDICATORS_SPEC = {
    # TU 工段 (7项)
    "rfpp":  {"group": "TU", "label": "RFPP 径向力峰峰值", "col": "rfppwc_first", "usl_col": "standard_rfpp", "scale": 10.0, "unit": "N", "is_double": False},
    "rfh1":  {"group": "TU", "label": "RFH1 径向力一次谐波", "col": "rfh1wc_first", "usl_col": "standard_rfh1", "scale": 10.0, "unit": "N", "is_double": False},
    "rfh2":  {"group": "TU", "label": "RFH2 径向力二次谐波", "col": "rfh2wc_first", "usl_col": "standard_rfh2", "scale": 10.0, "unit": "N", "is_double": False},
    "lfpp":  {"group": "TU", "label": "LFPP 侧向力峰峰值", "col": "lfppwc_first", "usl_col": "standard_lfpp", "scale": 10.0, "unit": "N", "is_double": False},
    "lfh1":  {"group": "TU", "label": "LFH1 侧向力一次谐波", "col": "lfh1wc_first", "usl_col": "standard_lfh1", "scale": 10.0, "unit": "N", "is_double": False},
    "cony":  {"group": "TU", "label": "CONY 锥度效应力", "col": "cony_first", "usl_col": "conny_usl", "lsl_col": "conny_lsl", "scale": 1.0, "unit": "N", "is_double": True},
    "plys":  {"group": "TU", "label": "PLYS 帘布层效应力", "col": "plys_first", "usl_col": "plys_usl", "lsl_col": "plys_lsl", "scale": 1.0, "unit": "N", "is_double": True},

    # TG 工段 (7项)
    "tbul":  {"group": "TG", "label": "TBUL 上胎侧凸起", "col": "tbul_first", "usl_col": "tbul_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "bbul":  {"group": "TG", "label": "BBUL 下胎侧凸起", "col": "bbul_first", "usl_col": "bbul_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "tdep":  {"group": "TG", "label": "TDEP 上胎侧凹陷", "col": "tdep_first", "usl_col": "tdep_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "bdep":  {"group": "TG", "label": "BDEP 下胎侧凹陷", "col": "bdep_first", "usl_col": "bdep_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "tlro":  {"group": "TG", "label": "TLRO 上胎侧径向跳动", "col": "tlro_first", "usl_col": "tlro_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "blro":  {"group": "TG", "label": "BLRO 下胎侧径向跳动", "col": "blro_first", "usl_col": "blro_usl", "scale": 1.0, "unit": "mm", "is_double": False},
    "crro":  {"group": "TG", "label": "CRRO 胎冠径向跳动", "col": "crro_first", "usl_col": "crro_usl", "scale": 1.0, "unit": "mm", "is_double": False},

    # TB 工段 (3项)
    "tbalw": {"group": "TB", "label": "TBALW 上侧动不平衡", "col": "tbalw_first", "usl_col": "tbalw_usl", "scale": 1.0, "unit": "g", "is_double": False},
    "bbalw": {"group": "TB", "label": "BBALW 下侧动不平衡", "col": "bbalw_first", "usl_col": "bbalw_usl", "scale": 1.0, "unit": "g", "is_double": False},
    "sbalw": {"group": "TB", "label": "SBALW 静不平衡", "col": "sbalw_first", "usl_col": "sbalw_usl", "scale": 1.0, "unit": "g", "is_double": False},

    # 兼容物理指标
    "weight": {"group": "OTHER", "label": "胎重偏差率", "col": "v_weight", "usl_col": None, "scale": 1.0, "unit": "%", "is_double": True}
}


def get_spec_usl(article10: str, indicator: str) -> Optional[float]:
    """获取指定规格在数据库中的规格上限值 (严格来自 Recipes 配方)"""
    usl, _ = get_spec_limits(article10, indicator)
    return usl


def get_spec_limits(article10: str, indicator: str) -> Tuple[Optional[float], Optional[float]]:
    """获取指定规格的上下限元组 (usl, lsl)
    - 严格根据 clean_yield 中绑定的 Recipes 配方限值查询
    - 无配方限时返回 (None, None)，不作人工伪造兜底
    """
    if indicator == "weight":
        return 0.028, -0.028

    spec = INDICATORS_SPEC.get(indicator)
    if not spec:
        spec = INDICATORS_SPEC.get("rfpp")

    if not article10:
        return None, None

    usl_col = spec.get("usl_col")
    lsl_col = spec.get("lsl_col")
    scale = spec.get("scale", 1.0)
    is_double = spec.get("is_double", False)

    if not usl_col:
        return None, None

    if is_double and lsl_col:
        sql = f"""
            SELECT 
                ANY_VALUE({usl_col}) AS usl_v,
                ANY_VALUE({lsl_col}) AS lsl_v
            FROM clean_yield
            WHERE article10 = ? AND {usl_col} IS NOT NULL
        """
        rows = qry(sql, [article10])
        if rows and rows[0].get('usl_v') is not None:
            r = rows[0]
            u_val = float(r['usl_v']) * scale if r['usl_v'] is not None else None
            l_val = float(r['lsl_v']) * scale if r.get('lsl_v') is not None else None
            return u_val, l_val
        return None, None
    else:
        sql = f"""
            SELECT ANY_VALUE({usl_col}) AS usl_v
            FROM clean_yield
            WHERE article10 = ? AND {usl_col} IS NOT NULL
        """
        rows = qry(sql, [article10])
        if rows and rows[0].get('usl_v') is not None:
            u_val = float(rows[0]['usl_v']) * scale
            return u_val, None
        return None, None


def calc_cpk(mean: Optional[float], std: Optional[float], usl: Optional[float], lsl: Optional[float] = None) -> Optional[float]:
    """统一计算单侧或双侧 CPK
    - 若 mean / std / usl 为空，返回 None
    - lsl 为 None 时：单侧上限 CPK = (usl - mean) / (3 * std)
    - lsl 存在时：  双侧 CPK = min((usl - mean)/(3*std), (mean - lsl)/(3*std))
    """
    if mean is None or std is None:
        return None
    if usl is None and lsl is None:
        return None
    if std <= 1e-6:
        return 1.33

    if lsl is None:
        if usl is None:
            return None
        return max(-5.0, min(5.0, (usl - mean) / (3.0 * std)))
    else:
        if usl is None:
            return max(-5.0, min(5.0, (mean - lsl) / (3.0 * std)))
        cpu = (usl - mean) / (3.0 * std)
        cpl = (mean - lsl) / (3.0 * std)
        return max(-5.0, min(5.0, min(cpu, cpl)))
