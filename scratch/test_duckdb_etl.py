import os
import time
import datetime
import duckdb

data_dir = r"d:\Ava\untitled1\untitled1_v2\backend\data"
base_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
cleaned_parquet = os.path.join(data_dir, "yield_flat_table_joined_100_cleaned.parquet")
recipes_csv = os.path.join(data_dir, "Recipes.csv")

t0 = time.time()
con = duckdb.connect()
print(f"Connected to DuckDB in {time.time() - t0:.2f}s")

# Test 1: Count rows in base_parquet
t1 = time.time()
row_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{base_parquet}')").fetchone()[0]
print(f"Base parquet row count: {row_cnt:,} in {time.time() - t1:.2f}s")

# Test 4: Complete DuckDB clean_data pipeline
t3 = time.time()
test_cleaned_out = os.path.join(data_dir, "test_cleaned.parquet.tmp")

con.execute(f"""
    CREATE OR REPLACE TABLE recipes_rf AS
    SELECT 
        LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') as art10_clean,
        TRY_CAST(RFPP_T1 AS DOUBLE) / 10.0 as rfpp_val,
        TRY_CAST(RFH1_T1 AS DOUBLE) / 10.0 as rfh1_val,
        TRY_CAST(UPDATE_LIMIT AS TIMESTAMP) as update_limit_dt
    FROM read_csv('{recipes_csv}', header=true, all_varchar=true)
    WHERE TRY_CAST(INFLATION AS BIGINT) != 200000
    QUALIFY ROW_NUMBER() OVER (PARTITION BY LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') ORDER BY ART10) = 1;
""")

con.execute(f"""
    CREATE OR REPLACE TABLE recipes_cony AS
    SELECT 
        LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') as art10_clean,
        TRY_CAST(CONU_T1 AS DOUBLE) as conu_val,
        TRY_CAST(CONL_T1 AS DOUBLE) as conl_val
    FROM read_csv('{recipes_csv}', header=true, all_varchar=true)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') ORDER BY TRY_CAST(RELEASE_TIME AS TIMESTAMP) DESC NULLS LAST) = 1;
""")

existing_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{base_parquet}') LIMIT 1").fetchall()]
drop_candidates = [
    "articleno", "articleno_7", "articlevariant", "branddesignation", "loadindexsingle", "speedsymbol", "ssr",
    "yt_workcenter", "ssr_insert_bead_cushion_workcenter", "ssr_insert_bead_cushion_lot",
    "bead_reinforcement_workcenter", "bead_reinforcement_lot", "second_ply_lot", "second_ply_workcenter",
    "standard_rfpp", "standard_rfh1"
]
cols_to_exclude = [c for c in drop_candidates if c in existing_cols]
exclude_str = f"EXCLUDE ({', '.join(cols_to_exclude)})" if cols_to_exclude else ""

con.execute(f"""
    COPY (
        SELECT 
            t.* {exclude_str},
            CASE 
                WHEN rf.art10_clean IS NOT NULL 
                     AND COALESCE(TRY_CAST(t.tu_first_shift_date AS TIMESTAMP), TRY_CAST(t.ct_loc_timestamp AS TIMESTAMP), TRY_CAST(t.gt_loc_timestamp AS TIMESTAMP)) >= rf.update_limit_dt 
                THEN rf.rfpp_val
                ELSE t.standard_rfpp 
            END AS standard_rfpp,
            CASE 
                WHEN rf.art10_clean IS NOT NULL 
                     AND COALESCE(TRY_CAST(t.tu_first_shift_date AS TIMESTAMP), TRY_CAST(t.ct_loc_timestamp AS TIMESTAMP), TRY_CAST(t.gt_loc_timestamp AS TIMESTAMP)) >= rf.update_limit_dt 
                THEN rf.rfh1_val
                ELSE t.standard_rfh1 
            END AS standard_rfh1,
            cy.conu_val AS conny_usl,
            cy.conl_val AS conny_lsl,
            0 AS rfpp_anomaly,
            0 AS rfh1_anomaly,
            0 AS grade_anomaly
        FROM read_parquet('{base_parquet}') t
        LEFT JOIN recipes_rf rf ON LPAD(TRIM(CAST(t.article10 AS VARCHAR)), 10, '0') = rf.art10_clean
        LEFT JOIN recipes_cony cy ON LPAD(TRIM(CAST(t.article10 AS VARCHAR)), 10, '0') = cy.art10_clean
        WHERE t.article10 IS NOT NULL 
          AND TRIM(CAST(t.article10 AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NULL')
    ) TO '{test_cleaned_out}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY')
""")

print(f"Cleaned dataset exported in {time.time() - t3:.2f}s")
if os.path.exists(test_cleaned_out):
    sz = os.path.getsize(test_cleaned_out) / (1024 * 1024)
    row_cleaned = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT article10) FROM read_parquet('{test_cleaned_out}')").fetchall()
    print(f"Cleaned rows: {row_cleaned[0][0]:,}, distinct articles: {row_cleaned[0][1]}, size: {sz:.2f} MB")
    os.remove(test_cleaned_out)


