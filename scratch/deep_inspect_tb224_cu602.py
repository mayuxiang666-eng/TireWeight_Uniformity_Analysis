import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from main import qry, db_conn

print("=== 1. CGRS Records for TB224 / TB124 around 2026-08-10 ===")
cgrs_rows = qry("""
    SELECT TechOffsetLocalDate, event_timestamp, Workcenter, ParameterName, ProdSpecific2, ProdSpecific1
    FROM cgrs_records
    WHERE Workcenter IN ('TB224', 'TB124', 'TB24')
    ORDER BY event_timestamp ASC
""")
for r in cgrs_rows:
    print("  CGRS:", r['TechOffsetLocalDate'], r['event_timestamp'], r['Workcenter'], r['ParameterName'], r['ProdSpecific2'])

time_expr = "COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))"

print("\n=== 2. Total clean_yield records for TB224 + 0312053000 after 2026-08-10 09:21 ===")
total_after_spec = qry(f"""
    SELECT 
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE gt_workcenter IN ('TB224', 'TB124', 'TB24')
      AND article10 = '0312053000'
      AND {time_expr} >= '2026-08-10 09:21:00'::TIMESTAMP
""")
print("  Total post records for spec 0312053000:", total_after_spec)

print("\n=== 3. Breakdown by CT Workcenter for TB224 + 0312053000 after 09:21 ===")
ct_breakdown = qry(f"""
    SELECT 
        ct_workcenter,
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE gt_workcenter IN ('TB224', 'TB124', 'TB24')
      AND article10 = '0312053000'
      AND {time_expr} >= '2026-08-10 09:21:00'::TIMESTAMP
    GROUP BY ct_workcenter
    ORDER BY cnt DESC
""")
for r in ct_breakdown:
    print(f"  CT Machine: {r['ct_workcenter']} | Count: {r['cnt']} | Min: {r['min_time']} | Max: {r['max_time']}")

print("\n=== 4. What happened after 10:36:51? Did TB224 switch article or stop? ===")
after_spec_prod = qry(f"""
    SELECT 
        article10,
        ct_workcenter,
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE gt_workcenter IN ('TB224', 'TB124', 'TB24')
      AND {time_expr} >= '2026-08-10 10:36:00'::TIMESTAMP
    GROUP BY article10, ct_workcenter
    ORDER BY min_time ASC
    LIMIT 20
""")
for r in after_spec_prod:
    print(f"  Next batch: Article={r['article10']} | CT={r['ct_workcenter']} | Count={r['cnt']} | Time: {r['min_time']} ~ {r['max_time']}")

print("\n=== 5. List all 17 tires of TB224 + CU602 after 09:21 ===")
cu602_tires = qry(f"""
    SELECT 
        barcode,
        article10,
        {time_expr} as prod_time,
        rfppwc_first
    FROM clean_yield
    WHERE gt_workcenter IN ('TB224', 'TB124', 'TB24')
      AND ct_workcenter = 'CU602'
      AND article10 = '0312053000'
      AND {time_expr} >= '2026-08-10 09:21:00'::TIMESTAMP
    ORDER BY {time_expr} ASC
""")
for idx, r in enumerate(cu602_tires):
    print(f"  [{idx+1:02d}] Barcode: {r['barcode']} | Time: {r['prod_time']} | RFPP: {r['rfppwc_first']}")
