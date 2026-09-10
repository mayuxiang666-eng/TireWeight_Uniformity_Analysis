import sys
import os
sys.path.insert(0, "untitled1_v2/backend")
from main import get_cpk_trend, reload_duckdb_data

reload_duckdb_data()

print("--- 1. Testing get_cpk_trend with time_col='tu_first_loc_timestamp' (终检 TU 时间) ---")
res_tu = get_cpk_trend(grain="daily", time_col="tu_first_loc_timestamp")
data_tu = res_tu.get("data", {})
dates_tu = data_tu.get("dates", [])
print("TU Date count:", len(dates_tu))
print("TU Dates (first 5):", dates_tu[:5])
print("TU Dates (last 5):", dates_tu[-5:])
print("TU RFPP Trends (first 5):", data_tu.get("cpk_trends", {}).get("RFPP 综合 CPK", [])[:5])

print("\n--- 2. Testing get_cpk_trend with time_col='gt_loc_timestamp' (成型 GT 时间) ---")
res_gt = get_cpk_trend(grain="daily", time_col="gt_loc_timestamp")
data_gt = res_gt.get("data", {})
dates_gt = data_gt.get("dates", [])
print("GT Date count:", len(dates_gt))
print("GT Dates (first 5):", dates_gt[:5])
print("GT Dates (last 5):", dates_gt[-5:])
print("GT RFPP Trends (first 5):", data_gt.get("cpk_trends", {}).get("RFPP 综合 CPK", [])[:5])
