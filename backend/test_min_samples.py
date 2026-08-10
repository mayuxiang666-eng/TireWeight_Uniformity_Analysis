import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
db_conn = duckdb.connect()
db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

article10 = '0313451000'
target_date = '2026-06-24'

print("--- Testing min_samples = 50 ---")
res50 = db_conn.execute("""
    SELECT tread_workcenter, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND ct_shiftdate::DATE = ?::DATE AND tread_workcenter IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 50
""", [article10, target_date]).fetchall()
print("Count with min_samples=50:", res50)

print("--- Testing min_samples = 10 ---")
res10 = db_conn.execute("""
    SELECT tread_workcenter, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND ct_shiftdate::DATE = ?::DATE AND tread_workcenter IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 10
""", [article10, target_date]).fetchall()
print("Count with min_samples=10:", res10)

print("--- Testing min_samples = 5 ---")
res5 = db_conn.execute("""
    SELECT tread_workcenter, COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND ct_shiftdate::DATE = ?::DATE AND tread_workcenter IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 5
""", [article10, target_date]).fetchall()
print("Count with min_samples=5:", res5)
