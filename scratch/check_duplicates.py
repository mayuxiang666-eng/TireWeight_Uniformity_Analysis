import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')
old_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_30d_2_cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

print("Duplicate barcode counts in NEW table:")
print(con.execute(f"""
    SELECT cnt, COUNT(*) 
    FROM (SELECT barcode, COUNT(*) as cnt FROM read_parquet('{new_path}') GROUP BY barcode) 
    GROUP BY cnt ORDER BY cnt DESC
""").df().to_string())

print("\nDuplicate barcode counts in OLD table:")
print(con.execute(f"""
    SELECT cnt, COUNT(*) 
    FROM (SELECT barcode, COUNT(*) as cnt FROM read_parquet('{old_path}') GROUP BY barcode) 
    GROUP BY cnt ORDER BY cnt DESC
""").df().to_string())

print("\nAre rows duplicate in NEW table, or do they differ by some column?")
# Let's select one barcode with count > 1 and see all its columns
dup_barcode = con.execute(f"SELECT barcode FROM read_parquet('{new_path}') GROUP BY barcode HAVING COUNT(*) > 1 LIMIT 1").fetchone()[0]
print(f"Barcode with duplicates: {dup_barcode}")
dup_rows = con.execute(f"SELECT * FROM read_parquet('{new_path}') WHERE barcode = '{dup_barcode}'").df()
print(dup_rows.to_string())

con.close()
