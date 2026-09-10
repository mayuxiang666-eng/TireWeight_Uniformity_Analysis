import duckdb

con = duckdb.connect()
p1 = "untitled1_v2/backend/data/yield_flat_table_joined_100.parquet"
p2 = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"

df1 = con.execute(f"SELECT MIN(tu_first_shift_date), MAX(tu_first_shift_date), COUNT(*) FROM read_parquet('{p1}')").df()
df2 = con.execute(f"SELECT MIN(tu_first_shift_date), MAX(tu_first_shift_date), COUNT(*) FROM read_parquet('{p2}')").df()

print("yield_flat_table_joined_100.parquet:", df1)
print("yield_flat_table_joined_100_cleaned.parquet:", df2)

# Check CGRS date range
cgrs_df = con.execute("SELECT MIN(TechOffsetLocalDate), MAX(TechOffsetLocalDate), COUNT(*) FROM read_csv_auto('untitled1_v2/backend/data/CGRS.csv', all_varchar=True)").df()
print("CGRS.csv date range:", cgrs_df)
