import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from main import calculate_cgrs_cpk_comparison, reload_duckdb_data
import json

reload_duckdb_data()
res = calculate_cgrs_cpk_comparison(
    workcenter="TB224",
    article10="0312053000",
    target_date="2026-08-10",
    indicator="rfpp",
    limit_n=50
)
print("Updated calculation result for TB224 + 0312053000 on 2026-08-10:")
print(json.dumps(res, indent=2, ensure_ascii=False))
