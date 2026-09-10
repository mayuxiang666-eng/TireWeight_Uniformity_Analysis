import sys
import os

sys.path.insert(0, os.path.abspath("backend"))
from main import qry

time_expr = "COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_shift_date AS TIMESTAMP))"

later_rows = qry(f"""
    SELECT 
        tu_first_shift_date,
        ct_workcenter,
        COUNT(*) as cnt,
        MIN({time_expr}) as min_time,
        MAX({time_expr}) as max_time
    FROM clean_yield
    WHERE gt_workcenter IN ('TB224', 'TB124', 'TB24')
      AND article10 = '0312053000'
      AND {time_expr} >= '2026-08-10 10:37:00'::TIMESTAMP
    GROUP BY 1, 2
    ORDER BY min_time ASC
""")
print("Later production of 0312053000 on TB224:", later_rows)
