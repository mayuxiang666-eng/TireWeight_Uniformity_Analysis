# -*- coding: utf-8 -*-
import duckdb
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = r"d:\Ava\untitled1\untitled1_v2"
sys.path.insert(0, BASE_DIR)

from backend.main import (
    get_top_warning_machines,
    get_spec_warning_machines_detailed,
    calc_cpk,
    qry,
    db_conn
)

# Switch db_conn to Server_Backend parquet so it has 2026-09-07
pq_path = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\backend\data\yield_flat_table_joined_100_cleaned.parquet"
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{pq_path}')")

target_date = "2026-09-07"
article = "0315997056"
indicator = "rfpp"

print("=== Running get_top_warning_machines ===")
top_machines = get_top_warning_machines(
    article10=article,
    target_date=target_date,
    indicator=indicator,
    n=10
)
for m in top_machines:
    print(m)

print("\n=== Running get_spec_warning_machines_detailed ===")
spec_item = {
    "article10": article,
    "stable_score": -0.5,
    "single_cpk": 1.15,
    "avg_cpk": 1.30,
    "sample_size": 47,
}
detailed = get_spec_warning_machines_detailed(
    item=spec_item,
    indicator=indicator,
    target_date=target_date,
    min_samples=5
)
for d in detailed:
    print("Machine:", d.get("workcenter"), 
          "| Process:", d.get("process"),
          "| Rank:", d.get("rank"),
          "| Level:", d.get("warning_level"),
          "| CPK change:", d.get("cpk_pct_change"),
          "| Hist CPK:", d.get("hist_cpk"),
          "| Today CPK:", d.get("today_cpk"),
          "| Reason:", d.get("reason"),
          "| Has Rec:", d.get("has_recommendation"))
