import os
import duckdb
import pandas as pd

_BASE = os.path.dirname(__file__)
data_path = os.path.normpath(os.path.join(_BASE, '..', 'src', 'yield_flat_table_0713cleaned.parquet')).replace('\\', '/')

print(f"Reading from: {data_path}")

con = duckdb.connect()

# 1. Row count
row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{data_path}')").fetchone()[0]
print(f"Total Rows: {row_count}")

# 2. Get column types and null counts
# Let's describe the parquet file structure
schema_df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{data_path}')").df()
print("Schema:")
print(schema_df.to_string())

# For each column, we want to know the number of null values and basic stats.
# Since there can be many columns, let's construct a query to get non-null counts.
cols = schema_df['column_name'].tolist()

# Let's get the first few rows
sample_df = con.execute(f"SELECT * FROM read_parquet('{data_path}') LIMIT 5").df()
print("\nSample Data:")
print(sample_df.to_string())

# Let's count null values for each column
null_queries = [f"SUM(CASE WHEN \"{col}\" IS NULL THEN 1 ELSE 0 END) AS \"{col}_null\"" for col in cols]
null_sql = f"SELECT {', '.join(null_queries)} FROM read_parquet('{data_path}')"
null_counts = con.execute(null_sql).df().iloc[0]

# Let's also get unique count for each column
unique_queries = [f"COUNT(DISTINCT \"{col}\") AS \"{col}_unique\"" for col in cols]
unique_sql = f"SELECT {', '.join(unique_queries)} FROM read_parquet('{data_path}')"
unique_counts = con.execute(unique_sql).df().iloc[0]

# Combine details
details = []
for col in cols:
    col_type = schema_df[schema_df['column_name'] == col]['column_type'].values[0]
    null_val = int(null_counts[f"{col}_null"])
    uniq_val = int(unique_counts[f"{col}_unique"])
    non_null_val = row_count - null_val
    null_pct = (null_val / row_count) * 100
    
    # Try to get min/max for non-complex types
    min_val = None
    max_val = None
    if col_type in ['VARCHAR', 'BIGINT', 'DOUBLE', 'INTEGER', 'TIMESTAMP', 'DATE']:
        try:
            min_max = con.execute(f"SELECT MIN(\"{col}\"), MAX(\"{col}\") FROM read_parquet('{data_path}')").fetchone()
            min_val = min_max[0]
            max_val = min_max[1]
        except Exception as e:
            pass
            
    details.append({
        'Column Name': col,
        'Type': col_type,
        'Non-Null Count': non_null_val,
        'Null Count': null_val,
        'Null %': f"{null_pct:.2f}%",
        'Unique Count': uniq_val,
        'Min Value': min_val,
        'Max Value': max_val
    })

details_df = pd.DataFrame(details)
print("\nDetailed Columns Information:")
print(details_df.to_string())

# Save to a json or csv in scratch to inspect
details_df.to_csv(os.path.join(_BASE, 'schema_details.csv'), index=False)
sample_df.to_csv(os.path.join(_BASE, 'sample_data.csv'), index=False)

con.close()
