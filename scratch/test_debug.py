import sys
import os
sys.path.append(os.path.abspath('backend'))

import duckdb
import numpy as np
from main import get_periods, LOT_MAP

_BASE = 'backend'
DATA_PATH = os.path.normpath(
    os.path.join(_BASE, "..", "src", "yield_flat_table_30d_2_cleaned.parquet")
).replace("\\", "/")

db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

def qry(sql: str, params=None):
    cursor = db_conn.cursor()
    if params:
        rel = cursor.execute(sql, params)
    else:
        rel = cursor.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    cursor.close()
    return [dict(zip(cols, r)) for r in rows]

baseline_from = "2026-05-31"
baseline_to = "2026-06-02"
study_from = "2026-06-04"
study_to = "2026-06-06"
min_yield = 50
cv_threshold = 0.4

b_from, b_to, s_from, s_to = get_periods(baseline_from, baseline_to, study_from, study_to)
print("Periods after get_periods:", b_from, b_to, s_from, s_to)

# Let's see overall numbers
sql_overall = """
    SELECT 
        COUNT(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_b,
        SUM(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_b,
        COUNT(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN 1 END) AS total_s,
        SUM(CASE WHEN ct_shiftdate::DATE >= ?::DATE AND ct_shiftdate::DATE <= ?::DATE THEN CAST(grade_anomaly_new AS INT) ELSE 0 END) AS anomalies_s
    FROM clean_yield
"""
overall = qry(sql_overall, [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to])[0]
print("Overall stats:", overall)

sql_overall_yield = """
    SELECT 
        COUNT(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN 1 END) AS total_b,
        COUNT(CASE WHEN ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE THEN 1 END) AS total_s
    FROM clean_yield
    WHERE ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE
"""
overall_stats = qry(sql_overall_yield, [b_from, b_to, s_from, s_to, b_from, s_to])[0]
print("Overall stats (yield):", overall_stats)
t_s_all = overall_stats['total_s'] or 0
t_b_all = overall_stats['total_b'] or 0

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
        anomalies_s AS anomalies,
        CASE WHEN total_s > 0 THEN ROUND(CAST(anomalies_s AS DOUBLE) / total_s * 100, 4) ELSE 0 END AS anomaly_rate,
        ROUND(
            (
                (CAST(anomalies_s AS DOUBLE) / NULLIF(?, 0)) - 
                (CAST(anomalies_b AS DOUBLE) / NULLIF(?, 0))
            ) * 100, 
            4
        ) AS contribution
    FROM by_article
"""
art_rows = qry(sql_top_articles, [
    b_from, b_to,
    b_from, b_to,
    s_from, s_to,
    s_from, s_to,
    b_from, s_to,
    min_yield,
    t_s_all, t_b_all
])
print("Art rows count:", len(art_rows))
art_rows.sort(key=lambda x: abs(x['contribution'] or 0.0), reverse=True)
top_articles = art_rows[:20]

# 2. 找到工序机台列
col_sql = """
    SELECT column_name
    FROM (DESCRIBE SELECT * FROM clean_yield LIMIT 1)
    WHERE column_name LIKE '%workcenter%'
      AND column_name NOT LIKE 'tu_%'
      AND column_name NOT LIKE 'tb_%'
      AND column_name NOT LIKE 'tg_%'
      AND column_name != 'css_workcenter'
"""
wc_cols = [r["column_name"] for r in qry(col_sql)]

spec_issues = []
machine_issues = []
material_issues = []

if top_articles and wc_cols:
    target_specs = [a['article10'] for a in top_articles]
    spec_placeholders = ",".join(["?"] * len(target_specs))
    
    union_parts = []
    union_params = []
    for col in wc_cols:
        union_parts.append(f"""
            SELECT article10, '{col}' AS workcenter_col, 
                   CONCAT('{col}', ':', CAST({col} AS VARCHAR)) AS machine,
                   ct_shiftdate, grade_anomaly_new
            FROM clean_yield
            WHERE article10 IN ({spec_placeholders}) AND {col} IS NOT NULL
              AND ct_shiftdate >= ?::DATE AND ct_shiftdate <= ?::DATE
        """)
        union_params += target_specs + [b_from, s_to]
    
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
            WHERE article10 IN ({spec_placeholders})
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
            bm.article10,
            bm.workcenter_col,
            bm.machine,
            bm.total_s AS total,
            bm.anomalies_s AS anomalies,
            bm.total_b,
            bm.anomalies_b,
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
        target_specs + 
        [b_from, b_to, b_from, b_to, s_from, s_to, s_from, s_to, min_yield]
    )
    
    print("Executing sql_by_mach...")
    raw_mach_rows = qry(sql_by_mach, mach_params)
    print("raw_mach_rows count:", len(raw_mach_rows))
