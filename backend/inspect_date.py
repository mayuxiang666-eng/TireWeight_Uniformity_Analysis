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
is_single_day = True
single_day_str = study_to

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
print("Total rows fetched:", len(rows))

# Parse keys
col_names = ["time_period", "article10", "sample_size", "avg_rfpp", "std_rfpp", "avg_rfh1", "std_rfh1", "usl_rfpp", "usl_rfh1"]
parsed_rows = []
for r in rows:
    parsed_rows.append(dict(zip(col_names, r)))

article_data = {}
for r in parsed_rows:
    art = r['article10']
    if art not in article_data:
        article_data[art] = []
    article_data[art].append(r)

results = []
for art, day_list in article_data.items():
    day_list.sort(key=lambda x: x['time_period'])
    
    cpk_list = []
    dates_list = []
    for d in day_list:
        if indicator == 'rfpp':
            avg_val = d['avg_rfpp']
            std_val = d['std_rfpp']
            usl_val = d['usl_rfpp']
        else:
            avg_val = d['avg_rfh1']
            std_val = d['std_rfh1']
            usl_val = d['usl_rfh1']
        
        if std_val is not None and std_val > 1e-6:
            cpk = (usl_val - avg_val) / (3.0 * std_val)
            if cpk is not None and not (np.isnan(cpk) or np.isinf(cpk)):
                cpk_list.append(cpk)
                dates_list.append(d['time_period'])
    
    if not cpk_list:
        continue
        
    # Check if target date is in dates_list
    target_match = any(str(dt) == single_day_str for dt in dates_list)
    last_date_str = str(dates_list[-1]) if dates_list else "None"
    
    if is_single_day:
        if not dates_list or str(dates_list[-1]) != single_day_str:
            # Print some debug info for a well-known article
            if art == '0312050000':
                print(f"Article {art} fails single day check. dates_list[-1] is {last_date_str}, expected {single_day_str}.")
                print(f"dates_list = {[str(dt) for dt in dates_list]}")
            continue

    mean_cpk = float(np.mean(cpk_list))
    std_cpk = float(np.std(cpk_list, ddof=1)) if len(cpk_list) > 1 else 0.0
    cv = std_cpk / abs(mean_cpk) if mean_cpk != 0 else 0.0
    stable_score = mean_cpk / (1 + cv) if mean_cpk > 0 else 0.0
    
    results.append({
        "article10": art,
        "stable_score": stable_score
    })

print("Total results processed:", len(results))
