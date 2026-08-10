import os
import duckdb

_BASE = os.path.dirname(__file__)
data_path = os.path.normpath(os.path.join(_BASE, 'src', 'yield_flat_table_30d_2_cleaned.parquet')).replace('\\', '/')
study_from = '2026-05-25'
study_to = '2026-05-28'
min_yield = 50

con = duckdb.connect()

sql = f"""
    SELECT article10, COUNT(*) as cnt
    FROM read_parquet('{data_path}')
    WHERE ct_shiftdate::DATE >= DATE '{study_from}' 
      AND ct_shiftdate::DATE <= DATE '{study_to}'
    GROUP BY article10
    ORDER BY cnt DESC
    LIMIT 5
"""
print(con.execute(sql).df())
con.close()
