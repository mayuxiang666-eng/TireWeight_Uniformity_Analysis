import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

sql = f"""
SELECT 
    ct_shiftdate::DATE as dt,
    article10,
    "group",
    COUNT(*) as n,
    AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_rfpp,
    STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp,
    AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) as avg_rfh1,
    STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) as std_rfh1,
    ANY_VALUE(standard_rfpp) as std_rfpp_col,
    ANY_VALUE(standard_rfh1) as std_rfh1_col
FROM read_parquet('{DATA_PATH}')
WHERE article10 = '0312423000' AND ct_shiftdate::DATE = '2026-07-13'
GROUP BY 1, 2, 3
"""

rows = conn.execute(sql).fetchall()
cols = [d[0] for d in conn.description]
for r in rows:
    print(dict(zip(cols, r)))
