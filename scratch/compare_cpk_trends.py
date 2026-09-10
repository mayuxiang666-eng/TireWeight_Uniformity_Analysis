import duckdb

con = duckdb.connect()
p = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{p}')")

# If tu_first_loc_timestamp is tu_first_shift_date:
con.execute("ALTER TABLE cy ADD COLUMN tu_first_loc_timestamp VARCHAR")
con.execute("UPDATE cy SET tu_first_loc_timestamp = tu_first_shift_date")

print("=== 1. Daily CPK trend by tu_first_loc_timestamp (TU 时间) ===")
df_tu = con.execute("""
    WITH spec_daily_stats AS (
        SELECT
            TRY_CAST(tu_first_loc_timestamp AS DATE) AS time_period,
            "group",
            article10,
            COUNT(*) AS sample_size,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
            COALESCE(ANY_VALUE(standard_rfpp), 
                     CASE "group" 
                         WHEN 'GROUP 1'  THEN 10.5 
                         WHEN 'GROUP 2A' THEN 11.5 
                         WHEN 'GROUP 2B' THEN 12.5 
                         WHEN 'GROUP 3'  THEN 12.5 
                     END) * 10.0 AS usl_rfpp
        FROM cy
        WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
          AND tu_first_loc_timestamp IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING COUNT(*) >= 10
    ),
    spec_cpk AS (
        SELECT
            time_period,
            sample_size,
            CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp
        FROM spec_daily_stats
    )
    SELECT
        time_period,
        SUM(sample_size) AS total_n,
        ROUND(SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0), 3) AS cpk
    FROM spec_cpk
    GROUP BY 1
    ORDER BY 1
""").df()
print(df_tu.head(10))

print("\n=== 2. Daily CPK trend by gt_loc_timestamp (GT 成型时间) ===")
df_gt = con.execute("""
    WITH spec_daily_stats AS (
        SELECT
            TRY_CAST(TRY_CAST(gt_loc_timestamp AS TIMESTAMP) AS DATE) AS time_period,
            "group",
            article10,
            COUNT(*) AS sample_size,
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) AS avg_rfpp,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) AS std_rfpp,
            COALESCE(ANY_VALUE(standard_rfpp), 
                     CASE "group" 
                         WHEN 'GROUP 1'  THEN 10.5 
                         WHEN 'GROUP 2A' THEN 11.5 
                         WHEN 'GROUP 2B' THEN 12.5 
                         WHEN 'GROUP 3'  THEN 12.5 
                     END) * 10.0 AS usl_rfpp
        FROM cy
        WHERE "group" IS NOT NULL AND "group" != 'None' AND "group" != ''
          AND gt_loc_timestamp IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING COUNT(*) >= 10
    ),
    spec_cpk AS (
        SELECT
            time_period,
            sample_size,
            CASE WHEN std_rfpp > 1e-6 THEN (usl_rfpp - avg_rfpp) / (3.0 * std_rfpp) ELSE NULL END AS cpk_rfpp
        FROM spec_daily_stats
    )
    SELECT
        time_period,
        SUM(sample_size) AS total_n,
        ROUND(SUM(cpk_rfpp * sample_size) / NULLIF(SUM(CASE WHEN cpk_rfpp IS NOT NULL THEN sample_size ELSE 0 END), 0), 3) AS cpk
    FROM spec_cpk
    GROUP BY 1
    ORDER BY 1
""").df()
print(df_gt.head(10))
