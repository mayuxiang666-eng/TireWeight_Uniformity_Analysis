"""
DuckDB 内存溢出深度诊断：
确认服务器执行合并时，ANTI JOIN 是否触发 OOM 以及可用内存实际值
"""
import duckdb
import os
import platform
import sys

try:
    import psutil
    mem = psutil.virtual_memory()
    print(f"总物理内存: {mem.total / 1024**3:.2f} GB")
    print(f"可用内存:   {mem.available / 1024**3:.2f} GB  ({mem.percent:.1f}% 已用)")
    swap = psutil.swap_memory()
    print(f"交换内存:   {swap.total / 1024**3:.2f} GB 总，{swap.used / 1024**3:.2f} GB 已用")
except Exception as e:
    print(f"psutil 不可用: {e}")

print()
print(f"Python: {sys.version}")
print(f"Platform: {platform.system()} {platform.machine()}")

print()
print("--- DuckDB 内存配置 ---")
con = duckdb.connect()
settings = con.execute(
    "SELECT name, value FROM duckdb_settings() WHERE name IN ('max_memory', 'threads', 'temp_directory', 'preserve_insertion_order')"
).fetchall()
for s in settings:
    print(f"  {s[0]} = {s[1]}")

# 尝试 SET max_memory
try:
    con.execute("SET max_memory='4GB'")
    val = con.execute("SELECT value FROM duckdb_settings() WHERE name='max_memory'").fetchone()
    print(f"  SET max_memory='4GB' 成功，当前值: {val[0]}")
except Exception as e:
    print(f"  SET max_memory='4GB' 失败: {e}")

print()
print("--- 检查 Parquet 文件大小 ---")
candidates = [
    r"D:\TU AI\TireWeight_Uniformity_Analysis\backend\data",
    r"D:\TU AI\TireWeight_Uniformity_Analysis\data",
]
base_path = None
inc_path = None
for d in candidates:
    bp = os.path.join(d, "yield_flat_table_joined_100.parquet")
    ip = os.path.join(d, "yield_incremental.parquet.tmp")
    if os.path.exists(bp) and base_path is None:
        base_path = bp
        print(f"  Base Parquet: {os.path.getsize(bp)/1024**2:.1f} MB -> {bp}")
    if os.path.exists(ip) and inc_path is None:
        inc_path = ip
        print(f"  Inc  Parquet: {os.path.getsize(ip)/1024**2:.1f} MB -> {ip}")

if base_path and inc_path:
    print()
    print("--- 模拟 DuckDB 合并内存需求估算 ---")
    con2 = duckdb.connect()
    try:
        base_rows = con2.execute(f"SELECT COUNT(*) FROM read_parquet('{base_path}')").fetchone()[0]
        inc_rows  = con2.execute(f"SELECT COUNT(*) FROM read_parquet('{inc_path}')").fetchone()[0]
        # barcode distinct count (for ANTI JOIN hash table size)
        inc_bc_count = con2.execute(
            f"SELECT COUNT(DISTINCT CAST(barcode AS VARCHAR)) FROM read_parquet('{inc_path}') WHERE barcode IS NOT NULL"
        ).fetchone()[0]
        print(f"  Base rows:          {base_rows:,}")
        print(f"  Inc  rows:          {inc_rows:,}")
        print(f"  Inc unique barcodes:{inc_bc_count:,}  (ANTI JOIN hash table 大小)")
        # Rough estimate: 77874 unique strings * 30 bytes avg = ~2.3 MB hash table
        estimated_hash_mb = inc_bc_count * 50 / 1024**2
        print(f"  估算 hash 表内存:   {estimated_hash_mb:.1f} MB  (应该很小！)")
        
        # Total merged rows estimate
        total_estimated = base_rows + inc_rows
        print(f"  合并后行数上限:     {total_estimated:,}")
        # 66 columns * 30 bytes avg * total rows = estimate
        est_result_mb = total_estimated * 66 * 30 / 1024**2
        print(f"  结果集估算大小:     {est_result_mb:.0f} MB")
        print()
        print("  [关键] DuckDB COPY TO PARQUET 是流式写入——不需要把全部结果放入内存")
        print("  [关键] ANTI JOIN 的 hash 表只有增量 barcode，非常小")
        print("  [关键] 如果仍然 OOM，问题可能在于 max_memory SET 没有生效")
    except Exception as e:
        print(f"  统计失败: {e}")
    finally:
        con2.close()
else:
    print("  [WARNING] 找不到 Parquet 文件，可能路径有误")

print()
print("--- ANTI JOIN EXPLAIN ANALYZE 计划 ---")
try:
    con3 = duckdb.connect()
    con3.execute("SET max_memory='4GB'")
    con3.execute("SET preserve_insertion_order=false")
    explain = con3.execute("""
    EXPLAIN SELECT COUNT(*) FROM (
        SELECT 'BC2' AS barcode, '2026-08-21' AS tu_first_loc_timestamp
        UNION ALL BY NAME
        SELECT base.* 
        FROM (
            SELECT 'BC1' AS barcode, '2026-08-01' AS tu_first_loc_timestamp
            UNION ALL BY NAME
            SELECT 'BC3' AS barcode, '2026-07-01' AS tu_first_loc_timestamp
        ) base
        ANTI JOIN (
            SELECT DISTINCT CAST(barcode AS VARCHAR) AS barcode
            FROM (SELECT 'BC2' AS barcode)
            WHERE barcode IS NOT NULL
        ) inc_bc_table
        ON CAST(base.barcode AS VARCHAR) = CAST(inc_bc_table.barcode AS VARCHAR)
    )
    WHERE tu_first_loc_timestamp IS NULL 
       OR TRY_CAST(tu_first_loc_timestamp AS DATE) >= DATE '2026-07-25'
    """).fetchall()
    for row in explain:
        print(row[1])
    con3.close()
except Exception as e:
    print(f"EXPLAIN 失败: {e}")
