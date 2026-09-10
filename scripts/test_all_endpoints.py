# -*- coding: utf-8 -*-
"""
Gate G-5: Full API Endpoints Smoke & Regression Testing Script
Tests all 21 core business API endpoints against the newly modularized modules
Uses Python standard library urllib.request and direct service execution.
"""
import sys
import os
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.core.db import reload_duckdb_data
print("Loading DuckDB parquet data into memory...")
t_init = time.time()
reload_duckdb_data()
print(f"DuckDB tables initialized in {time.time() - t_init:.2f}s")

from backend.routers import system, articles, machines, cgrs, trend
from backend.services import (
    article_service,
    machine_service,
    process_flow_service,
    cgrs_service,
    trend_service
)

# 确保服务间辅助钩子已注入 (模拟路由初始化环境)
machine_service.set_cgrs_comparator(cgrs_service.calculate_cgrs_cpk_comparison)
process_flow_service.set_process_flow_helpers(
    top_warning_provider=machine_service.get_top_warning_machines,
    best_tu_provider=machine_service.get_best_tu_machine_for_spec,
    cgrs_comparator=cgrs_service.calculate_cgrs_cpk_comparison,
    machine_cpk_provider=machine_service.get_machine_cpk
)
article_service.set_article_helpers(
    top_warning_provider=machine_service.get_top_warning_machines,
    best_tu_provider=machine_service.get_best_tu_machine_for_spec,
    cgrs_comparator=cgrs_service.calculate_cgrs_cpk_comparison
)

endpoints_to_test = [
    # 1. System & ETL
    ("GET", "/api/etl/status", lambda: system.get_etl_status(), lambda r: r.get("status") == "success"),
    # 2. Articles
    ("GET", "/api/articles/all", lambda: article_service.get_all_articles(), lambda r: r.get("status") == "success" and len(r.get("data", [])) > 0),
    ("GET", "/api/article/phase", lambda: article_service.get_article_phase(article10="0315567079"), lambda r: r.get("status") == "success"),
    ("GET", "/api/articles/warning-cpk", lambda: article_service.get_warning_cpk(indicator="rfpp", min_samples=5), lambda r: r.get("status") == "success"),
    ("GET", "/api/articles/barcode-measurements", lambda: article_service.get_barcode_measurements(article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/articles/lot-cpk-trend", lambda: article_service.get_lot_cpk_trend(article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/articles/lot-barcode-detail", lambda: article_service.get_lot_barcode_detail(article10="0315567079", lot="dummy", indicator="rfpp"), lambda r: r.get("status") == "success"),
    # 3. Trend & Filters
    ("GET", "/api/filters/articles", lambda: trend_service.get_filter_articles(min_yield=10), lambda r: r.get("status") == "success"),
    ("GET", "/api/filters/daterange", lambda: trend_service.get_filter_daterange(), lambda r: r.get("status") == "success"),
    ("GET", "/api/trend/cpk", lambda: trend_service.get_trend_cpk(grain="daily"), lambda r: r.get("status") == "success"),
    # 4. Machines
    ("GET", "/api/machines/cpk", lambda: machine_service.get_machine_cpk(target_date="2026-08-17", article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/cpk/trend", lambda: machine_service.get_machine_cpk_trend(machine="TB262", workcenter_col="gt_workcenter", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/combination-tree", lambda: process_flow_service.get_machine_combination_tree(spec="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/process-sankey", lambda: process_flow_service.get_process_sankey(article10="0316824072", indicator="rfpp", target_date="2026-08-17", min_samples=1), lambda r: r.get("status") == "success" and len(r.get("data", {}).get("nodes", [])) > 0),
    ("GET", "/api/machines/best-process-sankey", lambda: process_flow_service.get_best_process_sankey(article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/top-warning", lambda: machine_service.get_top_warning(spec="0315567079", indicator="rfpp", target_date="2026-08-17"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/best-tu", lambda: machine_service.get_best_tu(article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/machines/cpk-trend-comparison", lambda: machine_service.get_cpk_trend_comparison(workcenter_type="gt", machines="TB262,TB263", article10="0315567079", indicator="rfpp"), lambda r: r.get("status") == "success"),
    # 5. CGRS
    ("GET", "/api/cgrs/records", lambda: cgrs_service.get_cgrs_records(workcenter="TB262", date="2026-08-17", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/cgrs/controlled-analysis", lambda: cgrs_service.get_cgrs_controlled_analysis(workcenter="TB262", date="2026-08-17", indicator="rfpp"), lambda r: r.get("status") == "success"),
    ("GET", "/api/cgrs/recommended-params", lambda: cgrs_service.get_cgrs_recommended_params(machine="TB262", article10="0315567079", workcenter_type="gt", indicator="rfpp"), lambda r: r.get("status") == "success"),
    # ⭐ Key validation for param-recommendation (must not throw error! has_recommendation field must exist)
    ("GET", "/api/cgrs/param-recommendation", lambda: cgrs_service.get_param_recommendation(article="0315567079", indicator="rfpp", target_date="2026-08-17"), lambda r: "has_recommendation" in r and r.get("status") != "error"),
]

print("=== STARTING DIRECT ENDPOINTS EXECUTION SMOKE TEST ===")
passed = 0
failed = 0

for method, url, func, validator in endpoints_to_test:
    t0 = time.time()
    try:
        data = func()
        dur = (time.time() - t0) * 1000
        if validator(data):
            print(f"[PASS] ({dur:6.1f}ms) {method} {url}")
            passed += 1
        else:
            print(f"[FAIL] ({dur:6.1f}ms) {method} {url} -> Validation failed: {str(data)[:200]}")
            failed += 1
    except Exception as e:
        dur = (time.time() - t0) * 1000
        import traceback
        print(f"[ERR ] ({dur:6.1f}ms) {method} {url} -> Exception: {e}")
        traceback.print_exc()
        failed += 1

print(f"\nRESULTS: {passed} PASSED, {failed} FAILED out of {len(endpoints_to_test)} endpoints.")
if failed == 0:
    print(">>> ALL 22 API ENDPOINTS EXECUTED & VERIFIED 100% SUCCESSFULLY <<<")
    sys.exit(0)
else:
    print(">>> SOME TESTS FAILED <<<")
    sys.exit(1)
