"""
DuckDB 内存溢出诊断脚本 - 仅诊断不修改
用于排查服务器上 merge_data.py DuckDB OOM 问题
"""
import sys
import os
import platform

print("=" * 60)
print("DuckDB 内存溢出诊断报告")
print("=" * 60)

# --- 1. 系统信息 ---
print("\n[1] 系统信息:")
print(f"  Python 版本: {sys.version}")
print(f"  操作系统: {platform.system()} {platform.release()} {platform.machine()}")
try:
    import psutil
    mem = psutil.virtual_memory()
    print(f"  总物理内存: {mem.total / 1024**3:.2f} GB")
    print(f"  当前可用内存: {mem.available / 1024**3:.2f} GB")
    print(f"  当前已用内存: {mem.used / 1024**3:.2f} GB ({mem.percent:.1f}%)")
    cpu_count = psutil.cpu_count(logical=False)
    print(f"  CPU 物理核心: {cpu_count}")
except ImportError:
    print("  [psutil 未安装，跳过内存信息检查]")

# --- 2. DuckDB 版本与默认配置 ---
print("\n[2] DuckDB 信息:")
try:
    import duckdb
    print(f"  DuckDB 版本: {duckdb.__version__}")
    con = duckdb.connect()
    try:
        settings = con.execute(
            "SELECT name, value, description FROM duckdb_settings() WHERE name IN ('max_memory', 'threads', 'preserve_insertion_order', 'worker_threads')"
        ).fetchall()
        for s in settings:
            print(f"  设置 [{s[0]}] = {s[1]}")
    except Exception as e:
        print(f"  [查询设置失败: {e}]")
    con.close()
except Exception as e:
    print(f"  [DuckDB 加载失败: {e}]")

# --- 3. 检查本地 Parquet 文件大小 ---
print("\n[3] 本地 Parquet 文件状态:")
candidates = [
    r"D:\TU AI\TireWeight_Uniformity_Analysis\backend\data",
    r"D:\TU AI\TireWeight_Uniformity_Analysis\data",
]
for data_dir in candidates:
    for fname in ["yield_flat_table_joined_100.parquet", "yield_incremental.parquet.tmp"]:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            size_mb = os.path.getsize(fpath) / 1024**2
            print(f"  [FOUND] {fpath}")
            print(f"    大小: {size_mb:.1f} MB")
        else:
            print(f"  [NOT FOUND] {fpath}")

# --- 4. 模拟小规模合并 SQL 测试 DuckDB 是否支持 ANTI JOIN ---
print("\n[4] DuckDB ANTI JOIN 语法支持测试:")
try:
    import duckdb
    con = duckdb.connect()
    sql_anti = """
        SELECT base.* 
        FROM (SELECT 'BC1' AS barcode, '2026-08-01' AS ts) base
        ANTI JOIN (
            SELECT DISTINCT CAST(barcode AS VARCHAR) AS barcode
            FROM (SELECT 'BC2' AS barcode)
            WHERE barcode IS NOT NULL
        ) inc_bc_table
        ON CAST(base.barcode AS VARCHAR) = CAST(inc_bc_table.barcode AS VARCHAR)
    """
    res = con.execute(sql_anti).fetchall()
    print(f"  ANTI JOIN 语法测试: OK -> 结果 {res}")
    con.close()
except Exception as e:
    print(f"  ANTI JOIN 语法测试: FAILED -> {e}")

# --- 5. 检查服务器 ETL 文件版本（是否同步了 ANTI JOIN 修复）---
print("\n[5] 服务器 merge_data.py 文件关键词检查:")
server_merge = r"D:\TU AI\TireWeight_Uniformity_Analysis\etl\merge_data.py"
if os.path.exists(server_merge):
    with open(server_merge, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    print(f"  文件路径: {server_merge}")
    print(f"  文件大小: {os.path.getsize(server_merge)} bytes")
    print(f"  包含 'ANTI JOIN': {'YES' if 'ANTI JOIN' in content else 'NO - 旧版本！未同步！'}")
    print(f"  包含 'NOT IN': {'YES - 旧版本！' if 'NOT IN' in content else 'NO'}")
    print(f"  包含 'max_memory': {'YES' if 'max_memory' in content else 'NO - 未设置内存限制！'}")
    print(f"  包含 'preserve_insertion_order': {'YES' if 'preserve_insertion_order' in content else 'NO'}")
else:
    print(f"  [NOT FOUND] {server_merge}")
    # 尝试 backend/etl 目录
    alt_merge = r"D:\TU AI\TireWeight_Uniformity_Analysis\backend\etl\merge_data.py"
    if os.path.exists(alt_merge):
        with open(alt_merge, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        print(f"  文件路径: {alt_merge}")
        print(f"  包含 'ANTI JOIN': {'YES' if 'ANTI JOIN' in content else 'NO - 旧版本！未同步！'}")
        print(f"  包含 'NOT IN': {'YES - 旧版本！' if 'NOT IN' in content else 'NO'}")
        print(f"  包含 'max_memory': {'YES' if 'max_memory' in content else 'NO'}")
    else:
        print(f"  [NOT FOUND] {alt_merge}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
