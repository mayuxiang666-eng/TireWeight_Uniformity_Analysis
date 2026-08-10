import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

spec = "0314931000"

# 查询该规格拥有的所有不同日期及其条数
dates_sql = """
    SELECT tu_first_shift_date::DATE, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date IS NOT NULL
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 20
"""
res = con.execute(dates_sql, [spec]).fetchall()
print("Dates in clean_yield for spec 0314931000:")
for r in res:
    print(f"  {r[0]} => {r[1]} rows")
