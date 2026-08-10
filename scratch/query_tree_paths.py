import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

spec = "0314931000"
target_date = "2026-07-14"

# 查询在 HAVING COUNT(*) >= 10 时各路径的数据
paths_sql = """
    SELECT 
        gt_workcenter,
        ct_workcenter,
        tu_first_workcenter,
        tb_first_workcenter,
        COUNT(*) as lot_cnt
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
      AND gt_workcenter IS NOT NULL
      AND ct_workcenter IS NOT NULL
      AND tu_first_workcenter IS NOT NULL
      AND tb_first_workcenter IS NOT NULL
    GROUP BY 1, 2, 3, 4
    HAVING COUNT(*) >= 10
    ORDER BY lot_cnt DESC
"""
res = con.execute(paths_sql, [spec, target_date]).fetchall()
print("Paths with min_samples = 10:")
total = 0
for r in res:
    print(r)
    total += r[4]
print(f"Total count for paths: {total}")

# 查询所有路径（不加 HAVNG）
all_paths_sql = """
    SELECT 
        gt_workcenter,
        ct_workcenter,
        tu_first_workcenter,
        tb_first_workcenter,
        COUNT(*) as lot_cnt
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
      AND gt_workcenter IS NOT NULL
      AND ct_workcenter IS NOT NULL
      AND tu_first_workcenter IS NOT NULL
      AND tb_first_workcenter IS NOT NULL
    GROUP BY 1, 2, 3, 4
    ORDER BY lot_cnt DESC
"""
res_all = con.execute(all_paths_sql, [spec, target_date]).fetchall()
print("\nAll paths (no min_samples limit):")
for r in res_all:
    print(r)
