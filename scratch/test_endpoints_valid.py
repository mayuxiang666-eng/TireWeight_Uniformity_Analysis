import sys
import os

sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import get_paths, get_joint_combinations, get_insights

print("=== Calling get_paths with valid dates ===")
res_paths = get_paths(
    baseline_from="2026-06-13",
    baseline_to="2026-06-22",
    study_from="2026-06-23",
    study_to="2026-07-02",
    min_yield=50
)
print("Paths Status:", res_paths.get("status"))
if "message" in res_paths:
    print("Paths Message:", res_paths.get("message"))
print("Paths Cluster keys:", list(res_paths.get("data", {}).keys()) if res_paths.get("data") else None)

print("\n=== Calling get_joint_combinations with valid dates ===")
res_comb = get_joint_combinations(
    study_from="2026-06-23",
    study_to="2026-07-02",
    min_yield=50
)
print("Combinations Status:", res_comb.get("status"))
if "message" in res_comb:
    print("Combinations Message:", res_comb.get("message"))
print("Combinations count:", len(res_comb.get("data", [])) if res_comb.get("data") else None)

print("\n=== Calling get_insights with valid dates ===")
res_insights = get_insights(
    baseline_from="2026-06-13",
    baseline_to="2026-06-22",
    study_from="2026-06-23",
    study_to="2026-07-02",
    min_yield=50
)
print("Insights Status:", res_insights.get("status"))
if "message" in res_insights:
    print("Insights Message:", res_insights.get("message"))
print("Insights Alerts count:", len(res_insights.get("data", {}).get("alerts", [])) if res_insights.get("data") else None)
