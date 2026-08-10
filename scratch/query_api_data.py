import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

def qry(sql, params=None):
    if params:
        return con.execute(sql, params).df()
    else:
        return con.execute(sql).df()

target_date = '2026-06-15'
article10 = '0315626000'
indicator_col = 'rfppwc_first'
min_samples = 5

col_sql = """
    SELECT column_name
    FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
    WHERE column_name LIKE '%workcenter%'
      AND column_name != 'css_workcenter'
"""
wc_cols = [r[0] for r in con.execute(col_sql).fetchall()]

union_parts = []
union_params = []
for col in wc_cols:
    union_parts.append(f"""
      (
        WITH spec_stats AS (
            SELECT 
                '{col}' AS workcenter_col,
                CAST({col} AS VARCHAR) AS machine,
                COUNT(*) AS spec_n,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_avg,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS spec_std
            FROM clean_yield
            WHERE {col} IS NOT NULL 
              AND article10 = ? 
              AND ct_shiftdate::DATE = ?::DATE
            GROUP BY 1, 2
            HAVING COUNT(*) >= ?
        ),
        all_stats AS (
            SELECT 
                '{col}' AS workcenter_col,
                CAST({col} AS VARCHAR) AS machine,
                COUNT(*) AS all_n,
                AVG(TRY_CAST({indicator_col} AS DOUBLE)) AS all_avg,
                STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) AS all_std
            FROM clean_yield
            WHERE {col} IS NOT NULL 
              AND ct_shiftdate::DATE = ?::DATE
            GROUP BY 1, 2
        )
        SELECT 
            s.workcenter_col,
            s.machine,
            s.spec_n,
            ROUND(s.spec_avg + 3.0 * COALESCE(s.spec_std, 0.0), 4) AS spec_avg_3sigma,
            ROUND(s.spec_avg, 4) AS spec_avg,
            ROUND(COALESCE(s.spec_std, 0.0), 4) AS spec_std,
            a.all_n,
            ROUND(a.all_avg + 3.0 * COALESCE(a.all_std, 0.0), 4) AS all_avg_3sigma,
            ROUND(a.all_avg, 4) AS all_avg,
            ROUND(COALESCE(a.all_std, 0.0), 4) AS all_std
        FROM spec_stats s
        JOIN all_stats a ON s.workcenter_col = a.workcenter_col AND s.machine = a.machine
      )
    """)
    union_params.extend([article10, target_date, min_samples, target_date])

sql = " UNION ALL ".join(union_parts) + " ORDER BY workcenter_col, spec_avg_3sigma DESC"
df = qry(sql, union_params)

# Filter for ct_workcenter
ct_df = df[df['workcenter_col'] == 'ct_workcenter']
print("Query results for ct_workcenter:")
print(ct_df.to_string())
