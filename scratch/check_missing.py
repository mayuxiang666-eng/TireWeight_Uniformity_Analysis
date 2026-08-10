import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
con = duckdb.connect()
con.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{DATA_PATH}')")

spec = "0314931000"
target_date = "2026-07-14"

# 1. 查找基本统计
total_sql = """
    SELECT COUNT(*) as total_cnt
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
"""
total_cnt = con.execute(total_sql, [spec, target_date]).fetchone()[0]

# 2. 四工位全部非空统计 (树分析数据量)
all_not_null_sql = """
    SELECT COUNT(*)
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
      AND gt_workcenter IS NOT NULL
      AND ct_workcenter IS NOT NULL
      AND tu_first_workcenter IS NOT NULL
      AND tb_first_workcenter IS NOT NULL
"""
all_not_null_cnt = con.execute(all_not_null_sql, [spec, target_date]).fetchone()[0]

# 3. 统计每个单独工位非空的数量
wc_stats_sql = """
    SELECT 
        COUNT(gt_workcenter) as gt_n,
        COUNT(ct_workcenter) as ct_n,
        COUNT(tu_first_workcenter) as tu_n,
        COUNT(tb_first_workcenter) as tb_n
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
"""
wc_stats = con.execute(wc_stats_sql, [spec, target_date]).fetchone()

# 4. 统计具体各种缺失情况的组合
missing_breakdown_sql = """
    SELECT 
        (gt_workcenter IS NOT NULL) as has_gt,
        (ct_workcenter IS NOT NULL) as has_ct,
        (tu_first_workcenter IS NOT NULL) as has_tu,
        (tb_first_workcenter IS NOT NULL) as has_tb,
        COUNT(*) as cnt
    FROM clean_yield
    WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
    GROUP BY 1, 2, 3, 4
    ORDER BY cnt DESC
"""
breakdown = con.execute(missing_breakdown_sql, [spec, target_date]).fetchall()

# 5. 计算 CPK 的两个方法：
# 我们先获得 USL
usl_sql = """
    SELECT standard_rfpp * 10.0
    FROM clean_yield
    WHERE article10 = ? LIMIT 1
"""
usl = con.execute(usl_sql, [spec]).fetchone()[0]
if usl is None:
    usl = 100.0

print(f"Spec: {spec}, Target Date: {target_date}, USL: {usl}")
print(f"Total rows on target date: {total_cnt}")
print(f"All 4 workcenters NOT NULL (Tree dataset): {all_not_null_cnt}")
print(f"Individual non-null counts: GT={wc_stats[0]}, CT={wc_stats[1]}, TU={wc_stats[2]}, TB={wc_stats[3]}")
print("\nMissing breakdown (has_gt, has_ct, has_tu, has_tb):")
for row in breakdown:
    print(f"  GT:{row[0]}, CT:{row[1]}, TU:{row[2]}, TB:{row[3]} => Count: {row[4]}")

# 6. 计算 GT 机台 TB244 和 TB286 在两边的 CPK 差异
for machine in ["TB244", "TB286"]:
    # 局部非空 (Sankey)
    sankey_cpk_sql = """
        SELECT 
            COUNT(*),
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_v,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_v
        FROM clean_yield
        WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
          AND gt_workcenter = ? AND rfppwc_first IS NOT NULL
    """
    cnt_s, avg_s, std_s = con.execute(sankey_cpk_sql, [spec, target_date, machine]).fetchone()
    cpk_s = (usl - avg_s) / (3.0 * std_s) if std_s and std_s > 0 else 1.33

    # 全局非空 (Tree)
    tree_cpk_sql = """
        SELECT 
            COUNT(*),
            AVG(TRY_CAST(rfppwc_first AS DOUBLE)) as avg_v,
            STDDEV(TRY_CAST(rfppwc_first AS DOUBLE)) as std_v
        FROM clean_yield
        WHERE article10 = ? AND tu_first_shift_date::DATE = ?::DATE
          AND gt_workcenter = ? AND rfppwc_first IS NOT NULL
          AND gt_workcenter IS NOT NULL
          AND ct_workcenter IS NOT NULL
          AND tu_first_workcenter IS NOT NULL
          AND tb_first_workcenter IS NOT NULL
    """
    cnt_t, avg_t, std_t = con.execute(tree_cpk_sql, [spec, target_date, machine]).fetchone()
    cpk_t = (usl - avg_t) / (3.0 * std_t) if std_t and std_t > 0 else 1.33

    avg_s_str = f"{avg_s:.3f}" if avg_s is not None else "0"
    avg_t_str = f"{avg_t:.3f}" if avg_t is not None else "0"
    std_s_str = f"{std_s:.3f}" if std_s is not None else "0"
    std_t_str = f"{std_t:.3f}" if std_t is not None else "0"
    print(f"\nMachine {machine}:")
    print(f"  Sankey (Local Non-Null): N = {cnt_s}, Avg = {avg_s_str}, Std = {std_s_str}, CPK = {cpk_s:.3f}")
    print(f"  Tree (Global Non-Null): N = {cnt_t}, Avg = {avg_t_str}, Std = {std_t_str}, CPK = {cpk_t:.3f}")
