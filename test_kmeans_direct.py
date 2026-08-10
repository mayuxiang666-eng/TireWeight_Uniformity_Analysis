import sys
import os

# Add backend directory to path
sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import get_paths, get_suspects

print("=== Testing get_paths() ===")
res = get_paths(
    baseline_from="2026-06-13",
    baseline_to="2026-06-20",
    study_from="2026-06-21",
    study_to="2026-06-30",
    min_yield=50
)
print("Status:", res.get("status"))
data = res.get("data", {})
print("Cluster keys in paths data:", list(data.keys()))
for key, val in list(data.items())[:2]:
    print(f"Cluster {key} size of paths: {len(val)}, first 2 paths: {val[:2]}")

print("\n=== Testing get_suspects() ===")
res = get_suspects(
    study_from="2026-06-21",
    study_to="2026-06-30",
    article10=None,
    lift_threshold=1.5,
    min_yield=50
)
print("Status:", res.get("status"))
print("Suspects count:", len(res.get("data", [])))
print("Suspects sample:", res.get("data", [])[:2])
