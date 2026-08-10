import duckdb
import os
import numpy as np

# Load database
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_BASE, "src", "yield_flat_table_30d_2_cleaned.parquet")
conn = duckdb.connect()
conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

# Dates from the user's current analysis period
s_from = "2026-06-07"
s_to = "2026-06-09"
b_from = "2026-06-04"
b_to = "2026-06-06"
min_yield = 50

# Workcenter columns
col_sql = """
    SELECT column_name
    FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
    WHERE column_name LIKE '%workcenter%'
      AND column_name NOT LIKE 'tu_%'
      AND column_name NOT LIKE 'tb_%'
      AND column_name NOT LIKE 'tg_%'
      AND column_name != 'css_workcenter'
"""
wc_cols = [r[0] for r in conn.execute(col_sql).fetchall()]

# Top articles
sql_top_articles = """
    WITH by_article AS (
        SELECT
            article10,
            COUNT(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN 1 END) AS total_b,
            SUM(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_b,
            COUNT(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN 1 END) AS total_s,
            SUM(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_s
        FROM clean_yield
        WHERE ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE
        GROUP BY article10
        HAVING total_s > ?
    )
    SELECT
        article10,
        total_s AS total,
        anomalies_s AS anomalies
    FROM by_article
"""
top_articles = conn.execute(sql_top_articles, [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to, b_from, s_to, min_yield]).fetchall()

# Sort top_articles by anomalies desc (or contribution)
# Let's just take the first 10 for simplicity
top_articles = top_articles[:10]

print("Top 10 Specs Analysis:")
print("=" * 60)

for art in top_articles:
    art_name = art[0]
    
    # Query machines for this spec
    union_parts = []
    union_params = []
    for col in wc_cols:
        union_parts.append(f"""
            SELECT article10, '{col}' AS workcenter_col, 
                   CONCAT('{col}', ':', CAST({col} AS VARCHAR)) AS machine,
                   ct_shiftdate, grade_anomaly_new
            FROM clean_yield
            WHERE article10 = ? AND {col} IS NOT NULL
              AND ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE
        """)
        union_params += [art_name, b_from, s_to]
    
    union_sql = " UNION ALL ".join(union_parts)
    
    sql_by_mach = f"""
        WITH melted AS ({union_sql}),
        overall_by_art AS (
            SELECT 
                article10,
                COUNT(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_b,
                SUM(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_b,
                COUNT(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_s,
                SUM(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_s
            FROM clean_yield
            WHERE article10 = ?
            GROUP BY article10
        ),
        by_machine AS (
            SELECT
                m.article10,
                m.workcenter_col,
                m.machine,
                COUNT(CASE WHEN m.ct_shiftdate::DATE >= ?::DATE AND m.ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_b,
                SUM(CASE WHEN m.ct_shiftdate::DATE >= ?::DATE AND m.ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_b,
                COUNT(CASE WHEN m.ct_shiftdate::DATE >= ?::DATE AND m.ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_s,
                SUM(CASE WHEN m.ct_shiftdate::DATE >= ?::DATE AND m.ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_s
            FROM melted m
            GROUP BY m.article10, m.workcenter_col, m.machine
            HAVING total_s > ?
        )
        SELECT
            bm.machine,
            bm.total_s AS total,
            bm.anomalies_s AS anomalies,
            ROUND(
                (CAST(bm.anomalies_s AS DOUBLE) / NULLIF(o.anomalies_s, 0)) / 
                ((CAST(bm.total_s AS DOUBLE) / NULLIF(o.total_s, 0)) + 1e-8),
                4
            ) AS step_lift
        FROM by_machine bm
        JOIN overall_by_art o ON bm.article10 = o.article10
    """
    
    mach_params = (
        union_params + 
        [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to] + 
        [art_name] + 
        [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to, min_yield]
    )
    
    machines = conn.execute(sql_by_mach, mach_params).fetchall()
    
    # Sort machines by step_lift desc
    machines = sorted(machines, key=lambda x: x[3] or 0.0, reverse=True)
    mach_top20 = machines[:20]
    
    if len(mach_top20) <= 1:
        continue
        
    lifts = [m[3] or 0.0 for m in mach_top20]
    mean_mach = sum(lifts) / len(lifts)
    std_mach = float(np.std(lifts, ddof=0))
    cv_mach = std_mach / mean_mach if mean_mach > 0 else 0.0
    
    print(f"Spec: {art_name}")
    print(f"  CV: {cv_mach:.4f}")
    print(f"  Top 5 Lifts: {[round(x, 4) for x in lifts[:5]]}")
    print("-" * 60)
