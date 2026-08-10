import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

print("Is grade_anomaly constant for each barcode?")
grade_var = con.execute(f"""
    SELECT COUNT(*) 
    FROM (
        SELECT barcode 
        FROM read_parquet('{new_path}') 
        GROUP BY barcode 
        HAVING COUNT(DISTINCT grade_anomaly) > 1
    )
""").fetchone()[0]
print(f"Number of barcodes with varying grade_anomaly: {grade_var}")

print("\nIs rfpp_anomaly constant for each barcode?")
rfpp_var = con.execute(f"""
    SELECT COUNT(*) 
    FROM (
        SELECT barcode 
        FROM read_parquet('{new_path}') 
        GROUP BY barcode 
        HAVING COUNT(DISTINCT rfpp_anomaly) > 1
    )
""").fetchone()[0]
print(f"Number of barcodes with varying rfpp_anomaly: {rfpp_var}")

print("\nIs rfh1_anomaly constant for each barcode?")
rfh1_var = con.execute(f"""
    SELECT COUNT(*) 
    FROM (
        SELECT barcode 
        FROM read_parquet('{new_path}') 
        GROUP BY barcode 
        HAVING COUNT(DISTINCT rfh1_anomaly) > 1
    )
""").fetchone()[0]
print(f"Number of barcodes with varying rfh1_anomaly: {rfh1_var}")

print("\nCompute overall anomaly rates:")
# Row-level rates
row_grade_rate = con.execute(f"SELECT SUM(grade_anomaly)*100.0/COUNT(*) FROM read_parquet('{new_path}')").fetchone()[0]
row_rfpp_rate = con.execute(f"SELECT SUM(rfpp_anomaly)*100.0/COUNT(*) FROM read_parquet('{new_path}')").fetchone()[0]
row_rfh1_rate = con.execute(f"SELECT SUM(rfh1_anomaly)*100.0/COUNT(*) FROM read_parquet('{new_path}')").fetchone()[0]

# Barcode-level rates
# Since the anomaly status is constant for each barcode, we can take the MAX or AVG per barcode and then average them, or just query a deduplicated barcode table.
barcode_rates = con.execute(f"""
    WITH dedup AS (
        SELECT barcode, MAX(grade_anomaly) as grade_anomaly, MAX(rfpp_anomaly) as rfpp_anomaly, MAX(rfh1_anomaly) as rfh1_anomaly
        FROM read_parquet('{new_path}')
        GROUP BY barcode
    )
    SELECT 
        SUM(grade_anomaly)*100.0/COUNT(*) as b_grade_rate,
        SUM(rfpp_anomaly)*100.0/COUNT(*) as b_rfpp_rate,
        SUM(rfh1_anomaly)*100.0/COUNT(*) as b_rfh1_rate
    FROM dedup
""").fetchone()

print(f"Row-level:    grade_anomaly rate = {row_grade_rate:.4f}%, rfpp_anomaly rate = {row_rfpp_rate:.4f}%, rfh1_anomaly rate = {row_rfh1_rate:.4f}%")
print(f"Barcode-level: grade_anomaly rate = {barcode_rates[0]:.4f}%, rfpp_anomaly rate = {barcode_rates[1]:.4f}%, rfh1_anomaly rate = {barcode_rates[2]:.4f}%")

con.close()
