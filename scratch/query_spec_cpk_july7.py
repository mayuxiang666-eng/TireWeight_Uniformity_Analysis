import duckdb
import numpy as np

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

target_date = '2026-07-07'
article10 = '0359791000'
indicator = 'rfh1'

# Get 15 days ending at target_date
import datetime
target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
s_from = (target_dt - datetime.timedelta(days=15)).strftime("%Y-%m-%d")

sql = f"""
    SELECT
        ct_shiftdate::DATE AS time_period,
        COUNT(*) AS sample_size,
        AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) AS avg_val,
        STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) AS std_val,
        COALESCE(standard_rfh1, 
                 CASE "group" 
                     WHEN 'GROUP 1'  THEN 7.5 
                     WHEN 'GROUP 2A' THEN 8.5 
                     WHEN 'GROUP 2B' THEN 9.0 
                     WHEN 'GROUP 3'  THEN 9.5 
                 END) * 10.0 AS usl_val
    FROM clean_yield
    WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
      AND ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE
      AND article10 = ?
    GROUP BY time_period, article10, usl_val, "group"
    ORDER BY time_period
"""

rows = con.execute(sql, [s_from, target_date, article10]).fetchall()

cpk_list = []
dates_list = []
for r in rows:
    dt, sz, avg, std, usl = r
    if std is not None and std > 1e-6:
        cpk = (usl - avg) / (3.0 * std)
        cpk_list.append(cpk)
        dates_list.append(str(dt))
        print(f"Date: {dt}, size: {sz}, avg: {avg:.4f}, std: {std:.4f}, usl: {usl:.4f}, cpk: {cpk:.4f}")

mean_cpk = np.mean(cpk_list)
std_cpk = np.std(cpk_list, ddof=1) if len(cpk_list) > 1 else 0.0
threshold = mean_cpk - std_cpk
daily_cpk = cpk_list[-1]

print(f"\nSummary:")
print(f"  Historical mean (15 days): {mean_cpk:.4f}")
print(f"  Historical std (15 days): {std_cpk:.4f}")
print(f"  Threshold (mean - std): {threshold:.4f}")
print(f"  Daily CPK on {target_date}: {daily_cpk:.4f}")
print(f"  Is daily CPK < threshold? {daily_cpk < threshold}")
