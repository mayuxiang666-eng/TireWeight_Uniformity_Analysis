import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from main import calculate_cgrs_cpk_comparison, qry

res = calculate_cgrs_cpk_comparison(
    workcenter="TB224",
    article10="0312053000",
    target_date="2026-08-10",
    indicator="rfpp",
    limit_n=50
)
print("Result of calculate_cgrs_cpk_comparison:")
import json
print(json.dumps(res, indent=2, ensure_ascii=False))

# Let's also check what cgrs rows were found
rows = qry("SELECT * FROM cgrs_records WHERE (Workcenter = 'TB124' OR Workcenter = 'TB224') AND match_date = DATE '2026-08-10'")
print("\nFound CGRS rows:")
for r in rows:
    print(r.get('Workcenter'), r.get('TechOffsetLocalDate'), r.get('event_timestamp'), r.get('ParameterLocalName'), r.get('ProdSpecific2'))

# Let's check tu_first_loc_timestamp in clean_yield for TB224 and 0312053000
cy_rows = qry("""
    SELECT 
        gt_workcenter, 
        article10, 
        tu_first_loc_timestamp, 
        TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as tu_t,
        rfppwc_first
    FROM clean_yield
    WHERE gt_workcenter = 'TB224' AND article10 = '0312053000'
    ORDER BY tu_t DESC
    LIMIT 20
""")
print("\nClean yield rows (latest 20):")
for r in cy_rows:
    print(r)
