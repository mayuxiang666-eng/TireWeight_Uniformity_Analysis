import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

# Find a barcode where (barcode, greentiregutsid, specissue) has count > 1
dup_sql = f"""
    SELECT barcode, greentiregutsid, specissue, COUNT(*) as cnt 
    FROM read_parquet('{new_path}') 
    GROUP BY barcode, greentiregutsid, specissue 
    HAVING COUNT(*) > 1 
    LIMIT 3
"""
dup_keys = con.execute(dup_sql).df()
print("Duplicate keys example:")
print(dup_keys.to_string())

if not dup_keys.empty:
    for idx, row in dup_keys.iterrows():
        b = row['barcode']
        g = row['greentiregutsid']
        s = row['specissue']
        
        # Select all columns where barcode, greentiregutsid, specissue match
        print(f"\nDetails for barcode={b}, greentiregutsid={g}, specissue={s}:")
        df_rows = con.execute(f"""
            SELECT * FROM read_parquet('{new_path}') 
            WHERE barcode = '{b}' AND greentiregutsid = '{g}' AND specissue = '{s}'
        """).df()
        # Find which columns differ between these rows
        differing_cols = []
        for col in df_rows.columns:
            if df_rows[col].nunique(dropna=False) > 1:
                differing_cols.append(col)
        print("Differing columns:", differing_cols)
        print(df_rows[['barcode', 'greentiregutsid', 'specissue'] + differing_cols].to_string())

con.close()
