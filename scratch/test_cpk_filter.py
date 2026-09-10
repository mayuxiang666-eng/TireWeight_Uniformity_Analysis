import duckdb

con = duckdb.connect()
p = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{p}')")

print("=== Warning articles on 2026-08-10 for RFPP with min_samples >= 30 and CPK < 0.9 ===")
rows = con.execute("""
    WITH spec_stats AS (
        SELECT 
            article10,
            COUNT(*) as n,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_v,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_v,
            COALESCE(ANY_VALUE(standard_rfpp),
                     CASE ANY_VALUE("group")
                         WHEN 'GROUP 1'  THEN 10.5
                         WHEN 'GROUP 2A' THEN 11.5
                         WHEN 'GROUP 2B' THEN 12.5
                         WHEN 'GROUP 3'  THEN 12.5
                     END) * 10.0 AS usl_rfpp
        FROM cy
        WHERE tu_first_shift_date = '2026-08-10'
          AND rfppwc_first IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) >= 30
    )
    SELECT 
        article10,
        n,
        avg_v,
        std_v,
        usl_rfpp,
        ROUND((usl_rfpp - avg_v) / (3.0 * std_v), 3) as cpk
    FROM spec_stats
    WHERE (usl_rfpp - avg_v) / (3.0 * std_v) < 0.9
    ORDER BY cpk ASC
""").df()
print(rows.to_string())
