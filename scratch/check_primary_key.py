import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

unique_barcodes = con.execute(f"SELECT COUNT(DISTINCT barcode) FROM read_parquet('{new_path}')").fetchone()[0]
print(f"Total unique barcodes in new table: {unique_barcodes}")
print(f"Total rows in new table: {con.execute(f'SELECT COUNT(*) FROM read_parquet(\'{new_path}\')').fetchone()[0]}")

# Let's see if (barcode, greentiregutsid, specissue) is unique
print("\nCheck uniqueness of (barcode, greentiregutsid, specissue):")
print(con.execute(f"""
    SELECT cnt, COUNT(*) 
    FROM (SELECT barcode, greentiregutsid, specissue, COUNT(*) as cnt FROM read_parquet('{new_path}') GROUP BY barcode, greentiregutsid, specissue) 
    GROUP BY cnt ORDER BY cnt DESC
""").df().to_string())

# Let's see if (barcode, greentiregutsid) is unique
print("\nCheck uniqueness of (barcode, greentiregutsid):")
print(con.execute(f"""
    SELECT cnt, COUNT(*) 
    FROM (SELECT barcode, greentiregutsid, COUNT(*) as cnt FROM read_parquet('{new_path}') GROUP BY barcode, greentiregutsid) 
    GROUP BY cnt ORDER BY cnt DESC
""").df().to_string())

# Let's see if (barcode, specissue) is unique
print("\nCheck uniqueness of (barcode, specissue):")
print(con.execute(f"""
    SELECT cnt, COUNT(*) 
    FROM (SELECT barcode, specissue, COUNT(*) as cnt FROM read_parquet('{new_path}') GROUP BY barcode, specissue) 
    GROUP BY cnt ORDER BY cnt DESC
""").df().to_string())

# Let's check the number of non-null greentiregutsid
null_guts = con.execute(f"SELECT COUNT(*) FROM read_parquet('{new_path}') WHERE greentiregutsid IS NULL").fetchone()[0]
print(f"\nNull greentiregutsid count: {null_guts}")

con.close()
