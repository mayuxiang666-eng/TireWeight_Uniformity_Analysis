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
            TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
        ) AS event_timestamp
    FROM read_csv_auto('{cgrs_path}', all_varchar=True)
""")

cols = [r[0] for r in con.execute("DESCRIBE clean_yield").fetchall()]
if 'tu_first_loc_timestamp' not in cols and 'tu_first_shift_date' in cols:
    con.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_loc_timestamp VARCHAR")
    con.execute("UPDATE clean_yield SET tu_first_loc_timestamp = COALESCE(gt_loc_timestamp, tu_first_shift_date)")

print("=== 1. CGRS records for TB124/TB224 on 2026-08-10 ===")
cgrs_df = con.execute("""
    SELECT Workcenter, TechOffsetLocalDate, event_timestamp, ProdSpecific2, ParameterLocalName, ParameterName, TechOffsetHistoryValueFrom, TechOffsetHistoryValueTo
    FROM cgrs_records
    WHERE (Workcenter = 'TB124' OR Workcenter = 'TB224')
      AND match_date = DATE '2026-08-10'
""").df()
print(cgrs_df)

print("\n=== 2. Clean yield records for TB224 on spec 0312053000 ===")
all_gt = con.execute("""
    SELECT 
        gt_workcenter,
        article10,
        tu_first_shift_date,
        gt_loc_timestamp,
        TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as tu_time,
        rfppwc_first
    FROM clean_yield
    WHERE (gt_workcenter = 'TB224' OR gt_workcenter = 'TB124' OR gt_workcenter = 'TB24')
      AND article10 = '0312053000'
    ORDER BY tu_time ASC
""").df()
print(f"Total rows for TB224 + 0312053000: {len(all_gt)}")
if len(all_gt) > 0:
    print("Min time:", all_gt['tu_time'].min(), "Max time:", all_gt['tu_time'].max())
    print(all_gt.head(5))
    print(all_gt.tail(5))

print("\n=== 3. Clean yield records for TB224 across ALL specs on 2026-08-10 ===")
all_specs = con.execute("""
    SELECT 
        article10,
        COUNT(*) as cnt,
        MIN(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) as min_t,
        MAX(TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP)) as max_t
    FROM clean_yield
    WHERE (gt_workcenter = 'TB224' OR gt_workcenter = 'TB124' OR gt_workcenter = 'TB24')
      AND tu_first_shift_date::DATE = DATE '2026-08-10'
    GROUP BY article10
""").df()
print(all_specs)

print("\n=== 4. Check if TB224 produced anything after 2026-08-10 09:21 ===")
after_921 = con.execute("""
    SELECT 
        article10,
        TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as tu_t,
        gt_workcenter
    FROM clean_yield
    WHERE (gt_workcenter = 'TB224' OR gt_workcenter = 'TB124' OR gt_workcenter = 'TB24')
      AND TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) >= TIMESTAMP '2026-08-10 09:21:00'
    ORDER BY tu_t ASC
    LIMIT 10
""").df()
print(f"Rows after 9:21 across all specs: {len(after_921)}")
print(after_921)
