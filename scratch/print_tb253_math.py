# -*- coding: utf-8 -*-
import duckdb
import os
import sys
import math
import pandas as pd
import numpy as np

pq_path = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\backend\data\yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{pq_path}')")

target_date = "2026-09-07"
article10 = "0315997056"
indicator = "rfpp"

# Ensure tu_first_shift_date exists
cols = [r[0] for r in con.execute("DESCRIBE clean_yield").fetchall()]
if 'tu_first_loc_timestamp' in cols and 'tu_first_shift_date' not in cols:
    con.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_shift_date VARCHAR")
    con.execute("UPDATE clean_yield SET tu_first_shift_date = STRFTIME(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP), '%Y-%m-%d')")

# Import functions from backend.main
sys.path.insert(0, r"d:\Ava\untitled1\untitled1_v2")
from backend.main import (
    aggregate_node_stats_py,
    calc_cpk,
    get_spec_limits,
    qry
)

global_usl, global_lsl = get_spec_limits(article10, indicator)

# Fetch paths
cols = ["gt_workcenter", "ct_workcenter", "tu_first_workcenter"]
sql = f"""
    SELECT
        CAST(gt_workcenter AS VARCHAR) as gt,
        CAST(ct_workcenter AS VARCHAR) as ct,
        CAST(tu_first_workcenter AS VARCHAR) as tu,
        COUNT(*) as lot_cnt,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_val,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_val
    FROM clean_yield
    WHERE article10 = ?
      AND tu_first_shift_date::DATE = ?::DATE
      AND gt_workcenter IS NOT NULL
      AND ct_workcenter IS NOT NULL
    GROUP BY 1, 2, 3
    HAVING COUNT(*) >= 1
"""
rows = qry(sql, [article10, target_date])

data = []
for r in rows:
    lot_cnt = int(r['lot_cnt'])
    avg_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
    std_val = float(r['std_val']) if r['std_val'] is not None else 0.0
    cpk = calc_cpk(avg_val, std_val, global_usl, global_lsl)
    data.append({
        "lot_cnt": lot_cnt,
        "cpk": cpk,
        "avg_val": avg_val,
        "std_val": std_val,
        "gt_workcenter": r['gt'],
        "ct_workcenter": r['ct'],
        "tu_first_workcenter": r['tu'],
    })

total_tires = sum(p['lot_cnt'] for p in data)
global_avg_cpk = aggregate_node_stats_py(data, global_usl, indicator, lsl=global_lsl)["cpk"]

print(f"Total Tires for {article10} on {target_date}: {total_tires}")
print(f"Global Avg CPK for {article10}: {global_avg_cpk:.4f}")

# Machine analysis
machines = {}
for p in data:
    for col in cols:
        m_val = p.get(col)
        if m_val:
            machines[m_val] = col

raw_machine_list = []
for mach, mach_col in machines.items():
    mach_tires = 0
    matching_rows = []
    partner_groups = {}

    for p in data:
        matched_cols = [col for col in cols if p.get(col) == mach]
        if matched_cols:
            mach_tires += p['lot_cnt']
            matching_rows.append(p)
            for m_col in matched_cols:
                partner_parts = [('*' if c == m_col else (p.get(c) or '*')) for c in cols]
                partner_key = "_".join(partner_parts)
                if partner_key not in partner_groups:
                    partner_groups[partner_key] = {
                        "mCol": m_col,
                        "partnerParts": partner_parts,
                        "machTires": 0
                    }
                partner_groups[partner_key]["machTires"] += p['lot_cnt']

    mach_avg_cpk = aggregate_node_stats_py(matching_rows, global_usl, indicator, lsl=global_lsl)["cpk"] if matching_rows else 0.0
    controlled_baseline_numerator = 0.0
    controlled_baseline_denominator = 0.0

    for group in partner_groups.values():
        m_col = group["mCol"]
        partner_parts = group["partnerParts"]
        group_mach_tires = group["machTires"]
        other_rows = []
        for p in data:
            if p.get(m_col) != mach:
                is_match = True
                for idx, c in enumerate(cols):
                    if c == m_col:
                        continue
                    if p.get(c) != partner_parts[idx]:
                        is_match = False
                        break
                if is_match:
                    other_rows.append(p)

        partner_baseline = aggregate_node_stats_py(other_rows, global_usl, indicator, lsl=global_lsl)["cpk"] if other_rows else global_avg_cpk
        controlled_baseline_numerator += partner_baseline * group_mach_tires
        controlled_baseline_denominator += group_mach_tires

    controlled_baseline = (
        controlled_baseline_numerator / controlled_baseline_denominator
        if controlled_baseline_denominator > 0
        else global_avg_cpk
    )

    contribution = mach_avg_cpk - controlled_baseline
    volume = mach_tires / total_tires
    sqrt_tires = math.sqrt(mach_tires)

    raw_machine_list.append({
        "machine": mach,
        "workcenter_col": mach_col,
        "mach_avg_cpk": mach_avg_cpk,
        "controlled_baseline": controlled_baseline,
        "contribution": contribution,
        "volume": volume,
        "mach_tires": mach_tires,
        "sqrt_tires": sqrt_tires
    })

total_sqrt_tires = sum(m["sqrt_tires"] for m in raw_machine_list)
machine_list = []
for m in raw_machine_list:
    sqrt_volume_share = (m["sqrt_tires"] / total_sqrt_tires) if total_sqrt_tires > 0 else 0.0
    impact_score = m["contribution"] * sqrt_volume_share
    m["sqrt_volume_share"] = sqrt_volume_share
    m["impact_score"] = impact_score
    machine_list.append(m)

# Sort by impact_score ascending (most negative first)
machine_list.sort(key=lambda x: x["impact_score"])

print("\n" + "="*95)
print(f"{'Machine':8s} | {'Process':5s} | {'Tires':5s} | {'Mach CPK':8s} | {'Baseline':8s} | {'Contrib':8s} | {'SqrtVol%':8s} | {'ImpactScore':11s}")
print("="*95)
for m in machine_list:
    proc = "GT" if "gt" in m['workcenter_col'] else ("CT" if "ct" in m['workcenter_col'] else "TU")
    print(f"{m['machine']:8s} | {proc:5s} | {m['mach_tires']:5d} | {m['mach_avg_cpk']:8.3f} | {m['controlled_baseline']:8.3f} | {m['contribution']:8.4f} | {m['sqrt_volume_share']*100:7.2f}% | {m['impact_score']:11.4f}")
print("="*95)
