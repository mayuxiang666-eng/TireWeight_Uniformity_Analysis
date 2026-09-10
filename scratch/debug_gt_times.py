import duckdb

con = duckdb.connect()
yield_p = 'd:/Ava/untitled1/untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet'

print("GT production timestamps for TB252 between 08:00 and 13:00:")
df = con.execute(f"""
    SELECT barcode, gt_loc_timestamp, tu_first_loc_timestamp
    FROM read_parquet('{yield_p}')
    WHERE gt_workcenter IN ('TB152', 'TB252')
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) >= '2026-08-17 08:00:00'::TIMESTAMP
      AND TRY_CAST(gt_loc_timestamp AS TIMESTAMP) <= '2026-08-17 13:00:00'::TIMESTAMP
    ORDER BY TRY_CAST(gt_loc_timestamp AS TIMESTAMP) ASC
""").df()

print("Total GT count between 08:00 and 13:00:", len(df))
print(df.to_string())
