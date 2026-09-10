import duckdb
import numpy as np

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE clean_yield AS SELECT * FROM read_parquet('{parquet_path}')")
con.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_loc_timestamp VARCHAR")
con.execute("UPDATE clean_yield SET tu_first_loc_timestamp = tu_first_shift_date")

article = "0312053000"
target_date = "2026-08-10"
indicator = "rfpp"
time_col = "tu_first_loc_timestamp"
date_col = f"TRY_CAST(TRY_CAST({time_col} AS TIMESTAMP) AS DATE)"

sql = f"""
    SELECT 
        barcode,
        TRY_CAST(rfppwc_first AS DOUBLE) AS val,
        COALESCE(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) AS prod_time,
        gt_workcenter,
        tu_first_workcenter,
        "group",
        standard_rfpp,
        COALESCE(TRY_CAST(standard_rfpp AS DOUBLE), 
                 CASE "group" 
                     WHEN 'GROUP 1'  THEN 10.5 
                     WHEN 'GROUP 2A' THEN 11.5 
                     WHEN 'GROUP 2B' THEN 12.5 
                     WHEN 'GROUP 3'  THEN 12.5 
                 END) * 10.0 AS usl_rfpp
    FROM clean_yield
    WHERE {date_col} = ?::DATE
      AND article10 = ?
      AND rfppwc_first IS NOT NULL
    ORDER BY prod_time ASC, barcode ASC
"""

rows = con.execute(sql, [target_date, article]).df()
print(f"Total rows retrieved: {len(rows)}")
print(rows.head(5))

vals = rows['val'].dropna().values
usl = rows['usl_rfpp'].dropna().values[0] if len(rows['usl_rfpp'].dropna()) > 0 else 105.0
mean_v = float(np.mean(vals))
std_v = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
out_of_spec = int(np.sum(vals > usl))
out_rate = round(out_of_spec / len(vals) * 100, 2)
cpk = (usl - mean_v) / (3.0 * std_v) if std_v > 1e-6 else 1.33

print("\nSummary:")
print(f"  N = {len(vals)}, Mean = {mean_v:.3f}, Std = {std_v:.3f}, USL = {usl}, OutOfSpec = {out_of_spec} ({out_rate}%), CPK = {cpk:.3f}")
