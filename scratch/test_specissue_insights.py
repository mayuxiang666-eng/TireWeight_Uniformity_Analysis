import duckdb
import numpy as np
import pandas as pd

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

b_from = "2026-06-13"
b_to = "2026-06-28"
s_from = "2026-06-29"
s_to = "2026-07-13"

sql = """
SELECT
    article10,
    specissue,
    COUNT(*) AS total,
    SUM(CAST(grade_anomaly AS INT)) AS anomalies,
    AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
    STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
    COALESCE(ANY_VALUE(standard_rfpp), 
             CASE "group" 
                 WHEN 'GROUP 1'  THEN 10.5 
                 WHEN 'GROUP 2A' THEN 11.5 
                 WHEN 'GROUP 2B' THEN 12.5 
                 WHEN 'GROUP 3'  THEN 12.5 
             END) * 10.0 AS usl_rfpp,
    AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
    STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
    COALESCE(ANY_VALUE(standard_rfh1), 
             CASE "group" 
                 WHEN 'GROUP 1'  THEN 7.5 
                 WHEN 'GROUP 2A' THEN 8.5 
                 WHEN 'GROUP 2B' THEN 9.0 
                 WHEN 'GROUP 3'  THEN 9.5 
             END) * 10.0 AS usl_rfh1,
    MIN(ct_shiftdate::DATE) AS min_date,
    MAX(ct_shiftdate::DATE) AS max_date
FROM clean_yield
WHERE ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE
  AND article10 IS NOT NULL AND specissue IS NOT NULL AND "group" IS NOT NULL
GROUP BY 1, 2, "group"
HAVING total >= 10
"""

rows = db_conn.execute(sql, [b_from, s_to]).df()

# Group by article10
degradations = []
for art, g_data in rows.groupby('article10'):
    if len(g_data) < 2:
        continue
    # Sort by min_date
    g_sorted = g_data.sort_values(by='min_date').to_dict('records')
    
    # Compare consecutive versions
    for i in range(len(g_sorted) - 1):
        v1 = g_sorted[i]
        v2 = g_sorted[i+1]
        
        # Calculate CPK for v1
        cpk_v1_rfpp = (v1['usl_rfpp'] - v1['avg_rfpp']) / (3.0 * v1['std_rfpp']) if v1['std_rfpp'] and v1['std_rfpp'] > 1e-6 else None
        cpk_v1_rfh1 = (v1['usl_rfh1'] - v1['avg_rfh1']) / (3.0 * v1['std_rfh1']) if v1['std_rfh1'] and v1['std_rfh1'] > 1e-6 else None
        cpk_v1 = min(cpk_v1_rfpp, cpk_v1_rfh1) if cpk_v1_rfpp is not None and cpk_v1_rfh1 is not None else (cpk_v1_rfpp or cpk_v1_rfh1)
        
        # Calculate CPK for v2
        cpk_v2_rfpp = (v2['usl_rfpp'] - v2['avg_rfpp']) / (3.0 * v2['std_rfpp']) if v2['std_rfpp'] and v2['std_rfpp'] > 1e-6 else None
        cpk_v2_rfh1 = (v2['usl_rfh1'] - v2['avg_rfh1']) / (3.0 * v2['std_rfh1']) if v2['std_rfh1'] and v2['std_rfh1'] > 1e-6 else None
        cpk_v2 = min(cpk_v2_rfpp, cpk_v2_rfh1) if cpk_v2_rfpp is not None and cpk_v2_rfh1 is not None else (cpk_v2_rfpp or cpk_v2_rfh1)
        
        rate_v1 = (v1['anomalies'] / v1['total']) * 100
        rate_v2 = (v2['anomalies'] / v2['total']) * 100
        
        diff_rate = rate_v2 - rate_v1
        diff_cpk = (cpk_v2 - cpk_v1) if cpk_v2 is not None and cpk_v1 is not None else 0.0
        
        # We define degradation as: anomaly rate increased by > 0.1% OR CPK dropped by > 0.05
        if diff_rate > 0.1 or diff_cpk < -0.05:
            degradations.append({
                "article10": art,
                "v1_ver": v1['specissue'],
                "v2_ver": v2['specissue'],
                "v1_rate": round(rate_v1, 2),
                "v2_rate": round(rate_v2, 2),
                "v1_cpk": round(cpk_v1, 2) if cpk_v1 is not None else None,
                "v2_cpk": round(cpk_v2, 2) if cpk_v2 is not None else None,
                "diff_rate": round(diff_rate, 2),
                "diff_cpk": round(diff_cpk, 2),
                "date_switch": str(v2['min_date'])
            })

print(f"Found {len(degradations)} specissue degradation cases:")
for d in degradations[:15]:
    print(d)
