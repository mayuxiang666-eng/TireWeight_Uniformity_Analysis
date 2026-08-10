import duckdb

DATA_PATH = "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
conn = duckdb.connect()

def get_sankey_data(article10, indicator='rfpp', target_date=None):
    where_parts = ["article10 = ?"]
    params = [article10]
    if target_date:
        where_parts.append("ct_shiftdate::DATE = ?::DATE")
        params.append(target_date)
    
    where_clause = "WHERE " + " AND ".join(where_parts)
    
    # Selected workcenters in logical production sequence:
    # 1. Semi-finished components: Inner Liner, Bead, Sidewall, Tread, First Breaker, Second Breaker, First Ply, Cap Ply 1
    # 2. Building / 成型: TB
    # 3. Curing / 硫化: TG
    # 4. Final Testing / 终检: TU, CT
    
    stages = [
        ("内衬", "inner_liner_workcenter"),
        ("胎圈", "bead_workcenter"),
        ("胎侧", "sidewall_workcenter"),
        ("胎面", "tread_workcenter"),
        ("带束层1", "first_breaker_workcenter"),
        ("带束层2", "second_breaker_workcenter"),
        ("帘布层", "first_ply_workcenter"),
        ("冠带层", "wound_cap_ply1_workcenter"),
        ("成型TB", "tb_first_workcenter"),
        ("硫化TG", "tg_first_workcenter"),
        ("均匀性TU", "tu_first_workcenter"),
        ("终检CT", "ct_workcenter")
    ]
    
    # We can group pairs of adjacent stages to form links
    # Standard 4-level process flow:
    # Level 1: 部件准备 (Inner Liner, Bead, Sidewall, Tread, Breaker, Ply) -> Level 2: 成型 (TB)
    # Level 2: 成型 (TB) -> Level 3: 硫化 (TG)
    # Level 3: 硫化 (TG) -> Level 4: 均匀性 (TU)
    # Level 4: 均匀性 (TU) -> Level 5: 终检 (CT)
    
    # Let's verify link volumes for adjacent stage pairs
    pairs = [
        ("tread_workcenter", "tb_first_workcenter"),
        ("bead_workcenter", "tb_first_workcenter"),
        ("inner_liner_workcenter", "tb_first_workcenter"),
        ("sidewall_workcenter", "tb_first_workcenter"),
        ("first_breaker_workcenter", "tb_first_workcenter"),
        ("first_ply_workcenter", "tb_first_workcenter"),
        ("tb_first_workcenter", "tg_first_workcenter"),
        ("tg_first_workcenter", "tu_first_workcenter"),
        ("tu_first_workcenter", "ct_workcenter"),
    ]
    
    links = []
    for src_col, dst_col in pairs:
        sql = f"""
            SELECT 
                CAST({src_col} AS VARCHAR) as src,
                CAST({dst_col} AS VARCHAR) as dst,
                COUNT(*) as value,
                AVG(TRY_CAST({'rfppwc_first' if indicator=='rfpp' else 'rfh1wc_first'} AS DOUBLE)) as avg_val,
                STDDEV(TRY_CAST({'rfppwc_first' if indicator=='rfpp' else 'rfh1wc_first'} AS DOUBLE)) as std_val
            FROM read_parquet('{DATA_PATH}')
            {where_clause} AND {src_col} IS NOT NULL AND {dst_col} IS NOT NULL
            GROUP BY 1, 2
        """
        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            links.append({
                "source": f"{src_col[:3].upper()}_{r[0]}",
                "target": f"{dst_col[:2].upper()}_{r[1]}",
                "value": r[2],
                "avg": r[3],
                "std": r[4]
            })
            
    print(f"Total links generated: {len(links)}")
    print("Sample links:", links[:5])

get_sankey_data('0312423000', 'rfpp')
