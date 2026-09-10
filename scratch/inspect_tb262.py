import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from main import qry, db_conn

print("=== 1. Machine name candidates ===")
wc_clean = "TB262"
cgrs_candidates = [wc_clean]
gt_candidates = [wc_clean]
if wc_clean.startswith("TB2"):
    cgrs_candidates.append("TB1" + wc_clean[3:])
    gt_candidates.append("TB" + wc_clean[3:])

print("CGRS Candidates:", cgrs_candidates)
print("GT Candidates:", gt_candidates)

print("\n=== 2. CGRS records for TB262 / TB162 ===")
cgrs_rows = qry(f"""
    SELECT TechOffsetLocalDate, event_timestamp, Workcenter, ParameterName, ParameterLocalName, ProdSpecific2, ProdSpecific1
    FROM cgrs_records
    WHERE Workcenter IN ('TB262', 'TB162', 'TB62')
    ORDER BY event_timestamp ASC
""")
for r in cgrs_rows:
    print("  CGRS:", r)

time_expr = "COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))"

print("\n=== 3. Clean_yield records for TB262 / TB162 / TB62 + 0315124087 (ALL TIME) ===")
all_records_spec = qry(f"""
    SELECT 
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE (gt_workcenter IN ('TB262', 'TB162', 'TB62') OR gt_workcenter LIKE '%262%' OR gt_workcenter LIKE '%162%')
      AND article10 LIKE '0315124%'
""")
print("  Total records for 0315124%:", all_records_spec)

print("\n=== 4. Check distinct articles on TB262 / TB162 around 2026-08-10 ~ 2026-08-11 ===")
around_records = qry(f"""
    SELECT 
        article10,
        gt_workcenter,
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE (gt_workcenter IN ('TB262', 'TB162', 'TB62') OR gt_workcenter LIKE '%262%' OR gt_workcenter LIKE '%162%')
      AND {time_expr} >= '2026-08-10 00:00:00'::TIMESTAMP
      AND {time_expr} <= '2026-08-11 23:59:59'::TIMESTAMP
    GROUP BY article10, gt_workcenter
    ORDER BY min_time ASC
""")
for r in around_records:
    print("  Production around 08-10~08-11:", r)

print("\n=== 5. Check what was produced on TB262 before 2026-08-11 01:02:00 ===")
before_0102 = qry(f"""
    SELECT 
        barcode,
        article10,
        gt_workcenter,
        {time_expr} as prod_time,
        rfppwc_first
    FROM clean_yield
    WHERE (gt_workcenter IN ('TB262', 'TB162', 'TB62') OR gt_workcenter LIKE '%262%' OR gt_workcenter LIKE '%162%')
      AND {time_expr} < '2026-08-11 01:02:00'::TIMESTAMP
    ORDER BY {time_expr} DESC
    LIMIT 15
""")
print(f"  Count before 01:02: {len(before_0102)}")
for r in before_0102:
    print("    Before 01:02 tire:", r)

print("\n=== 6. Check what was produced on TB262 after 2026-08-11 01:02:00 ===")
after_0102 = qry(f"""
    SELECT 
        barcode,
        article10,
        gt_workcenter,
        {time_expr} as prod_time,
        rfppwc_first
    FROM clean_yield
    WHERE (gt_workcenter IN ('TB262', 'TB162', 'TB62') OR gt_workcenter LIKE '%262%' OR gt_workcenter LIKE '%162%')
      AND {time_expr} >= '2026-08-11 01:02:00'::TIMESTAMP
    ORDER BY {time_expr} ASC
    LIMIT 15
""")
print(f"  Count after 01:02: {len(after_0102)}")
for r in after_0102:
    print("    After 01:02 tire:", r)
