import sys
sys.path.append('d:/Ava/untitled1/untitled1_v2/backend')
from main import calculate_critical_machine, qry, get_spec_usl
import numpy as np

# We want to replicate the exact calculation for article10 = '0315979059' on '2026-07-14'
article10 = '0315979059'
indicator = 'rfpp'
target_date = '2026-07-14'
min_samples = 30

indicator_col = "rfppwc_first"
global_usl = get_spec_usl(article10, indicator)
print("USL:", global_usl)

sql = f"""
    SELECT 
        CAST(gt_workcenter AS VARCHAR) as gt,
        CAST(ct_workcenter AS VARCHAR) as ct,
        CAST(tu_first_workcenter AS VARCHAR) as tu,
        CAST(tb_first_workcenter AS VARCHAR) as tb,
        COUNT(*) as lot_cnt,
        AVG(TRY_CAST({indicator_col} AS DOUBLE)) as avg_val,
        STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as std_val
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
      AND gt_workcenter IS NOT NULL
      AND ct_workcenter IS NOT NULL
      AND tu_first_workcenter IS NOT NULL
      AND tb_first_workcenter IS NOT NULL
    GROUP BY 1, 2, 3, 4
    HAVING COUNT(*) >= 1
"""
rows = qry(sql, [article10, target_date])
print("Total rows returned from DB:", len(rows))

data = []
for r in rows:
    lot_cnt = int(r['lot_cnt'])
    avg_val = float(r['avg_val']) if r['avg_val'] is not None else 0.0
    std_val = float(r['std_val']) if r['std_val'] is not None else 0.0
    cpk = (global_usl - avg_val) / (3.0 * std_val) if std_val > 0 else 1.33
    cpk = max(0.0, min(5.0, cpk))
    data.append({
        "lot_cnt": lot_cnt,
        "cpk": cpk,
        "gt_workcenter": r['gt'],
        "ct_workcenter": r['ct'],
        "tu_first_workcenter": r['tu'],
        "tb_first_workcenter": r['tb']
    })

total_tires = sum(p['lot_cnt'] for p in data)
total_weighted_cpk = sum(p['cpk'] * p['lot_cnt'] for p in data)
global_avg_cpk = total_weighted_cpk / total_tires
print("Total Tires:", total_tires)
print("Global Avg CPK:", global_avg_cpk)

cols = ["gt_workcenter", "ct_workcenter", "tu_first_workcenter", "tb_first_workcenter"]
machines = set()
for p in data:
    for col in cols:
        if p[col]:
            machines.add(p[col])

machine_list = []
for mach in machines:
    mach_tires = 0
    mach_weighted_cpk = 0
    partner_groups = {}

    for p in data:
        matched_cols = [col for col in cols if p[col] == mach]
        if matched_cols:
            mach_tires += p['lot_cnt']
            mach_weighted_cpk += p['cpk'] * p['lot_cnt']

            for m_col in matched_cols:
                partner_parts = [('*' if c == m_col else (p[c] or '*')) for c in cols]
                partner_key = "_".join(partner_parts)

                if partner_key not in partner_groups:
                    partner_groups[partner_key] = {
                        "mCol": m_col,
                        "partnerParts": partner_parts,
                        "machTires": 0,
                        "machWeightedCpk": 0
                    }
                partner_groups[partner_key]["machTires"] += p['lot_cnt']
                partner_groups[partner_key]["machWeightedCpk"] += p['cpk'] * p['lot_cnt']

    mach_avg_cpk = mach_weighted_cpk / mach_tires if mach_tires > 0 else 0.0

    controlled_baseline_numerator = 0.0
    controlled_baseline_denominator = 0.0

    for group in partner_groups.values():
        m_col = group["mCol"]
        partner_parts = group["partnerParts"]
        group_mach_tires = group["machTires"]

        other_tires = 0
        other_weighted_cpk = 0.0

        for p in data:
            if p[m_col] != mach:
                is_match = True
                for idx, c in enumerate(cols):
                    if c == m_col:
                        continue
                    if p[c] != partner_parts[idx]:
                        is_match = False
                        break
                if is_match:
                    other_tires += p['lot_cnt']
                    other_weighted_cpk += p['cpk'] * p['lot_cnt']

        partner_baseline = other_weighted_cpk / other_tires if other_tires > 0 else global_avg_cpk
        controlled_baseline_numerator += partner_baseline * group_mach_tires
        controlled_baseline_denominator += group_mach_tires

    controlled_baseline = (
        controlled_baseline_numerator / controlled_baseline_denominator
        if controlled_baseline_denominator > 0
        else global_avg_cpk
    )

    contribution = mach_avg_cpk - controlled_baseline
    volume = mach_tires / total_tires
    impact_score = contribution * volume

    machine_list.append({
        "machine": mach,
        "mach_tires": mach_tires,
        "mach_avg_cpk": mach_avg_cpk,
        "controlled_baseline": controlled_baseline,
        "contribution": contribution,
        "volume": volume,
        "impact_score": impact_score
    })

machine_list.sort(key=lambda x: x["impact_score"])
print("\n=== Machine Rankings ===")
for m in machine_list:
    print(f"Machine: {m['machine']}")
    print(f"  Tires (N): {m['mach_tires']}, Vol: {m['volume']:.3f}")
    print(f"  CPK: {m['mach_avg_cpk']:.4f}, Baseline: {m['controlled_baseline']:.4f}")
    print(f"  Contrib: {m['contribution']:.4f}")
    print(f"  Impact Score: {m['impact_score']:.6f}")
