import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
cgrs_path = "untitled1_v2/backend/data/CGRS.csv"

con.execute(f"CREATE TABLE clean_yield AS SELECT * FROM read_parquet('{parquet_path}')")
con.execute(f"""
    CREATE OR REPLACE TABLE cgrs_records AS 
    SELECT 
        *,
        COALESCE(
            TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
            TRY_CAST(SPLIT_PART(TechOffsetLocalDate, ' ', 1) AS DATE)
        ) AS match_date,
        COALESCE(
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y-%m-%d %H:%M:%S') AS TIMESTAMP),
            TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
        ) AS event_timestamp
    FROM read_csv_auto('{cgrs_path}', all_varchar=True)
""")

print("=== 1. CGRS records for TB133 / TB233 on 2026-08-10 ===")
cgrs_df = con.execute("""
    SELECT 
        Workcenter,
        TechOffsetLocalDate,
        event_timestamp,
        ProdSpecific2,
        ParameterLocalName,
        TechOffsetHistoryValueFrom,
        TechOffsetHistoryValueTo
    FROM cgrs_records
    WHERE (Workcenter = 'TB133' OR Workcenter = 'TB233')
      AND match_date = DATE '2026-08-10'
    ORDER BY event_timestamp ASC
""").df()
print(cgrs_df.to_string())

print("\n=== 2. All production records for TB233 on spec 0312053000 across ALL dates ===")
gt_spec_df = con.execute("""
    SELECT 
        gt_workcenter,
        article10,
        tu_first_shift_date,
        TRY_CAST(gt_loc_timestamp AS TIMESTAMP) as gt_time,
        rfppwc_first
    FROM clean_yield
    WHERE (gt_workcenter = 'TB233' OR gt_workcenter = 'TB133' OR gt_workcenter = 'TB33')
      AND article10 = '0312053000'
    ORDER BY gt_time ASC
""").df()
print(f"Total rows for TB233 + 0312053000: {len(gt_spec_df)}")
if len(gt_spec_df) > 0:
    print(gt_spec_df.to_string())

print("\n=== 3. What specs was TB233 producing on 2026-08-09 and 2026-08-10 before 02:36? ===")
prev_prod = con.execute("""
    SELECT 
        article10,
        COUNT(*) as cnt,
        MIN(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as min_t,
        MAX(TRY_CAST(gt_loc_timestamp AS TIMESTAMP)) as max_t
    FROM clean_yield
    WHERE (gt_workcenter = 'TB233' OR gt_workcenter = 'TB133' OR gt_workcenter = 'TB33')
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) >= TIMESTAMP '2026-08-08 00:00:00'
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) <= TIMESTAMP '2026-08-10 03:00:00'
    GROUP BY article10
    ORDER BY min_t ASC
""").df()
print(prev_prod.to_string())
