import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

spec = "0314931000"
target_date = "2026-08-02"

res = con.execute("""
    SELECT gt_workcenter, ct_workcenter, tu_first_workcenter, tb_first_workcenter, rfppwc_first
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
    LIMIT 5
""", [spec, target_date]).fetchall()

print("Sample rows:")
for r in res:
    print(r)

# Let's see all unique gt_workcenter values on this day
gts = con.execute("""
    SELECT gt_workcenter, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
    GROUP BY 1
""", [spec, target_date]).fetchall()
print("\nUnique gt_workcenter values:")
for r in gts:
    print(r)
