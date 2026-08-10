import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

# Query machine counts in ct_workcenter
sql = """
    SELECT ct_workcenter, COUNT(*) as count
    FROM clean_yield 
    WHERE ct_shiftdate::DATE = '2026-06-14' AND article10 = '0315626000'
    GROUP BY ct_workcenter
    ORDER BY count DESC
"""
rows = con.execute(sql).fetchall()
print("Machine counts in ct_workcenter for 0315626000 on 2026-06-14:")
for r in rows:
    print(f"  {r[0]}: {r[1]}")
