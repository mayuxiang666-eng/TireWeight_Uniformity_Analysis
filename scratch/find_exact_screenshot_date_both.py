import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE clean_yield AS SELECT * FROM read_parquet('d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet')")

for indicator in ['rfpp', 'rfh1']:
    indicator_col = "rfppwc_first" if indicator == "rfpp" else "rfh1wc_first"
    sql = f"""
        SELECT 
            ct_shiftdate::DATE as date,
            COUNT(*) as spec_n,
            AVG(TRY_CAST({indicator_col} AS DOUBLE)) as spec_avg,
            STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) as spec_std
        FROM clean_yield 
        WHERE article10 = '0315626000' AND ct_workcenter = 'CU704'
        GROUP BY date
        ORDER BY date
    """
    dates_list = con.execute(sql).fetchall()

    for d, spec_n, spec_avg, spec_std in dates_list:
        if spec_n == 5:
            # Check all count for this machine on this date
            all_n = con.execute(f"SELECT COUNT(*) FROM clean_yield WHERE ct_shiftdate::DATE = '{d}' AND ct_workcenter = 'CU704'").fetchone()[0]
            spec_std_val = spec_std if spec_std is not None else 0.0
            avg_3s = spec_avg + 3.0 * spec_std_val
            
            # Check all stats
            all_avg = con.execute(f"SELECT AVG(TRY_CAST({indicator_col} AS DOUBLE)) FROM clean_yield WHERE ct_shiftdate::DATE = '{d}' AND ct_workcenter = 'CU704'").fetchone()[0]
            all_std = con.execute(f"SELECT STDDEV(TRY_CAST({indicator_col} AS DOUBLE)) FROM clean_yield WHERE ct_shiftdate::DATE = '{d}' AND ct_workcenter = 'CU704'").fetchone()[0]
            all_std_val = all_std if all_std is not None else 0.0
            all_avg_3s = all_avg + 3.0 * all_std_val
            
            print(f"Indicator: {indicator}, Date: {d}, spec_n: {spec_n}, spec_avg+3sigma: {avg_3s:.3f}, all_n: {all_n}, all_avg+3sigma: {all_avg_3s:.3f}")
