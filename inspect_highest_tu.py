import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

def get_highest_tu_path(article10, indicator='rfpp', target_date=None):
    where_parts = ["article10 = ?"]
    params = [article10]
    if target_date:
        where_parts.append("ct_shiftdate::DATE = ?::DATE")
        params.append(target_date)
        
    where_clause = "WHERE " + " AND ".join(where_parts)
    ind_col = 'rfppwc_first' if indicator == 'rfpp' else 'rfh1wc_first'
    
    # Selected key workcenters in manufacturing flow order:
    # Tread, Bead, Inner Liner, Breaker 1 -> TB (Building) -> TG (Curing) -> TU (Uniformity)
    
    # First, find the TU machine for this article with the highest (avg + 3*std)
    tu_sql = f"""
        SELECT 
            tu_first_workcenter,
            AVG(TRY_CAST({ind_col} AS DOUBLE)) as avg_v,
            STDDEV(TRY_CAST({ind_col} AS DOUBLE)) as std_v,
            AVG(TRY_CAST({ind_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({ind_col} AS DOUBLE)), 0.0) as val_3sigma,
            COUNT(*) as n
        FROM read_parquet('{DATA_PATH}')
        {where_clause} AND tu_first_workcenter IS NOT NULL
        GROUP BY 1
        ORDER BY val_3sigma DESC
    """
    tu_rows = conn.execute(tu_sql, params).fetchall()
    print("TU Ranking:")
    for r in tu_rows:
        print("  TU Machine:", r[0], "avg+3sigma:", r[3], "n:", r[4])
        
    if tu_rows:
        max_tu_machine = tu_rows[0][0]
        print(f"\nHighest TU machine is: {max_tu_machine}")
        
        # Now find the most frequent path leading to/through this highest TU machine
        flow_sql = f"""
            SELECT 
                tread_workcenter,
                bead_workcenter,
                inner_liner_workcenter,
                first_breaker_workcenter,
                tb_first_workcenter,
                tg_first_workcenter,
                tu_first_workcenter,
                ct_workcenter,
                COUNT(*) as path_count,
                AVG(TRY_CAST({ind_col} AS DOUBLE)) + 3.0 * COALESCE(STDDEV(TRY_CAST({ind_col} AS DOUBLE)), 0.0) as path_3sigma
            FROM read_parquet('{DATA_PATH}')
            {where_clause} AND tu_first_workcenter = ?
            GROUP BY 1,2,3,4,5,6,7,8
            ORDER BY path_count DESC
            LIMIT 1
        """
        top_path = conn.execute(flow_sql, params + [max_tu_machine]).fetchone()
        print("\nTop path for max TU machine:", top_path)

get_highest_tu_path('0312423000', 'rfpp')
