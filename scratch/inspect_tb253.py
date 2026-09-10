# -*- coding: utf-8 -*-
import os
import sys
import duckdb
import pandas as pd
import numpy as np

BASE_DIR = r"d:\Ava\untitled1\untitled1_v2"
sys.path.insert(0, BASE_DIR)

from backend.main import (
    get_top_warning_machines,
    get_spec_warning_machines_detailed,
    calc_cpk,
    qry,
    db_conn,
    DATA_PATH
)

target_date = "2026-09-07"
article = "0315997056"
indicator = "rfpp"

print("DATA_PATH:", DATA_PATH)

# Check all GT machines for 0315997056 on 2026-09-07
time_col = "tu_first_loc_timestamp"
date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"

res = qry(f"""
    SELECT 
        gt_workcenter,
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) as usl
    FROM clean_yield
    WHERE {date_col} = ?::DATE
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
    GROUP BY gt_workcenter
    ORDER BY tires DESC
""", [target_date, article])

print(f"\n--- GT Machines on {target_date} for {article} ---")
for r in res:
    usl = (r['usl'] or 10.5) * 10.0
    cpk = calc_cpk(r['mean_rfpp'], r['std_rfpp'], usl, None) if r['std_rfpp'] else 1.33
    print(f"GT: {r['gt_workcenter']:6s} | Tires: {r['tires']:4d} | Mean: {r['mean_rfpp']:.2f} | Std: {r['std_rfpp']:.2f} | USL: {usl:.1f} | CPK: {cpk:.3f}")

# Check all CT machines
res_ct = qry(f"""
    SELECT 
        ct_workcenter,
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) as usl
    FROM clean_yield
    WHERE {date_col} = ?::DATE
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
    GROUP BY ct_workcenter
    ORDER BY tires DESC
""", [target_date, article])

print(f"\n--- CT Machines on {target_date} for {article} ---")
for r in res_ct:
    usl = (r['usl'] or 10.5) * 10.0
    cpk = calc_cpk(r['mean_rfpp'], r['std_rfpp'], usl, None) if r['std_rfpp'] else 1.33
    print(f"CT: {r['ct_workcenter']:6s} | Tires: {r['tires']:4d} | Mean: {r['mean_rfpp']:.2f} | Std: {r['std_rfpp']:.2f} | USL: {usl:.1f} | CPK: {cpk:.3f}")

# Check overall spec CPK
res_all = qry(f"""
    SELECT 
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) as usl
    FROM clean_yield
    WHERE {date_col} = ?::DATE
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
""", [target_date, article])
r = res_all[0]
usl = (r['usl'] or 10.5) * 10.0
spec_cpk = calc_cpk(r['mean_rfpp'], r['std_rfpp'], usl, None)
print(f"\n--- Overall Spec {article} on {target_date} ---")
print(f"Total Tires: {r['tires']} | Mean: {r['mean_rfpp']:.2f} | Std: {r['std_rfpp']:.2f} | Spec CPK: {spec_cpk:.3f}")

# Now call get_top_warning_machines
print("\n--- Calling get_top_warning_machines ---")
top_m = get_top_warning_machines(
    article10=article,
    target_date=target_date,
    indicator=indicator,
    n=10,
    time_col=time_col
)
for m in top_m:
    print(m)
