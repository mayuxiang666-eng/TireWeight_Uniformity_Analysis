import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

# Get all workcenter columns
cols = [r[0] for r in con.execute("DESCRIBE clean_yield").fetchall() if 'workcenter' in r[0]]

# Print overall row count for 2026-06-14 and article10 = '0315626000'
res_total = con.execute("SELECT COUNT(*) FROM clean_yield WHERE ct_shiftdate::DATE = '2026-06-14' AND article10 = '0315626000'").fetchone()[0]
print(f"Total rows for 2026-06-14 and 0315626000: {res_total}")

# Print counts for each workcenter column
select_parts = ", ".join([f"COUNT({c}) AS {c}_count, COUNT(DISTINCT {c}) AS {c}_distinct" for c in cols])
sql = f"SELECT {select_parts} FROM clean_yield WHERE ct_shiftdate::DATE = '2026-06-14' AND article10 = '0315626000'"
df = con.execute(sql).df()
print("\nCounts in workcenter columns:")
for col in cols:
    print(f"  {col}: non-null count = {df[f'{col}_count'][0]}, unique machines = {df[f'{col}_distinct'][0]}")

# Let's inspect some rows to see if there is any column that has nulls or if there is filtering
print("\nFirst 5 rows of these columns:")
df_rows = con.execute(f"SELECT ct_shiftdate::DATE, article10, {', '.join(cols)} FROM clean_yield WHERE ct_shiftdate::DATE = '2026-06-14' AND article10 = '0315626000' LIMIT 5").df()
print(df_rows.to_string())
