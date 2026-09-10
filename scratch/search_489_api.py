import duckdb
import pandas as pd
import json

# Let's inspect backend/main.py APIs and their outputs for 2026-08-17
p_clean = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\data\yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{p_clean}')")

def qry(sql, params=None):
    cursor = con.cursor()
    if params:
        rel = cursor.execute(sql, params)
    else:
        rel = cursor.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    cursor.close()
    return [dict(zip(cols, r)) for r in rows]

print("=" * 80)
print("CHECKING ALL BACKEND QUERIES FOR 2026-08-17")
print("=" * 80)

# Check all possible where clauses or aggregations that equal 489
# 1. Check sum of samples for warning-cpk for various indicators
for ind in ['rfpp', 'rfh1', 'cony', 'weight']:
    for min_s in [1, 5, 10, 20, 30, 50]:
        for phase in ['all', 'p3', 'p4']:
            phase_cond = ""
            if phase == "p3":
                phase_cond = " AND (ct_shop IS NULL OR UPPER(CAST(ct_shop AS VARCHAR)) NOT LIKE '%P4%')"
            elif phase == "p4":
                phase_cond = " AND (ct_shop IS NOT NULL AND UPPER(CAST(ct_shop AS VARCHAR)) LIKE '%P4%')"
            
            if ind == 'weight':
                sql = f"""
                    SELECT COUNT(*) as cnt, SUM(sample_size) as sum_samples
                    FROM (
                        SELECT article10, COUNT(*) as sample_size
                        FROM clean_yield
                        WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
                          AND tire_weight_actual_first IS NOT NULL AND TRY_CAST(tire_weight_actual_first AS DOUBLE) > 0.0
                          AND tire_weight_target_first IS NOT NULL AND TRY_CAST(tire_weight_target_first AS DOUBLE) > 0.0
                          {phase_cond}
                        GROUP BY 1
                        HAVING COUNT(*) >= {min_s}
                    )
                """
            else:
                col = "rfppwc_first" if ind == "rfpp" else ("rfh1wc_first" if ind == "rfh1" else "cony_first")
                val_cond = f"{col} IS NOT NULL AND TRY_CAST({col} AS DOUBLE) > 0" if ind != "cony" else f"{col} IS NOT NULL"
                sql = f"""
                    SELECT COUNT(*) as cnt, SUM(sample_size) as sum_samples
                    FROM (
                        SELECT article10, COUNT(*) as sample_size
                        FROM clean_yield
                        WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
                          AND {val_cond}
                          {phase_cond}
                        GROUP BY 1
                        HAVING COUNT(*) >= {min_s}
                    )
                """
            res = qry(sql)[0]
            if res['cnt'] == 489 or res['sum_samples'] == 489:
                print(f"MATCH FOUND! Indicator={ind}, min_samples={min_s}, phase={phase}: {res}")

# 2. Check machines endpoint
wc_cols = [
    "tread_workcenter", "wound_cap_ply1_workcenter", "wound_cap_ply2_workcenter",
    "first_breaker_workcenter", "second_breaker_workcenter", "sidewall_workcenter",
    "bead_workcenter", "inner_liner_workcenter", "first_ply_workcenter",
    "tb_first_workcenter", "gt_workcenter", "ct_workcenter", "tu_first_workcenter"
]

for wc in wc_cols:
    cnt = qry(f"SELECT COUNT(DISTINCT {wc}) as n FROM clean_yield WHERE tu_first_shift_date::DATE = DATE '2026-08-17'")[0]['n']
    valid_rows = qry(f"SELECT COUNT(*) as n FROM clean_yield WHERE tu_first_shift_date::DATE = DATE '2026-08-17' AND {wc} IS NOT NULL AND TRIM(CAST({wc} AS VARCHAR)) NOT IN ('', 'None', 'nan')")[0]['n']
    if cnt == 489 or valid_rows == 489:
        print(f"MATCH in workcenter {wc}: distinct={cnt}, valid_rows={valid_rows}")

# 3. Check combinations of machines or paths
# 4. Check barcodes
distinct_barcodes = qry("SELECT COUNT(DISTINCT barcode) as n FROM clean_yield WHERE tu_first_shift_date::DATE = DATE '2026-08-17'")[0]['n']
print(f"Distinct barcodes on 2026-08-17: {distinct_barcodes}")

# 5. Check if there are duplicate barcodes on 2026-08-17
dup_barcodes = qry("""
    SELECT COUNT(*) as n FROM (
        SELECT barcode, COUNT(*) as c
        FROM clean_yield
        WHERE tu_first_shift_date::DATE = DATE '2026-08-17'
        GROUP BY barcode
        HAVING c > 1
    )
""")[0]['n']
print(f"Duplicate barcodes on 2026-08-17: {dup_barcodes}")

# 6. Check CGRS records or other tables
print("\n--- Check other conditions on 2026-08-17 ---")
# Let's test ANY subset where count is 489
# Check if any single article has 489? No, max was 33.
# Check combinations of dates / time ranges:
for h in range(1, 24):
    cnt = qry(f"""
        SELECT COUNT(*) as n FROM clean_yield 
        WHERE TRY_CAST(ct_loc_timestamp AS DATE) = DATE '2026-08-17' 
          AND EXTRACT(hour FROM TRY_CAST(ct_loc_timestamp AS TIMESTAMP)) < {h}
    """)[0]['n']
    if cnt == 489:
        print(f"MATCH: CT timestamp before hour {h}: {cnt}")

