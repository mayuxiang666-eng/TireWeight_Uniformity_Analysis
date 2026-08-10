import sys
import os

sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import get_machines

print("=== Running local call to get_machines ===")
res = get_machines(
    baseline_from="2026-06-08",
    baseline_to="2026-06-11",
    study_from="2026-06-05",
    study_to="2026-06-09",
    min_yield=50,
    workcenter_col="tread",
    cluster_id=0,
    cluster_type="anomaly"
)
print("Result Status:", res.get("status"))
if "message" in res:
    print("Result Message:", res.get("message"))
print("Result Data Length:", len(res.get("data", [])))
print("Result Data:", res.get("data"))
