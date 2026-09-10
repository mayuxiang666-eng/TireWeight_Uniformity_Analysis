import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE clean_yield AS SELECT * FROM read_parquet('{parquet_path}')")

print("=== 1. Date counts in clean_yield by tu_first_shift_date ===")
df_dates = con.execute("""
    SELECT 
        tu_first_shift_date,
        COUNT(*) as total_records,
        COUNT(rfppwc_first) as rfpp_count,
        AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_rfpp,
        STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
        MIN(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as min_gt_t,
        MAX(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as max_gt_t
    FROM clean_yield
    GROUP BY tu_first_shift_date
    ORDER BY tu_first_shift_date ASC
""").df()
print(df_dates.to_string())

print("\n=== 2. Check gt_loc_timestamp date distribution ===")
df_gt_dates = con.execute("""
    SELECT 
        STRFTIME(TRY_CAST(gt_loc_timestamp AS TIMESTAMP), '%Y-%m-%d') as gt_date,
        COUNT(*) as total_records,
        MIN(tu_first_shift_date) as min_tu_shift,
        MAX(tu_first_shift_date) as max_tu_shift
    FROM clean_yield
    GROUP BY gt_date
    ORDER BY gt_date ASC
""").df()
print(df_gt_dates.head(20).to_string())

print("\n=== 3. Inspect sample rows for 2026-07-10 to 2026-07-15 ===")
sample_july = con.execute("""
    SELECT 
        barcode,
        article10,
        tu_first_shift_date,
        gt_loc_timestamp,
        ct_loc_timestamp,
        tu_first_workcenter,
        gt_workcenter,
        rfppwc_first,
        rfh1wc_first,
        cony_first
    FROM clean_yield
    WHERE tu_first_shift_date >= '2026-07-10' AND tu_first_shift_date <= '2026-07-15'
    LIMIT 15
""").df()
print(sample_july.to_string())
