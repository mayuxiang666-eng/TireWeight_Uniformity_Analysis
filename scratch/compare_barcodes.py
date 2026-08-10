import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')
old_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_30d_2_cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

# Find intersection barcodes
barcodes_sql = f"""
    SELECT barcode 
    FROM read_parquet('{new_path}')
    INTERSECT
    SELECT barcode 
    FROM read_parquet('{old_path}')
    LIMIT 5
"""
matching_barcodes = con.execute(barcodes_sql).df()['barcode'].tolist()
print("Matching barcodes:", matching_barcodes)

if matching_barcodes:
    barcodes_str = ", ".join([f"'{b}'" for b in matching_barcodes])
    
    print("\nOld table sample:")
    old_sample = con.execute(f"""
        SELECT barcode, grade_anomaly_new, grade_rfppwc_first, grade_rfh1wc_first, grade_cony_first 
        FROM read_parquet('{old_path}') 
        WHERE barcode IN ({barcodes_str})
    """).df()
    print(old_sample.to_string())
    
    print("\nNew table sample:")
    new_sample = con.execute(f"""
        SELECT barcode, grade_anomaly, rfppwc_first, rfh1wc_first, rfpp_anomaly, rfh1_anomaly, anomaly_code
        FROM read_parquet('{new_path}') 
        WHERE barcode IN ({barcodes_str})
    """).df()
    print(new_sample.to_string())
else:
    print("No matching barcodes found.")

con.close()
