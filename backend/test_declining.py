import duckdb
from datetime import datetime, timedelta
import numpy as np

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

study_from = '2026-07-13'
study_to = '2026-07-13'
indicator = 'rfh1'

target_dt = datetime.strptime(study_from, "%Y-%m-%d")
s_from = (target_dt - timedelta(days=15)).strftime("%Y-%m-%d")
s_to = study_to

sql = """
    SELECT
        ct_shiftdate::DATE AS time_period,
        article10,
        COUNT(*) AS sample_size,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_rfh1,
        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_rfh1,
        COALESCE(ANY_VALUE(standard_rfpp), 
                 CASE ANY_VALUE("group") 
                     WHEN 'GROUP 1'  THEN 10.5 
                     WHEN 'GROUP 2A' THEN 11.5 
                     WHEN 'GROUP 2B' THEN 12.5 
                     WHEN 'GROUP 3'  THEN 12.5 
                 END) * 10.0 AS usl_rfpp,
        COALESCE(ANY_VALUE(standard_rfh1), 
                 CASE ANY_VALUE("group") 
                     WHEN 'GROUP 1'  THEN 7.5 
                     WHEN 'GROUP 2A' THEN 8.5 
                     WHEN 'GROUP 2B' THEN 9.0 
                     WHEN 'GROUP 3'  THEN 9.5 
                 END) * 10.0 AS usl_rfh1
    FROM clean_yield
    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
      AND ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE
    GROUP BY 1, 2
    HAVING COUNT(*) >= 10
"""

rows = db_conn.execute(sql, [s_from, s_to]).fetchall()
col_names = ["time_period", "article10", "sample_size", "avg_rfpp", "std_rfpp", "avg_rfh1", "std_rfh1", "usl_rfpp", "usl_rfh1"]
parsed_rows = [dict(zip(col_names, r)) for r in rows]

article_data = {}
for r in parsed_rows:
    art = r['article10']
    if art not in article_data:
        article_data[art] = []
    article_data[art].append(r)

results_declining = []
results_declining_below_mean = []

for art, day_list in article_data.items():
    day_list.sort(key=lambda x: x['time_period'])
    cpk_list = []
    dates_list = []
    for d in day_list:
        avg_val = d['avg_rfh1']
        std_val = d['std_rfh1']
        usl_val = d['usl_rfh1']
        
        if std_val is not None and std_val > 1e-6:
            cpk = (usl_val - avg_val) / (3.0 * std_val)
            if cpk is not None and not (np.isnan(cpk) or np.isinf(cpk)):
                cpk_list.append(cpk)
                dates_list.append(d['time_period'])
    
    if not cpk_list or str(dates_list[-1]) != '2026-07-13':
        continue
        
    mean_cpk = float(np.mean(cpk_list))
    diff = 0.0
    is_declining = False
    if len(cpk_list) >= 2:
        diff = cpk_list[-1] - cpk_list[-2]
        if diff < 0:
            is_declining = True
            
    is_below_mean = cpk_list[-1] < mean_cpk
    
    if is_declining:
        results_declining.append(art)
    if is_declining and is_below_mean:
        results_declining_below_mean.append(art)

print("Only declining count:", len(results_declining))
print("Only declining + below mean count:", len(results_declining_below_mean))
