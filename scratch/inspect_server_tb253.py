# -*- coding: utf-8 -*-
import duckdb
import os
import pandas as pd
import numpy as np

pq_path = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\backend\data\yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE VIEW cy AS SELECT * FROM read_parquet('{pq_path}')")

target_date = "2026-09-07"
article = "0315997056"
time_col = "tu_first_loc_timestamp"
date_col = f"CAST((TRY_CAST({time_col} AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE)"

print(f"=== Querying {target_date} for spec {article} ===")

# GT Machines
df_gt = con.execute(f"""
    SELECT 
        gt_workcenter,
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) * 10.0 as usl
    FROM cy
    WHERE {date_col} = '{target_date}'::DATE
      AND article10 = '{article}'
      AND rfppwc_first IS NOT NULL
    GROUP BY gt_workcenter
    ORDER BY tires DESC
""").fetchdf()
print("\n--- GT Machines ---")
print(df_gt)

# CT Machines
df_ct = con.execute(f"""
    SELECT 
        ct_workcenter,
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) * 10.0 as usl
    FROM cy
    WHERE {date_col} = '{target_date}'::DATE
      AND article10 = '{article}'
      AND rfppwc_first IS NOT NULL
    GROUP BY ct_workcenter
    ORDER BY tires DESC
""").fetchdf()
print("\n--- CT Machines ---")
print(df_ct)

# TU Machines
df_tu = con.execute(f"""
    SELECT 
        tu_workcenter,
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) * 10.0 as usl
    FROM cy
    WHERE {date_col} = '{target_date}'::DATE
      AND article10 = '{article}'
      AND rfppwc_first IS NOT NULL
    GROUP BY tu_workcenter
    ORDER BY tires DESC
""").fetchdf()
print("\n--- TU Machines ---")
print(df_tu)

# Overall Spec metrics
df_all = con.execute(f"""
    SELECT 
        COUNT(*) as tires,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        ANY_VALUE(standard_rfpp) * 10.0 as usl
    FROM cy
    WHERE {date_col} = '{target_date}'::DATE
      AND article10 = '{article}'
      AND rfppwc_first IS NOT NULL
""").fetchdf()
print("\n--- Overall Spec ---")
print(df_all)
