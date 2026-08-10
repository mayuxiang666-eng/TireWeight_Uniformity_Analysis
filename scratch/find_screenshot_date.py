import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

spec = "0314931000"

res = con.execute("""
    SELECT tu_first_shift_date::DATE, gt_workcenter, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND gt_workcenter IN ('TB244', 'TB286')
    GROUP BY 1, 2
    ORDER BY 1 DESC
""", [spec]).fetchall()

print("Dates and gt counts:")
for r in res:
    print(r)
