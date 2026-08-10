import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

wc_cols = ['tread_workcenter', 'bead_workcenter', 'inner_liner_workcenter', 'sidewall_workcenter', 'first_breaker_workcenter', 'second_breaker_workcenter', 'first_ply_workcenter', 'wound_cap_ply1_workcenter', 'wound_cap_ply2_workcenter', 'tb_first_workcenter', 'tg_first_workcenter', 'tu_first_workcenter', 'ct_workcenter']

select_clause = ", ".join(wc_cols)
sql = f"""
SELECT {select_clause}, COUNT(*) as flow_count, AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_rfpp, STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_rfpp, AVG(TRY_CAST(rfh1wc_first AS DOUBLE)) as avg_rfh1, STDDEV(TRY_CAST(rfh1wc_first AS DOUBLE)) as std_rfh1
FROM read_parquet('{DATA_PATH}')
WHERE article10 = '0312423000'
GROUP BY {", ".join([str(i+1) for i in range(len(wc_cols))])}
ORDER BY flow_count DESC
LIMIT 10
"""
rows = conn.execute(sql).fetchall()
cols = [d[0] for d in conn.description]
for r in rows:
    print(dict(zip(cols, r)))
