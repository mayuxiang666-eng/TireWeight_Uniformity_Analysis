# -*- coding: utf-8 -*-
"""
生产日期与班次 SQL 过滤条件构造模块
"""
from typing import Optional


def build_production_time_where(
    time_col: str = "tu_first_loc_timestamp",
    date_single: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    shift: Optional[str] = None
) -> str:
    """
    构造 DuckDB SQL WHERE 时间条件。
    天的划分：精细到分，从第一天 08:00:00 到第二天 08:00:00 作为一天的划分。
    班组划分：
      - 'all' / None: 08:00 ~ 次日08:00
      - 'morning': 08:00 ~ 16:00
      - 'middle': 16:00 ~ 24:00
      - 'night': 24:00 ~ 08:00 (次日00:00~08:00)
    """
    col_ref = time_col if time_col else "tu_first_loc_timestamp"
    ts_expr = f"TRY_CAST({col_ref} AS TIMESTAMP)"
    prod_date_expr = f"CAST(({ts_expr} - INTERVAL 8 HOUR) AS DATE)"
    
    conds = [f"{col_ref} IS NOT NULL"]
    
    if date_single:
        conds.append(f"{prod_date_expr} = '{date_single}'")
    elif date_from and date_to:
        conds.append(f"{prod_date_expr} BETWEEN '{date_from}' AND '{date_to}'")
    elif date_from:
        conds.append(f"{prod_date_expr} >= '{date_from}'")
    elif date_to:
        conds.append(f"{prod_date_expr} <= '{date_to}'")
        
    if shift and shift != 'all':
        hr_expr = f"EXTRACT(HOUR FROM {ts_expr})"
        if shift == 'morning':
            conds.append(f"({hr_expr} >= 8 AND {hr_expr} < 16)")
        elif shift == 'middle':
            conds.append(f"({hr_expr} >= 16 AND {hr_expr} < 24)")
        elif shift == 'night':
            conds.append(f"({hr_expr} >= 0 AND {hr_expr} < 8)")
            
    return " AND ".join(conds)


def get_phase_sql_condition(phase: Optional[str]) -> str:
    """
    根据 phase 参数生成 DuckDB SQL 过滤条件
    - 'p3': ct_shop 为空或不含 'P4' / 'p4' (三期)
    - 'p4': ct_shop 包含 'P4' / 'p4' (四期)
    - 'all' 或 None: 不限制期别
    """
    if not phase or phase == "all":
        return ""
    if phase == "p3":
        return " AND (ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%')"
    if phase == "p4":
        return " AND (ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%')"
    return ""
