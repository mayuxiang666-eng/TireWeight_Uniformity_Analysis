import duckdb

con = duckdb.connect()
cgrs_path = "untitled1_v2/backend/data/CGRS.csv"
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

res = con.execute("SELECT Workcenter, TechOffsetLocalDate, match_date, event_timestamp FROM cgrs_records WHERE event_timestamp IS NOT NULL LIMIT 5").df()
print(res)

null_count = con.execute("SELECT COUNT(*) FROM cgrs_records WHERE TechOffsetLocalDate IS NOT NULL AND event_timestamp IS NULL").fetchone()[0]
print(f"Null event_timestamp count: {null_count}")
