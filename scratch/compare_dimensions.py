import duckdb

con = duckdb.connect()
p = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{p}')")

print("=== Comparison of dates 7.10 - 7.16 by different time dimensions ===")
for col in ['tu_first_shift_date', 'gt_loc_timestamp', 'ct_loc_timestamp']:
    print(f"\n--- Dimension: {col} ---")
    if col == 'tu_first_shift_date':
        date_expr = "tu_first_shift_date"
    else:
        date_expr = f"STRFTIME(TRY_CAST({col} AS TIMESTAMP), '%Y-%m-%d')"
    
    df = con.execute(f"""
        SELECT 
            {date_expr} as d,
            COUNT(*) as n,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as mean_rfpp,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp
        FROM cy
        WHERE {date_expr} >= '2026-07-09' AND {date_expr} <= '2026-07-16'
        GROUP BY d
        ORDER BY d ASC
    """).df()
    print(df.to_string())
