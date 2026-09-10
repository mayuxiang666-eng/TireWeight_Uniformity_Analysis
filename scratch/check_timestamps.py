import duckdb

con = duckdb.connect()
parquet_path = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{parquet_path}')")
df = con.execute("""
    SELECT 
        gt_workcenter,
        article10,
        tu_first_shift_date,
        gt_loc_timestamp,
        ct_loc_timestamp
    FROM cy
    WHERE gt_workcenter = 'TB224' AND article10 = '0312053000'
    LIMIT 5
""").df()
print(df)
