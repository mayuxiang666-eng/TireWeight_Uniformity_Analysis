import sys
import os

sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import get_machines

print("=== Running local call to get_machines with VALID dates and explicit limit ===")
res = get_machines(
    baseline_from="2026-06-13",
    baseline_to="2026-06-22",
    study_from="2026-06-23",
    study_to="2026-07-02",
    min_yield=50,
    workcenter_col="tread",
    cluster_id=0,
    cluster_type="anomaly",
    limit=20
)
print("Result Status:", res.get("status"))
if "message" in res:
    print("Result Message:", res.get("message"))
print("Result Data Length:", len(res.get("data", [])))
if res.get("data"):
    print("Result Data Sample (first 2):", res.get("data")[:2])
