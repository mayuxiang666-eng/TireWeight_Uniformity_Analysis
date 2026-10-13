# -*- coding: utf-8 -*-
"""
Production time & phase SQL utility module
"""
from typing import Optional, Dict


def build_production_time_where(
    time_col: str = "tu_first_loc_timestamp",
    date_single: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    shift: Optional[str] = None
) -> str:
    """
    Build DuckDB SQL WHERE conditions for production time and shift windows.
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
    Convert phase string to DuckDB SQL WHERE filter on ct_shop:
    - P3 (三期): ct_shop is null or ct_shop does not contain 'P4'
    - P4 (四期): ct_shop is not null and ct_shop contains 'P4'
    - 'all' or None: no filter
    """
    if not phase or str(phase).lower() == "all":
        return ""
    p_lower = str(phase).lower()
    if p_lower in ("p3", "3", "phase3", "三期"):
        return " AND (ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%')"
    if p_lower in ("p4", "4", "phase4", "四期"):
        return " AND (ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%')"
    return ""


_MACHINE_PHASE_CACHE: Dict[str, str] = {}


def init_machine_phase_cache(con=None) -> Dict[str, str]:
    """
    Precompute plant-wide machine phase mapping (P3 / P4) cached in memory.
    """
    global _MACHINE_PHASE_CACHE
    try:
        if con is None:
            from backend.core.db import db_conn
            con = db_conn
        
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        if 'clean_yield' not in tables:
            return _MACHINE_PHASE_CACHE
            
        sql = """
            SELECT 
                m,
                CASE WHEN SUM(CASE WHEN UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%' THEN 1 ELSE 0 END) >
                          SUM(CASE WHEN UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%' OR ct_shop IS NULL THEN 1 ELSE 0 END)
                     THEN 'P4' ELSE 'P3' END as phase
            FROM (
                SELECT ct_workcenter as m, ct_shop FROM clean_yield WHERE ct_workcenter IS NOT NULL AND ct_workcenter != ''
                UNION ALL
                SELECT gt_workcenter as m, ct_shop FROM clean_yield WHERE gt_workcenter IS NOT NULL AND gt_workcenter != ''
                UNION ALL
                SELECT tu_first_workcenter as m, ct_shop FROM clean_yield WHERE tu_first_workcenter IS NOT NULL AND tu_first_workcenter != ''
            )
            GROUP BY 1
        """
        rows = con.execute(sql).fetchall()
        _MACHINE_PHASE_CACHE = {str(r[0]).strip().upper(): str(r[1]).strip().upper() for r in rows if r[0]}
        print(f"[time_utils] Plant machine phase cache warmed up with {len(_MACHINE_PHASE_CACHE)} machines.")
    except Exception as e:
        print(f"[time_utils] init_machine_phase_cache error: {e}")
    return _MACHINE_PHASE_CACHE


def get_machine_phase(machine: str) -> str:
    """
    Get machine phase ('P4' or 'P3') with O(1) in-memory lookup (0ms).
    """
    if not machine:
        return "P3"
    mach_clean = str(machine).strip().upper()
    global _MACHINE_PHASE_CACHE
    if not _MACHINE_PHASE_CACHE:
        init_machine_phase_cache()
    return _MACHINE_PHASE_CACHE.get(mach_clean, "P3")
