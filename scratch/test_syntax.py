import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

col = 'ct_workcenter'
indicator_col = 'rfh1wc_first'
article10 = '0315626000'
target_date = '2026-07-07'
min_samples = 2

sql = f"""
  (
    WITH active_machines AS (
        SELECT 
            CAST({col} AS VARCHAR) AS machine,
            COUNT(*) AS spec_n
        FROM clean_yield
        WHERE {col} IS NOT NULL 
          AND article10 = ? 
          AND ct_shiftdate::DATE = ?::DATE
        GROUP BY 1
        HAVING COUNT(*) >= ?
    ),
    spec_stats_three_days AS (
        SELECT 
            CAST({col} AS VARCHAR) AS machine,
            ct_shiftdate::DATE AS dt,
            AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_avg,
            STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_std
        FROM clean_yield
        WHERE {col} IS NOT NULL 
          AND article10 = ? 
          AND ct_shiftdate::DATE IN (?::DATE - 1, ?::DATE, ?::DATE + 1)
        GROUP BY 1, 2
    ),
    all_stats_three_days AS (
        SELECT 
            CAST({col} AS VARCHAR) AS machine,
            ct_shiftdate::DATE AS dt,
            COUNT(*) AS all_n,
            AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS all_avg,
            STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS all_std
        FROM clean_yield
        WHERE {col} IS NOT NULL 
          AND ct_shiftdate::DATE IN (?::DATE - 1, ?::DATE, ?::DATE + 1)
        GROUP BY 1, 2
    )
    SELECT 
        '{col}' AS workcenter_col,
        m.machine,
        m.spec_n,
        
        ROUND(s_curr.spec_avg + 3.0 * COALESCE(s_curr.spec_std, 0.0), 4) AS spec_avg_3sigma,
        ROUND(s_curr.spec_avg, 4) AS spec_avg,
        ROUND(COALESCE(s_curr.spec_std, 0.0), 4) AS spec_std,
        
        COALESCE(a_curr.all_n, 0) AS all_n,
        ROUND(a_curr.all_avg + 3.0 * COALESCE(a_curr.all_std, 0.0), 4) AS all_avg_3sigma,
        ROUND(a_curr.all_avg, 4) AS all_avg,
        ROUND(COALESCE(a_curr.all_std, 0.0), 4) AS all_std,
        
        CASE WHEN 
            (s_prev.spec_avg + 3.0 * COALESCE(s_prev.spec_std, 0.0)) > (s_curr.spec_avg + 3.0 * COALESCE(s_curr.spec_std, 0.0)) AND
            (s_curr.spec_avg + 3.0 * COALESCE(s_curr.spec_std, 0.0)) > (s_next.spec_avg + 3.0 * COALESCE(s_next.spec_std, 0.0))
        THEN 1 ELSE 0 END AS spec_declining_warning,
        
        CASE WHEN 
            (a_prev.all_avg + 3.0 * COALESCE(a_prev.all_std, 0.0)) > (a_curr.all_avg + 3.0 * COALESCE(a_curr.all_std, 0.0)) AND
            (a_curr.all_avg + 3.0 * COALESCE(a_curr.all_std, 0.0)) > (a_next.all_avg + 3.0 * COALESCE(a_next.all_std, 0.0))
        THEN 1 ELSE 0 END AS all_declining_warning
    FROM active_machines m
    LEFT JOIN spec_stats_three_days s_curr ON m.machine = s_curr.machine AND s_curr.dt = ?::DATE
    LEFT JOIN spec_stats_three_days s_prev ON m.machine = s_prev.machine AND s_prev.dt = ?::DATE - 1
    LEFT JOIN spec_stats_three_days s_next ON m.machine = s_next.machine AND s_next.dt = ?::DATE + 1
    LEFT JOIN all_stats_three_days a_curr ON m.machine = a_curr.machine AND a_curr.dt = ?::DATE
    LEFT JOIN all_stats_three_days a_prev ON m.machine = a_prev.machine AND a_prev.dt = ?::DATE - 1
    LEFT JOIN all_stats_three_days a_next ON m.machine = a_next.machine AND a_next.dt = ?::DATE + 1
  )
"""

union_params = [
    # active_machines
    article10, target_date, min_samples,
    # spec_stats_three_days
    article10, target_date, target_date, target_date,
    # all_stats_three_days
    target_date, target_date, target_date,
    # joins
    target_date, target_date, target_date,
    target_date, target_date, target_date
]

res = con.execute(sql, union_params).df()
print("Success running SQL syntax test!")
print(res.to_string())
