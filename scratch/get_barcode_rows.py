import os
import duckdb

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

# Find a barcode that has exactly 4 rows
barcode_info = con.execute(f"""
    SELECT barcode, COUNT(*) as cnt 
    FROM read_parquet('{new_path}') 
    GROUP BY barcode 
    HAVING cnt = 4 
    LIMIT 1
""").fetchone()

if barcode_info:
    barcode = barcode_info[0]
    print(f"Selected Barcode: {barcode}")
    
    # Query all columns for this barcode
    df = con.execute(f"SELECT * FROM read_parquet('{new_path}') WHERE barcode = '{barcode}'").df()
    
    # Manual Markdown Table formatting
    columns = df.columns
    rows_data = df.values.tolist()
    
    md_lines = []
    # Header
    header = "| Column Name | Is Different? | " + " | ".join([f"Row {i+1}" for i in range(len(rows_data))]) + " |"
    sep = "| :--- | :---: | " + " | ".join([":---" for _ in range(len(rows_data))]) + " |"
    md_lines.append(header)
    md_lines.append(sep)
    
    for col_idx, col_name in enumerate(columns):
        vals = [str(r[col_idx]) for r in rows_data]
        is_diff = "DIFF" if len(set(vals)) > 1 else "SAME"
        row_str = f"| `{col_name}` | {is_diff} | " + " | ".join([f"`{v}`" if v != 'None' else '*None*' for v in vals]) + " |"
        md_lines.append(row_str)
        
    md_table = "\n".join(md_lines)
    print("\n--- TRANSPOSED MD TABLE ---")
    # Avoid printing directly to console if it might fail, write to file first
    with open(os.path.join(_BASE, 'sample_transposed.md'), 'w', encoding='utf-8') as f:
        f.write(f"# Barcode {barcode} Transposed Rows Comparison\n\n")
        f.write(md_table)
    print("Done writing to sample_transposed.md")
else:
    print("No barcode with 4 rows found.")

con.close()
