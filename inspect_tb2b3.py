import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

sql = f"""
SELECT 
    ct_shiftdate::DATE as dt,
    article10,
    ccs_workcenter,
    gt_workcenter,
    ct_workcenter,
    tu_first_workcenter,
    tg_first_workcenter,
    tb_first_workcenter,
    COUNT(*) as record_count
FROM read_parquet('{DATA_PATH}')
WHERE article10 = '0312082000' 
  AND ct_shiftdate::DATE = '2026-07-07'
  AND gt_workcenter = 'TB2B3'
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
"""

rows = conn.execute(sql).fetchall()
cols = [d[0] for d in conn.description]
print(f"Total rows found: {len(rows)}")
for r in rows:
    print(dict(zip(cols, r)))
