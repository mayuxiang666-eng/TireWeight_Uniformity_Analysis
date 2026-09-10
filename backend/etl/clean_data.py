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
    
    try:
        input_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{input_path}')").fetchone()[0]
        print(f"原始数据集大小: {input_count:,} 行。")

        has_recipes = os.path.exists(recipes_path)
        if has_recipes:
            print("\n--- 步骤 1.2: 基于 Recipes.csv 预编译配方映射表 (RFPP / RFH1 / CONY) ---")
            try:
                # 1. 为 RFPP/RFH1 准备过滤后的配方数据 (受 INFLATION 限制)
                con.execute(f"""
                    CREATE OR REPLACE TABLE recipes_rf AS
                    SELECT 
                        LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') as art10_clean,
                        TRY_CAST(RFPP_T1 AS DOUBLE) / 10.0 as rfpp_val,
                        TRY_CAST(RFH1_T1 AS DOUBLE) / 10.0 as rfh1_val,
                        TRY_CAST(UPDATE_LIMIT AS TIMESTAMP) as update_limit_dt
                    FROM read_csv('{recipes_path}', header=true, all_varchar=true)
                    WHERE TRY_CAST(INFLATION AS BIGINT) != 200000
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') ORDER BY ART10) = 1;
                """)

                # 2. 为 CONY 准备完整配方数据
                con.execute(f"""
                    CREATE OR REPLACE TABLE recipes_cony AS
                    SELECT 
                        LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') as art10_clean,
                        TRY_CAST(CONU_T1 AS DOUBLE) as conu_val,
                        TRY_CAST(CONL_T1 AS DOUBLE) as conl_val
                    FROM read_csv('{recipes_path}', header=true, all_varchar=true)
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY LPAD(TRIM(CAST(ART10 AS VARCHAR)), 10, '0') ORDER BY TRY_CAST(RELEASE_TIME AS TIMESTAMP) DESC NULLS LAST) = 1;
                """)
                print("  配方映射表预编译就绪。")
            except Exception as e:
                print(f"[Warning] 配方表解析异常 ({e})，将保持原物理标准值。")
                has_recipes = False
        else:
            print(f"[Warning] 未找到配方表: {recipes_path}，跳过标准上限值检查与更新。")

        print("\n--- 步骤 2: 动态检查并构建列过滤方案 ---")
        existing_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{input_path}') LIMIT 1").fetchall()]
        
        art_col = "article10_intended" if "article10_intended" in existing_cols else "article10"
        art10_alias_expr = f", t.{art_col} AS article10" if (art_col != "article10" and "article10" not in existing_cols) else ""
        
        # 需剔除的冗余字段及高缺失率字段
        drop_candidates = [
            "articleno", "articleno_7", "articlevariant", "branddesignation", "loadindexsingle", "speedsymbol", "ssr",
            "yt_workcenter", "ssr_insert_bead_cushion_workcenter", "ssr_insert_bead_cushion_lot",
            "bead_reinforcement_workcenter", "bead_reinforcement_lot", "second_ply_lot", "second_ply_workcenter",
            "standard_rfpp", "standard_rfh1"
        ]
        cols_to_exclude = [c for c in drop_candidates if c in existing_cols]
        exclude_str = f"EXCLUDE ({', '.join(cols_to_exclude)})" if cols_to_exclude else ""
        print(f"已动态排除冗余/高缺失字段: {cols_to_exclude}")

        print("\n--- 步骤 3: DuckDB 原生流式清洗与原子输出 (Out-of-Core Execution) ---")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = output_path + ".cleaning.tmp"

        ts_candidates = ["tu_first_loc_timestamp", "tu_first_shift_date", "ct_loc_timestamp", "gt_loc_timestamp"]
        available_ts = [f"TRY_CAST(t.{c} AS TIMESTAMP)" for c in ts_candidates if c in existing_cols]
        ts_expr = f"COALESCE({', '.join(available_ts)})" if available_ts else "NULL"

        if has_recipes:
            clean_sql = f"""
                COPY (
                    SELECT 
                        t.* {exclude_str}{art10_alias_expr},
                        -- 基于生产日期与配方发布日期的物理上限标准更新
                        CASE 
                            WHEN rf.art10_clean IS NOT NULL 
                                 AND {ts_expr} >= rf.update_limit_dt 
                            THEN rf.rfpp_val
                            ELSE t.standard_rfpp 
                        END AS standard_rfpp,
                        CASE 
                            WHEN rf.art10_clean IS NOT NULL 
                                 AND {ts_expr} >= rf.update_limit_dt 
                            THEN rf.rfh1_val
                            ELSE t.standard_rfh1 
                        END AS standard_rfh1,
                        cy.conu_val AS conny_usl,
                        cy.conl_val AS conny_lsl
                    FROM read_parquet('{input_path}') t
                    LEFT JOIN recipes_rf rf ON LPAD(TRIM(CAST(t.{art_col} AS VARCHAR)), 10, '0') = rf.art10_clean
                    LEFT JOIN recipes_cony cy ON LPAD(TRIM(CAST(t.{art_col} AS VARCHAR)), 10, '0') = cy.art10_clean
                    WHERE t.{art_col} IS NOT NULL 
                      AND TRIM(CAST(t.{art_col} AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NULL')
                ) TO '{tmp_path}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
            """
        else:
            clean_sql = f"""
                COPY (
                    SELECT 
                        t.* {exclude_str}{art10_alias_expr},
                        t.standard_rfpp,
                        t.standard_rfh1,
                        NULL::DOUBLE AS conny_usl,
                        NULL::DOUBLE AS conny_lsl
                    FROM read_parquet('{input_path}') t
                    WHERE t.{art_col} IS NOT NULL 
                      AND TRIM(CAST(t.{art_col} AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NULL')
                ) TO '{tmp_path}' (FORMAT 'PARQUET', COMPRESSION 'SNAPPY');
            """

        con.execute(clean_sql)
        
        final_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{tmp_path}')").fetchone()[0]
        final_cols = len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{tmp_path}') LIMIT 1").fetchall())
        
        os.replace(tmp_path, output_path)
        print(f"[Success] DuckDB 流式清洗完成！终态保存至: {output_path}")
        print(f"最终清洗数据集大小: {final_rows:,} 行, {final_cols} 列。")

        # 同步镜像副本至备用 data 目录
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
