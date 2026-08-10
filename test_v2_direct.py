import sys
import os

# Add backend directory to path
sys.path.append(r"d:\Ava\untitled1\untitled1_v2\backend")

from main import get_summary, get_daily_trend, get_cpk_trend

print("=== Testing get_summary() ===")
res = get_summary()
print("Summary Result:", res)

print("\n=== Testing get_daily_trend(article10=None) ===")
res = get_daily_trend(article10=None)
print("Daily trend records count:", len(res.get("data", [])))
print("Daily trend sample:", res.get("data", [])[:2])

print("\n=== Testing get_cpk_trend(grain='daily', article10=None) ===")
res = get_cpk_trend(grain="daily", article10=None)
print("Status:", res.get("status"))
if res.get("status") == "error":
    print("Error Message:", res.get("message"))
else:
    data = res.get("data", {})
    print("Dates count:", len(data.get("dates", [])))
    print("Dates sample:", data.get("dates", [])[:5])
    print("Groups in cpk_trends:", list(data.get("cpk_trends", {}).keys()))
    for g, trend in data.get("cpk_trends", {}).items():
        valid_points = [x for x in trend if x is not None]
        print(f"Group {g}: total points={len(trend)}, valid points={len(valid_points)}, sample={valid_points[:5]}")
