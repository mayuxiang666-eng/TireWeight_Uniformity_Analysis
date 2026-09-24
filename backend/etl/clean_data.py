import os
import duckdb

def get_data_dir():
    etl_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(etl_dir)
    candidates = [
        os.path.join(root_dir, "backend", "data"),
        os.path.join(etl_dir, "data"),
        os.path.join(os.getcwd(), "backend", "data"),
        os.path.join(root_dir, "data"),
        os.path.join(os.getcwd(), "data"),
    ]
    for p in candidates:
        p_abs = os.path.abspath(p)
        if os.path.exists(os.path.join(p_abs, "yield_flat_table_joined_100.parquet")) or \
           os.path.exists(os.path.join(p_abs, "yield_flat_table_joined_100_cleaned.parquet")):
            return p_abs
    target = os.path.abspath(os.path.join(root_dir, "backend", "data"))
    os.makedirs(target, exist_ok=True)
    return target


def clean_main(input_path=None, output_path=None, recipes_path=None):
    data_dir = get_data_dir()
    
    if input_path is None:
        input_path = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    if output_path is None:
        output_path = os.path.join(data_dir, "yield_flat_table_joined_100_cleaned.parquet")
    if recipes_path is None:
        recipes_path = os.path.join(data_dir, "Recipes.csv")
        
    print("--- 步骤 1: 检查原始 Parquet 数据集 ---")
    if not os.path.exists(input_path):
        print(f"[Error] 未找到输入文件: {input_path}。")
        return False
        
    con = duckdb.connect()
    # 启用磁盘溢出缓冲与内存保护，杜绝 Out of Memory Allocation failure
    temp_dir = os.path.join(data_dir, "duckdb_tmp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_dir_sql = temp_dir.replace("\\", "/")
    con.execute(f"PRAGMA temp_directory='{temp_dir_sql}'")
    con.execute("PRAGMA max_memory='4GB'")
    con.execute("PRAGMA threads=4")
    
    try:
        input_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{input_path}')").fetchone()[0]
        print(f"原始数据集大小: {input_count:,} 行。")

        has_recipes = os.path.exists(recipes_path)
        if has_recipes:
            print("\n--- 步骤 1.2: 基于 Recipes.csv 预编译配方全量指标映射表 (RF/LF/CON/PLY/BALW/TG) ---")
            try:
                con.execute(f"""
                    CREATE OR REPLACE TABLE recipes_limits AS
                    SELECT 
                        LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') as art10_clean,
                        CASE 
                            WHEN TRY_CAST(RFPP_T1 AS DOUBLE) = 1050 THEN 10.5
                            WHEN TRY_CAST(RFPP_T1 AS DOUBLE) = 5 THEN 5.0
                            WHEN TRY_CAST(RFPP_T1 AS DOUBLE) >= 30 AND TRY_CAST(RFPP_T1 AS DOUBLE) < 250 
                                 AND TRY_CAST(RFPP_T1 AS DOUBLE) NOT IN (960, 990) 
                            THEN TRY_CAST(RFPP_T1 AS DOUBLE) / 10.0 
                            ELSE 10.5 
                        END as rfpp_val,
                        CASE 
                            WHEN TRY_CAST(RFH1_T1 AS DOUBLE) = 750 THEN 7.5
                            WHEN TRY_CAST(RFH1_T1 AS DOUBLE) = 5 THEN 5.0
                            WHEN TRY_CAST(RFH1_T1 AS DOUBLE) >= 30 AND TRY_CAST(RFH1_T1 AS DOUBLE) < 180 
                                 AND TRY_CAST(RFH1_T1 AS DOUBLE) NOT IN (960, 990) 
                            THEN TRY_CAST(RFH1_T1 AS DOUBLE) / 10.0 
                            ELSE 7.5 
                        END as rfh1_val,
                        CASE 
                            WHEN TRY_CAST(RFH2_T1 AS DOUBLE) >= 30 AND TRY_CAST(RFH2_T1 AS DOUBLE) < 100 
                            THEN TRY_CAST(RFH2_T1 AS DOUBLE) / 10.0 
                            ELSE NULL 
                        END as rfh2_val,
                        CASE 
                            WHEN TRY_CAST(LFPP_T1 AS DOUBLE) >= 30 AND TRY_CAST(LFPP_T1 AS DOUBLE) < 200 
                                 AND TRY_CAST(LFPP_T1 AS DOUBLE) NOT IN (960, 990) 
                            THEN TRY_CAST(LFPP_T1 AS DOUBLE) / 10.0 
                            ELSE NULL 
                        END as lfpp_val,
                        CASE 
                            WHEN TRY_CAST(LFH1_T1 AS DOUBLE) >= 30 AND TRY_CAST(LFH1_T1 AS DOUBLE) < 100 
                                 AND TRY_CAST(LFH1_T1 AS DOUBLE) NOT IN (960, 990) 
                            THEN TRY_CAST(LFH1_T1 AS DOUBLE) / 10.0 
                            ELSE NULL 
                        END as lfh1_val,
                        CASE 
                            WHEN ABS(TRY_CAST(CONU_T1 AS DOUBLE)) >= 10 AND ABS(TRY_CAST(CONU_T1 AS DOUBLE)) < 200 
                                 AND ABS(TRY_CAST(CONU_T1 AS DOUBLE)) NOT IN (960, 990) 
                            THEN TRY_CAST(CONU_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as conu_val,
                        CASE 
                            WHEN ABS(TRY_CAST(CONL_T1 AS DOUBLE)) >= 10 AND ABS(TRY_CAST(CONL_T1 AS DOUBLE)) < 200 
                                 AND ABS(TRY_CAST(CONL_T1 AS DOUBLE)) NOT IN (960, 990) 
                            THEN TRY_CAST(CONL_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as conl_val,
                        CASE 
                            WHEN TRY_CAST(PLYU_T1 AS DOUBLE) >= 100 AND TRY_CAST(PLYU_T1 AS DOUBLE) < 600 
                                 AND TRY_CAST(PLYU_T1 AS DOUBLE) NOT IN (960, 9980, 9990) 
                            THEN TRY_CAST(PLYU_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as plyu_val,
                        CASE 
                            WHEN TRY_CAST(PLYL_T1 AS DOUBLE) >= 20 AND TRY_CAST(PLYL_T1 AS DOUBLE) < 500 
                                 AND TRY_CAST(PLYL_T1 AS DOUBLE) NOT IN (960, 990, 9960, 9980, -9980) 
                            THEN TRY_CAST(PLYL_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as plyl_val,
                        CASE 
                            WHEN TRY_CAST(TBALW_T1 AS DOUBLE) >= 20 AND TRY_CAST(TBALW_T1 AS DOUBLE) < 150 
                                 AND TRY_CAST(TBALW_T1 AS DOUBLE) NOT IN (0.1, 996) 
                            THEN TRY_CAST(TBALW_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as tbalw_val,
                        CASE 
                            WHEN TRY_CAST(BBALW_T1 AS DOUBLE) >= 20 AND TRY_CAST(BBALW_T1 AS DOUBLE) < 150 
                                 AND TRY_CAST(BBALW_T1 AS DOUBLE) NOT IN (0.1, 996) 
                            THEN TRY_CAST(BBALW_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as bbalw_val,
                        CASE 
                            WHEN TRY_CAST(SBALW_T1 AS DOUBLE) >= 20 AND TRY_CAST(SBALW_T1 AS DOUBLE) < 100 
                                 AND TRY_CAST(SBALW_T1 AS DOUBLE) != 996 
                            THEN TRY_CAST(SBALW_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as sbalw_val,
                        CASE 
                            WHEN TRY_CAST(BULS_T1 AS DOUBLE) >= 0.3 AND TRY_CAST(BULS_T1 AS DOUBLE) <= 2.5 
                                 AND TRY_CAST(BULS_T1 AS DOUBLE) NOT IN (96, 99, 996) 
                            THEN TRY_CAST(BULS_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as buls_val,
                        CASE 
                            WHEN TRY_CAST(DEPS_T1 AS DOUBLE) >= 0.3 AND TRY_CAST(DEPS_T1 AS DOUBLE) <= 2.5 
                                 AND TRY_CAST(DEPS_T1 AS DOUBLE) NOT IN (96, 99, 996) 
                            THEN TRY_CAST(DEPS_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as deps_val,
                        CASE 
                            WHEN TRY_CAST(LROH1_T1 AS DOUBLE) >= 0.3 AND TRY_CAST(LROH1_T1 AS DOUBLE) <= 2.5 
                                 AND TRY_CAST(LROH1_T1 AS DOUBLE) NOT IN (96, 99, 996) 
                            THEN TRY_CAST(LROH1_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as lroh1_val,
                        CASE 
                            WHEN TRY_CAST(RROM_T1 AS DOUBLE) >= 0.3 AND TRY_CAST(RROM_T1 AS DOUBLE) <= 2.5 
                                 AND TRY_CAST(RROM_T1 AS DOUBLE) NOT IN (96, 99, 996) 
                            THEN TRY_CAST(RROM_T1 AS DOUBLE) 
                            ELSE NULL 
                        END as rrom_val
                    FROM read_csv('{recipes_path}', header=true, all_varchar=true)
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') 
                        ORDER BY TRY_CAST(RELEASE_TIME AS TIMESTAMP) DESC NULLS LAST, ART10
                    ) = 1;
                """)
                print("  配方全量指标映射表预编译就绪。")
            except Exception as e:
                print(f"[Warning] 配方表解析异常 ({e})，将保持原物理标准值。")
                has_recipes = False
        else:
            print(f"[Warning] 未找到配方表: {recipes_path}，跳过标准上限值检查与更新。")

        print("\n--- 步骤 2: 动态检查并构建列过滤方案 ---")
        existing_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{input_path}') LIMIT 1").fetchall()]
        
        art_col = "article10_intended" if "article10_intended" in existing_cols else "article10"
        art10_alias_expr = f", t.{art_col} AS article10" if (art_col != "article10" and "article10" not in existing_cols) else ""
        
        # 需剔除的冗余字段及将被重新派生计算的字段
        drop_candidates = [
            "articleno", "articleno_7", "articlevariant", "branddesignation", "loadindexsingle", "speedsymbol", "ssr",
            "yt_workcenter", "ssr_insert_bead_cushion_workcenter", "ssr_insert_bead_cushion_lot",
            "bead_reinforcement_workcenter", "bead_reinforcement_lot", "second_ply_lot", "second_ply_workcenter",
            "standard_rfpp", "standard_rfh1", "standard_rfh2", "standard_lfpp", "standard_lfh1",
            "conny_usl", "conny_lsl", "plys_usl", "plys_lsl", "tbalw_usl", "bbalw_usl", "sbalw_usl",
            "tbul_usl", "bbul_usl", "tdep_usl", "bdep_usl", "tlro_usl", "blro_usl", "crro_usl",
            "is_anomaly_tu", "is_anomaly_tg", "is_anomaly_tb", "is_anomaly_overall",
            "anomaly_count_tu", "anomaly_count_tg", "anomaly_count_tb", "anomaly_count_total", "anomaly_sources"
        ]
        
        # TG 几何尺寸测量字段（需在 t.* 中排除并乘以 1000 转换为 mm 存储）
        tg_measure_cols = ["tbul_first", "bbul_first", "tdep_first", "bdep_first", "tlro_first", "blro_first", "crro_first"]
        
        # 17 项原生 Grade 字段（需在 t.* 中排除并进行 UPPER(TRIM) 大小写规范化）
        grade_17_cols = [
            "grade_rfppwc_first", "grade_rfh1wc_first", "grade_rfh2wc_first", "grade_lfppwc_first", "grade_lfh1wc_first", "grade_cony_first", "grade_plys_first",
            "grade_tbul_first", "grade_bbul_first", "grade_tdep_first", "grade_bdep_first", "grade_tlro_first", "grade_blro_first", "grade_crro_first",
            "grade_tbalw_first", "grade_bbalw_first", "grade_sbalw_first"
        ]

        all_excludes = list(set([c for c in drop_candidates + tg_measure_cols + grade_17_cols if c in existing_cols]))
        exclude_str = f"EXCLUDE ({', '.join(all_excludes)})" if all_excludes else ""
        print(f"已动态排除冗余/重算字段: {all_excludes}")

        print("\n--- 步骤 3: DuckDB 原生流式清洗与原子输出 (Out-of-Core Execution) ---")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = output_path + ".cleaning.tmp"

        # 辅助宏定义： Grade 表达式（若在输入表中存在则引用，否则默认 'A'）
        def g_expr(col_name):
            if col_name in existing_cols:
                return f"UPPER(TRIM(CAST(t.{col_name} AS VARCHAR)))"
            return "'A'"

        # Grade 标准化表达式
        grade_select_exprs = []
        for gc in grade_17_cols:
            if gc in existing_cols:
                grade_select_exprs.append(f"NULLIF(UPPER(TRIM(CAST(t.{gc} AS VARCHAR))), '') AS {gc}")
            else:
                grade_select_exprs.append(f"NULL::VARCHAR AS {gc}")
        grade_select_sql = ",\n                        ".join(grade_select_exprs)

        # TU / TG / TB 判定表达式
        tu_anomaly_expr = f"""(
            ({g_expr('grade_rfppwc_first')} != 'A' AND {g_expr('grade_rfppwc_first')} IS NOT NULL AND {g_expr('grade_rfppwc_first')} != '') OR
            ({g_expr('grade_rfh1wc_first')} != 'A' AND {g_expr('grade_rfh1wc_first')} IS NOT NULL AND {g_expr('grade_rfh1wc_first')} != '') OR
            ({g_expr('grade_rfh2wc_first')} != 'A' AND {g_expr('grade_rfh2wc_first')} IS NOT NULL AND {g_expr('grade_rfh2wc_first')} != '') OR
            ({g_expr('grade_lfppwc_first')} != 'A' AND {g_expr('grade_lfppwc_first')} IS NOT NULL AND {g_expr('grade_lfppwc_first')} != '') OR
            ({g_expr('grade_lfh1wc_first')} != 'A' AND {g_expr('grade_lfh1wc_first')} IS NOT NULL AND {g_expr('grade_lfh1wc_first')} != '') OR
            ({g_expr('grade_cony_first')}   != 'A' AND {g_expr('grade_cony_first')} IS NOT NULL   AND {g_expr('grade_cony_first')} != '') OR
            ({g_expr('grade_plys_first')}   != 'A' AND {g_expr('grade_plys_first')} IS NOT NULL   AND {g_expr('grade_plys_first')} != '')
        )"""

        tg_anomaly_expr = f"""(
            ({g_expr('grade_tbul_first')} != 'A' AND {g_expr('grade_tbul_first')} IS NOT NULL AND {g_expr('grade_tbul_first')} != '') OR
            ({g_expr('grade_bbul_first')} != 'A' AND {g_expr('grade_bbul_first')} IS NOT NULL AND {g_expr('grade_bbul_first')} != '') OR
            ({g_expr('grade_tdep_first')} != 'A' AND {g_expr('grade_tdep_first')} IS NOT NULL AND {g_expr('grade_tdep_first')} != '') OR
            ({g_expr('grade_bdep_first')} != 'A' AND {g_expr('grade_bdep_first')} IS NOT NULL AND {g_expr('grade_bdep_first')} != '') OR
            ({g_expr('grade_tlro_first')} != 'A' AND {g_expr('grade_tlro_first')} IS NOT NULL AND {g_expr('grade_tlro_first')} != '') OR
            ({g_expr('grade_blro_first')} != 'A' AND {g_expr('grade_blro_first')} IS NOT NULL AND {g_expr('grade_blro_first')} != '') OR
            ({g_expr('grade_crro_first')} != 'A' AND {g_expr('grade_crro_first')} IS NOT NULL AND {g_expr('grade_crro_first')} != '')
        )"""

        tb_anomaly_expr = f"""(
            ({g_expr('grade_tbalw_first')} != 'A' AND {g_expr('grade_tbalw_first')} IS NOT NULL AND {g_expr('grade_tbalw_first')} != '') OR
            ({g_expr('grade_bbalw_first')} != 'A' AND {g_expr('grade_bbalw_first')} IS NOT NULL AND {g_expr('grade_bbalw_first')} != '') OR
            ({g_expr('grade_sbalw_first')} != 'A' AND {g_expr('grade_sbalw_first')} IS NOT NULL AND {g_expr('grade_sbalw_first')} != '')
        )"""

        # TG 测量值乘以 1000 转换为毫米 (mm)
        tg_mm_select_sql = """
                        ROUND(TRY_CAST(t.tbul_first AS DOUBLE) * 1000.0, 4) AS tbul_first,
                        ROUND(TRY_CAST(t.bbul_first AS DOUBLE) * 1000.0, 4) AS bbul_first,
                        ROUND(TRY_CAST(t.tdep_first AS DOUBLE) * 1000.0, 4) AS tdep_first,
                        ROUND(TRY_CAST(t.bdep_first AS DOUBLE) * 1000.0, 4) AS bdep_first,
                        ROUND(TRY_CAST(t.tlro_first AS DOUBLE) * 1000.0, 4) AS tlro_first,
                        ROUND(TRY_CAST(t.blro_first AS DOUBLE) * 1000.0, 4) AS blro_first,
                        ROUND(TRY_CAST(t.crro_first AS DOUBLE) * 1000.0, 4) AS crro_first
        """ if all(c in existing_cols for c in tg_measure_cols) else """
                        t.tbul_first, t.bbul_first, t.tdep_first, t.bdep_first, t.tlro_first, t.blro_first, t.crro_first
        """

        clean_sql = f"""
            COPY (
                WITH base_step1 AS (
                    SELECT 
                        t.* {exclude_str}{art10_alias_expr},
                        
                        -- TG 测量值换算为毫米 (mm)
                        {tg_mm_select_sql},

                        -- 17 项原生 Grade 字段大小写规整
                        {grade_select_sql},

                        -- 100% 优先匹配 Recipes.csv 控制限 (解除时间限制)
                        {"COALESCE(rl.rfpp_val, 10.5) AS standard_rfpp," if has_recipes else "10.5 AS standard_rfpp,"}
                        {"COALESCE(rl.rfh1_val, 7.5)  AS standard_rfh1," if has_recipes else "7.5 AS standard_rfh1,"}
                        {"rl.rfh2_val  AS standard_rfh2," if has_recipes else "NULL::DOUBLE AS standard_rfh2,"}
                        {"rl.lfpp_val  AS standard_lfpp," if has_recipes else "NULL::DOUBLE AS standard_lfpp,"}
                        {"rl.lfh1_val  AS standard_lfh1," if has_recipes else "NULL::DOUBLE AS standard_lfh1,"}
                        {"rl.conu_val  AS conny_usl," if has_recipes else "NULL::DOUBLE AS conny_usl,"}
                        {"rl.conl_val  AS conny_lsl," if has_recipes else "NULL::DOUBLE AS conny_lsl,"}
                        {"rl.plyu_val  AS plys_usl," if has_recipes else "NULL::DOUBLE AS plys_usl,"}
                        {"rl.plyl_val  AS plys_lsl," if has_recipes else "NULL::DOUBLE AS plys_lsl,"}
                        {"rl.tbalw_val AS tbalw_usl," if has_recipes else "NULL::DOUBLE AS tbalw_usl,"}
                        {"rl.bbalw_val AS bbalw_usl," if has_recipes else "NULL::DOUBLE AS bbalw_usl,"}
                        {"rl.sbalw_val AS sbalw_usl," if has_recipes else "NULL::DOUBLE AS sbalw_usl,"}
                        {"rl.buls_val  AS tbul_usl," if has_recipes else "NULL::DOUBLE AS tbul_usl,"}
                        {"rl.buls_val  AS bbul_usl," if has_recipes else "NULL::DOUBLE AS bbul_usl,"}
                        {"rl.deps_val  AS tdep_usl," if has_recipes else "NULL::DOUBLE AS tdep_usl,"}
                        {"rl.deps_val  AS bdep_usl," if has_recipes else "NULL::DOUBLE AS bdep_usl,"}
                        {"rl.lroh1_val AS tlro_usl," if has_recipes else "NULL::DOUBLE AS tlro_usl,"}
                        {"rl.lroh1_val AS blro_usl," if has_recipes else "NULL::DOUBLE AS blro_usl,"}
                        {"rl.rrom_val  AS crro_usl," if has_recipes else "NULL::DOUBLE AS crro_usl,"}

                        -- 工序异常判定 (0 / 1)
                        CASE WHEN {tu_anomaly_expr} THEN 1 ELSE 0 END AS is_anomaly_tu,
                        CASE WHEN {tg_anomaly_expr} THEN 1 ELSE 0 END AS is_anomaly_tg,
                        CASE WHEN {tb_anomaly_expr} THEN 1 ELSE 0 END AS is_anomaly_tb,

                        -- 各工序超差指标个数计数
                        (
                            (CASE WHEN {g_expr('grade_rfppwc_first')} != 'A' AND {g_expr('grade_rfppwc_first')} IS NOT NULL AND {g_expr('grade_rfppwc_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_rfh1wc_first')} != 'A' AND {g_expr('grade_rfh1wc_first')} IS NOT NULL AND {g_expr('grade_rfh1wc_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_rfh2wc_first')} != 'A' AND {g_expr('grade_rfh2wc_first')} IS NOT NULL AND {g_expr('grade_rfh2wc_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_lfppwc_first')} != 'A' AND {g_expr('grade_lfppwc_first')} IS NOT NULL AND {g_expr('grade_lfppwc_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_lfh1wc_first')} != 'A' AND {g_expr('grade_lfh1wc_first')} IS NOT NULL AND {g_expr('grade_lfh1wc_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_cony_first')}   != 'A' AND {g_expr('grade_cony_first')} IS NOT NULL   AND {g_expr('grade_cony_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_plys_first')}   != 'A' AND {g_expr('grade_plys_first')} IS NOT NULL   AND {g_expr('grade_plys_first')} != '' THEN 1 ELSE 0 END)
                        ) AS anomaly_count_tu,

                        (
                            (CASE WHEN {g_expr('grade_tbul_first')} != 'A' AND {g_expr('grade_tbul_first')} IS NOT NULL AND {g_expr('grade_tbul_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_bbul_first')} != 'A' AND {g_expr('grade_bbul_first')} IS NOT NULL AND {g_expr('grade_bbul_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_tdep_first')} != 'A' AND {g_expr('grade_tdep_first')} IS NOT NULL AND {g_expr('grade_tdep_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_bdep_first')} != 'A' AND {g_expr('grade_bdep_first')} IS NOT NULL AND {g_expr('grade_bdep_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_tlro_first')} != 'A' AND {g_expr('grade_tlro_first')} IS NOT NULL AND {g_expr('grade_tlro_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_blro_first')} != 'A' AND {g_expr('grade_blro_first')} IS NOT NULL AND {g_expr('grade_blro_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_crro_first')} != 'A' AND {g_expr('grade_crro_first')} IS NOT NULL AND {g_expr('grade_crro_first')} != '' THEN 1 ELSE 0 END)
                        ) AS anomaly_count_tg,

                        (
                            (CASE WHEN {g_expr('grade_tbalw_first')} != 'A' AND {g_expr('grade_tbalw_first')} IS NOT NULL AND {g_expr('grade_tbalw_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_bbalw_first')} != 'A' AND {g_expr('grade_bbalw_first')} IS NOT NULL AND {g_expr('grade_bbalw_first')} != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN {g_expr('grade_sbalw_first')} != 'A' AND {g_expr('grade_sbalw_first')} IS NOT NULL AND {g_expr('grade_sbalw_first')} != '' THEN 1 ELSE 0 END)
                        ) AS anomaly_count_tb

                    FROM read_parquet('{input_path}') t
                    {"LEFT JOIN recipes_limits rl ON LPAD(TRIM(CAST(t." + art_col + " AS VARCHAR)), 10, '0') = rl.art10_clean" if has_recipes else ""}
                    WHERE t.{art_col} IS NOT NULL 
                      AND TRIM(CAST(t.{art_col} AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NULL')
                )
                SELECT 
                    b.*,
                    -- 全局总异常判定 (只要任一工段异常则为 1)
                    CASE WHEN (b.is_anomaly_tu = 1 OR b.is_anomaly_tg = 1 OR b.is_anomaly_tb = 1) THEN 1 ELSE 0 END AS is_anomaly_overall,
                    
                    -- 总超差项数统计
                    (b.anomaly_count_tu + b.anomaly_count_tg + b.anomaly_count_tb) AS anomaly_count_total,

                    -- 异常来源标签字符串
                    CASE 
                        WHEN b.is_anomaly_tu = 1 AND b.is_anomaly_tg = 1 AND b.is_anomaly_tb = 1 THEN 'TU+TG+TB'
                        WHEN b.is_anomaly_tu = 1 AND b.is_anomaly_tg = 1 THEN 'TU+TG'
                        WHEN b.is_anomaly_tu = 1 AND b.is_anomaly_tb = 1 THEN 'TU+TB'
                        WHEN b.is_anomaly_tg = 1 AND b.is_anomaly_tb = 1 THEN 'TG+TB'
                        WHEN b.is_anomaly_tu = 1 THEN 'TU'
                        WHEN b.is_anomaly_tg = 1 THEN 'TG'
                        WHEN b.is_anomaly_tb = 1 THEN 'TB'
                        ELSE 'NORMAL'
                    END AS anomaly_sources
                FROM base_step1 b
            ) TO '{tmp_path}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
        """

        con.execute(clean_sql)
        
        final_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{tmp_path}')").fetchone()[0]
        final_cols = len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tmp_path}') LIMIT 1").fetchall())
        
        os.replace(tmp_path, output_path)
        print(f"[Success] DuckDB 流式清洗完成！终态保存至: {output_path}")
        print(f"最终清洗数据集大小: {final_rows:,} 行, {final_cols} 列。")

        # 同步镜像副本至备用 data 目录 (仅正式清洗表同步)
        if not output_path.endswith(".tmp"):
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for alt_dir in [os.path.join(root_dir, "data"), os.path.join(root_dir, "backend", "data")]:
                if os.path.isdir(alt_dir) and os.path.abspath(alt_dir) != os.path.abspath(os.path.dirname(output_path)):
                    try:
                        import shutil
                        alt_output = os.path.join(alt_dir, os.path.basename(output_path))
                        shutil.copy2(output_path, alt_output)
                        print(f"[Mirror] 同步清洗镜像至: {alt_output}")
                    except Exception:
                        pass

        return True

    except Exception as e:
        print(f"[Error] DuckDB 清洗流程异常: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False
    finally:
        con.close()


if __name__ == "__main__":
    clean_main()
