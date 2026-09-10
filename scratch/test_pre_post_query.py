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
    # Check if gt_loc_timestamp exists, if so can we use full timestamp or date?
    con.execute("UPDATE clean_yield SET tu_first_loc_timestamp = COALESCE(gt_loc_timestamp, tu_first_shift_date)")

print("Sample clean_yield rows:")
df_sample = con.execute("SELECT gt_workcenter, article10, tu_first_loc_timestamp, gt_loc_timestamp, rfppwc_first FROM clean_yield WHERE gt_workcenter IS NOT NULL LIMIT 5").df()
print(df_sample)

# Let's find an actual CGRS event and query 50 rows before and 50 rows after!
# First let's find matching machines and articles
cgrs_events = con.execute("""
    SELECT DISTINCT 
        Workcenter, 
        event_timestamp, 
        ProdSpecific2, 
        match_date 
    FROM cgrs_records 
    ORDER BY event_timestamp DESC 
    LIMIT 10
""").df()
print("\nRecent CGRS Events:")
print(cgrs_events)

for _, event in cgrs_events.iterrows():
    wc = event['Workcenter']
    ts = event['event_timestamp']
    art = event['ProdSpecific2']
    dt = event['match_date']
    
    # compatible machines: e.g. TB122 -> TB222, TB22, TB122
    candidates = [wc]
    if wc.startswith("TB1"):
        candidates.extend(["TB2" + wc[3:], "TB" + wc[3:]])
    elif wc.startswith("TB2"):
        candidates.extend(["TB1" + wc[3:], "TB" + wc[3:]])
    
    placeholders = ",".join(["?"] * len(candidates))
    
    # Query before 50
    sql_before = f"""
        SELECT 
            gt_workcenter,
            article10,
            TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as t_stamp,
            TRY_CAST(rfppwc_first AS DOUBLE) as val
        FROM clean_yield
        WHERE gt_workcenter IN ({placeholders})
          AND TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) < ?::TIMESTAMP
          AND rfppwc_first IS NOT NULL
        ORDER BY TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) DESC
        LIMIT 50
    """
    rows_before = con.execute(sql_before, candidates + [ts]).df()
    
    # Query after 50
    sql_after = f"""
        SELECT 
            gt_workcenter,
            article10,
            TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) as t_stamp,
            TRY_CAST(rfppwc_first AS DOUBLE) as val
        FROM clean_yield
        WHERE gt_workcenter IN ({placeholders})
          AND TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) >= ?::TIMESTAMP
          AND rfppwc_first IS NOT NULL
        ORDER BY TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) ASC
        LIMIT 50
    """
    rows_after = con.execute(sql_after, candidates + [ts]).df()
    
    print(f"\nMatch test for CGRS {wc} ({candidates}) at {ts} on date {dt} (Spec={art}):")
    print(f"  Rows before count: {len(rows_before)}, Rows after count: {len(rows_after)}")
    if len(rows_before) > 0 and len(rows_after) > 0:
        print("  Found both before and after data!")
        print("  Sample before:", rows_before[['gt_workcenter', 'article10', 't_stamp', 'val']].head(2))
        print("  Sample after:", rows_after[['gt_workcenter', 'article10', 't_stamp', 'val']].head(2))
        break
