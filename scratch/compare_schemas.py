import os
import duckdb
import pandas as pd

_BASE = os.path.dirname(__file__)
new_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')
old_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_30d_2_cleaned.parquet')).replace('\\', '/')

con = duckdb.connect()

print("New parquet cols count:", len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{new_path}')").df()))
print("Old parquet cols count:", len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{old_path}')").df()))

new_df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{new_path}')").df()[['column_name', 'column_type']]
old_df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{old_path}')").df()[['column_name', 'column_type']]

# Merge to compare
comp_df = pd.merge(old_df, new_df, on='column_name', how='outer', suffixes=('_old', '_new'))
print("\nSchema Comparison (All columns):")
print(comp_df.to_string())

con.close()
