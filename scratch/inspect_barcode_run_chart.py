import duckdb

con = duckdb.connect()
p = "untitled1_v2/backend/data/yield_flat_table_joined_100_cleaned.parquet"
con.execute(f"CREATE TABLE cy AS SELECT * FROM read_parquet('{p}')")

sample = con.execute("""
    SELECT 
        barcode,
        article10,
        tu_first_shift_date,
        gt_loc_timestamp,
        rfppwc_first,
        rfh1wc_first,
        cony_first,
        tire_weight_actual_first,
        gt_workcenter,
        tu_first_workcenter,
        standard_rfpp,
        "group"
    FROM cy
    WHERE article10 = '0312053000'
      AND tu_first_shift_date = '2026-08-10'
    ORDER BY gt_loc_timestamp ASC
    LIMIT 10
""").df()
print(sample.to_string())
