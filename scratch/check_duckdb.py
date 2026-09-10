import duckdb

con = duckdb.connect()

# Get DuckDB memory and temp settings
settings = con.execute(
    "SELECT name, value FROM duckdb_settings() WHERE name IN ('max_memory', 'threads', 'temp_directory', 'preserve_insertion_order')"
).fetchall()
print("DuckDB default settings:")
for s in settings:
    print(f"  [{s[0]}] = {s[1]}")

# Check if ANTI JOIN is hash-based (check explain plan)
con.execute("SET max_memory='4GB'")
con.execute("SET preserve_insertion_order=false")

explain = con.execute("""
EXPLAIN 
SELECT base.* 
FROM (SELECT 'BC1' AS barcode, '2026-08-01' AS ts) base
ANTI JOIN (
    SELECT DISTINCT CAST(barcode AS VARCHAR) AS barcode
    FROM (SELECT 'BC2' AS barcode)
    WHERE barcode IS NOT NULL
) inc_bc_table
ON CAST(base.barcode AS VARCHAR) = CAST(inc_bc_table.barcode AS VARCHAR)
""").fetchall()
print("\nANTI JOIN query plan:")
for row in explain:
    print(row[1])

con.close()
