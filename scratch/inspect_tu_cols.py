import duckdb

con = duckdb.connect()
p = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{p}')")

cols = [r[0] for r in con.execute("DESCRIBE cy").fetchall()]
print("Parquet columns containing 'tu':", [c for c in cols if 'tu' in c.lower()])
print("Parquet columns containing 'gt':", [c for c in cols if 'gt' in c.lower()])

# Check tu_first_shift_date vs gt_loc_timestamp
df = con.execute("""
    SELECT 
        tu_first_shift_date,
        gt_loc_timestamp,
        ct_loc_timestamp,
        tu_first_workcenter,
        gt_workcenter
    FROM cy
    LIMIT 5
""").df()
print(df)
