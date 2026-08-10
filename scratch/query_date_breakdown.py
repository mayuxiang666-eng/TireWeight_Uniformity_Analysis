import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

target_date = '2026-06-15'
article10 = '0315626000'

cols = [r[0] for r in con.execute("DESCRIBE clean_yield").fetchall() if 'workcenter' in r[0]]

res_total = con.execute(f"SELECT COUNT(*) FROM clean_yield WHERE ct_shiftdate::DATE = '{target_date}' AND article10 = '{article10}'").fetchone()[0]
print(f"Total rows for {target_date} and {article10}: {res_total}")

print("\nMachine counts for each workcenter column:")
for col in cols:
    sql = f"""
        SELECT {col}, COUNT(*) as count
        FROM clean_yield 
        WHERE ct_shiftdate::DATE = '{target_date}' AND article10 = '{article10}'
        GROUP BY {col}
        ORDER BY count DESC
    """
    rows = con.execute(sql).fetchall()
    print(f"  {col}: {len(rows)} machines")
    for r in rows:
        print(f"    - {r[0]}: {r[1]}")
