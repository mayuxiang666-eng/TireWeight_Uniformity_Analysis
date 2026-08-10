import os
import sys
import json
import base64
import datetime
import psycopg2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# --- 加密/解密帮助函数 ---
def xor_crypt(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))

def encrypt(plain_text: str, key: str) -> str:
    data_bytes = plain_text.encode('utf-8')
    key_bytes = key.encode('utf-8')
    encrypted_bytes = xor_crypt(data_bytes, key_bytes)
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def decrypt(encrypted_text: str, key: str) -> str:
    encrypted_bytes = base64.b64decode(encrypted_text.encode('utf-8'))
    key_bytes = key.encode('utf-8')
    decrypted_bytes = xor_crypt(encrypted_bytes, key_bytes)
    return decrypted_bytes.decode('utf-8')

def find_config_file(filename):
    etl_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(etl_dir)
    config_dir = os.path.join(backend_dir, "config")
    
    candidates = [
        os.path.join(config_dir, filename),
        os.path.join(backend_dir, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), "config", filename),
        os.path.join(os.path.dirname(backend_dir), filename)
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.join(config_dir, filename)

def setup_config():
    print("\n--- Amazon Redshift 数据库连接配置初始化 ---")
    server = input("请输入数据库服务器地址 (Server, e.g. xxx.redshift.amazonaws.com): ").strip()
    port_input = input("请输入端口号 (Port, 默认 5439): ").strip()
    port = int(port_input) if port_input else 5439
    database = input("请输入数据库名称 (Database, e.g. mustangmaster): ").strip()
    user = input("请输入数据库用户名 (User): ").strip()
    password = input("请输入密码 (Password): ").strip()
    
    import secrets
    key = secrets.token_hex(16)
    
    secret_path = find_config_file("secret.key")
    db_config_path = find_config_file("db_config.json")
    
    os.makedirs(os.path.dirname(secret_path), exist_ok=True)
    os.makedirs(os.path.dirname(db_config_path), exist_ok=True)
    
    with open(secret_path, "w", encoding="utf-8") as f:
        f.write(key)
        
    enc_user = encrypt(user, key)
    enc_pass = encrypt(password, key)
    
    config = {
        "server": server,
        "port": port,
        "database": database,
        "user": enc_user,
        "password": enc_pass
    }
    
    with open(db_config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    print(f"[OK] 配置文件 {db_config_path} 和密钥 {secret_path} 已成功生成！")
    print("------------------------------------\n")

def format_chunk(df_chunk):
    date_cols = ["ct_shiftdate", "last_modified_utc_timestamp"]
    for col in date_cols:
        if col in df_chunk.columns:
            df_chunk[col] = pd.to_datetime(df_chunk[col], errors="coerce")
    
    numeric_cols = ["loadindexsingle", "standard_rfpp", "standard_rfh1", "ss_value", "rfppwc_first", "rfh1wc_first"]
    for col in numeric_cols:
        for col_name in df_chunk.columns:
            if col_name.lower() == col:
                df_chunk[col_name] = pd.to_numeric(df_chunk[col_name], errors="coerce")
                
    for col in df_chunk.columns:
        if col in date_cols or col.lower() in numeric_cols:
            continue
        df_chunk[col] = df_chunk[col].astype(str).replace({
            'nan': None, 'None': None, '<NA>': None, 'NAT': None, 'NaT': None, 'nat': None
        })
    return df_chunk

def build_arrow_schema(df_chunk):
    fields = []
    numeric_cols = ["loadindexsingle", "standard_rfpp", "standard_rfh1", "ss_value", "rfppwc_first", "rfh1wc_first"]
    date_cols = ["ct_shiftdate", "last_modified_utc_timestamp"]
    for col in df_chunk.columns:
        if col in date_cols:
            fields.append(pa.field(col, pa.timestamp('s')))
        elif col.lower() in numeric_cols:
            fields.append(pa.field(col, pa.float64()))
        else:
            fields.append(pa.field(col, pa.string()))
    return pa.schema(fields)

CREATE_TEMP_TABLE_SQL = """
DROP TABLE IF EXISTS tmp_dil_article_standard;

CREATE TEMP TABLE tmp_dil_article_standard
DISTSTYLE ALL
SORTKEY (articleid)
AS
WITH base AS
(
    SELECT
        articleid,
        articleno,
        articlevariant,
        specissue,
        greentiregutsid,
        branddesignation,
        loadindexsingle,
        speedsymbol,
        ssr,

        CASE UPPER(TRIM(speedsymbol))
            WHEN 'L'   THEN 120
            WHEN 'M'   THEN 130
            WHEN 'N'   THEN 140
            WHEN 'P'   THEN 150
            WHEN 'Q'   THEN 160
            WHEN 'R'   THEN 170
            WHEN 'S'   THEN 180
            WHEN 'T'   THEN 190
            WHEN 'U'   THEN 200
            WHEN 'H'   THEN 210
            WHEN 'V'   THEN 240
            WHEN 'W'   THEN 270
            WHEN 'Y'   THEN 300
            WHEN '(Y)' THEN 301
            WHEN 'ZR'  THEN 241
            WHEN '(Y'  THEN 301
            WHEN '(V'  THEN 241
            ELSE NULL
        END AS ss_value

    FROM stg_he.stg_dil_article
),

judgement AS
(
    SELECT
        articleid,
        articleno,
        articlevariant,
        specissue,
        greentiregutsid,
        branddesignation,
        loadindexsingle,
        speedsymbol,
        ssr,

        CASE

            WHEN UPPER(TRIM(COALESCE(branddesignation,''))) = 'CONTINENTAL'
                 AND
                 (
                    (
                        loadindexsingle > 104
                        AND loadindexsingle <= 111
                        AND ss_value <= 210
                    )
                    OR
                    (
                        UPPER(TRIM(COALESCE(ssr::text,''))) = 'SSR'
                        AND loadindexsingle > 104
                    )
                 )
            THEN 'GROUP 2A'

            WHEN UPPER(TRIM(COALESCE(branddesignation,''))) = 'CONTINENTAL'
                 AND
                 (
                    loadindexsingle <= 104
                    OR
                    (
                        loadindexsingle > 104
                        AND ss_value > 210
                    )
                 )
            THEN 'GROUP 1'

            WHEN UPPER(TRIM(COALESCE(branddesignation,''))) = 'CONTINENTAL'
                 AND loadindexsingle > 111
                 AND ss_value <= 210
            THEN 'GROUP 2B'

            WHEN UPPER(TRIM(COALESCE(branddesignation,''))) <> 'CONTINENTAL'
                 AND
                 (
                    loadindexsingle <= 104
                    OR
                    (
                        loadindexsingle > 104
                        AND ss_value > 210
                    )
                 )
            THEN 'GROUP 3'

            WHEN UPPER(TRIM(COALESCE(branddesignation,''))) <> 'CONTINENTAL'
                 AND loadindexsingle > 104
                 AND ss_value <= 210
            THEN 'GROUP 4'

            ELSE NULL

        END AS "Group"

    FROM base
)

SELECT
    articleid,
    articleno,
    articlevariant,
    specissue,
    greentiregutsid,
    branddesignation,
    loadindexsingle,
    speedsymbol,
    ssr,

    "Group",

    CASE
        WHEN "Group" = 'GROUP 1'  THEN 10.5
        WHEN "Group" = 'GROUP 2A' THEN 11.5
        WHEN "Group" = 'GROUP 2B' THEN 12.5
        WHEN "Group" = 'GROUP 3'  THEN 12.5
        WHEN "Group" = 'GROUP 4'  THEN 14.5
        ELSE NULL
    END AS standard_rfpp,

    CASE
        WHEN "Group" = 'GROUP 1'  THEN 7.5
        WHEN "Group" = 'GROUP 2A' THEN 8.5
        WHEN "Group" = 'GROUP 2B' THEN 9.0
        WHEN "Group" = 'GROUP 3'  THEN 9.5
        WHEN "Group" = 'GROUP 4'  THEN 10.0
        ELSE NULL
    END AS standard_rfh1

FROM judgement;
"""

SELECT_QUERY = """
SELECT
    y.article10,
    y.barcode,

    y.tire_weight_target_first,
    y.tire_weight_actual_first,
    y.cony_first,

    y.ccs_workcenter,
    y.yt_workcenter,
    y.gt_workcenter,
    y.ct_workcenter,
    y.tu_first_shift_date,

    y.bead_lot,
    y.bead_workcenter,

    y.tread_lot,
    y.tread_workcenter,

    y.inner_liner_lot,
    y.inner_liner_workcenter,

    y.sidewall_lot,
    y.sidewall_workcenter,

    y.first_breaker_lot,
    y.first_breaker_workcenter,

    y.second_breaker_lot,
    y.second_breaker_workcenter,

    y.first_ply_lot,
    y.first_ply_workcenter,

    y.second_ply_lot,
    y.second_ply_workcenter,

    y.wound_cap_ply1_lot,
    y.wound_cap_ply1_workcenter,

    y.wound_cap_ply2_lot,
    y.wound_cap_ply2_workcenter,

    y.tb_first_workcenter,
    y.tg_first_workcenter,
    y.tu_first_workcenter,

    y.gt_loc_timestamp,
    y.ct_loc_timestamp,
    y.bead_loc_timestamp,
    y.tread_loc_timestamp,
    y.inner_liner_loc_timestamp,
    y.sidewall_loc_timestamp,
    y.first_breaker_loc_timestamp,
    y.second_breaker_loc_timestamp,
    y.first_ply_loc_timestamp,
    y.second_ply_loc_timestamp,
    y.wound_cap_ply1_loc_timestamp,
    y.wound_cap_ply2_loc_timestamp,

    y.rfppwc_first,
    y.rfh1wc_first,

    y.bead_reinforcement_lot,
    y.bead_reinforcement_workcenter,

    y.ssr_insert_bead_cushion_lot,
    y.ssr_insert_bead_cushion_workcenter,

    y.article_fk,

    a.article_pk,
    a.articleid,

    t.articleno,
    t.articlevariant,
    t.specissue,
    t.greentiregutsid,
    t.branddesignation,
    t.loadindexsingle,
    t.speedsymbol,
    t.ssr,

    t."Group",
    t.standard_rfpp,
    t.standard_rfh1

FROM he_datamarts.yield_flat_table y

LEFT JOIN he_datamarts.article a
    ON y.article_fk = a.article_pk

LEFT JOIN tmp_dil_article_standard t
    ON a.articleid = t.articleid

WHERE y.ct_shiftdate >= CURRENT_DATE - INTERVAL '30 day'
;
"""

def fetch_main(output_parquet=None):
    db_config_path = find_config_file("db_config.json")
    secret_path = find_config_file("secret.key")
    
    if not os.path.exists(db_config_path) or not os.path.exists(secret_path):
        setup_config()
        
    with open(db_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    with open(secret_path, "r", encoding="utf-8") as f:
        key = f.read().strip()
        
    try:
        user = decrypt(config["user"], key)
        password = decrypt(config["password"], key)
    except Exception as e:
        print("[Error] 账户或密码解密失败，请检查配置文件与密钥。")
        return False
        
    print("正在连接 Amazon Redshift 数据库...")
    
    if output_parquet is None:
        etl_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(etl_dir), "data")
        os.makedirs(data_dir, exist_ok=True)
        output_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    else:
        os.makedirs(os.path.dirname(output_parquet), exist_ok=True)
        
    conn = None
    try:
        conn = psycopg2.connect(
            host=config['server'],
            port=config.get('port', 5439),
            database=config['database'],
            user=user,
            password=password
        )
        print("连接数据库成功！")
        
        with conn.cursor() as test_cursor:
            test_cursor.execute("SELECT 1;")
            test_cursor.fetchone()
        conn.rollback()
        
        conn.autocommit = False
        with conn:
            with conn.cursor() as client_cursor:
                print("正在执行临时表创建 SQL...")
                client_cursor.execute(CREATE_TEMP_TABLE_SQL)
                print("临时表 tmp_dil_article_standard 创建成功！")
            
            chunk_size = 100000
            cursor_name = "redshift_joined_stream_cursor"
            
            with conn.cursor(name=cursor_name) as cursor:
                cursor.itersize = chunk_size
                print("正在执行主查询 SQL...")
                cursor.execute(SELECT_QUERY)
                
                total_rows = 0
                writer = None
                
                rows = cursor.fetchmany(chunk_size)
                if rows:
                    cols = [desc[0] for desc in cursor.description]
                    print(f"查询执行成功，返回列数: {len(cols)}")
                    
                    while True:
                        df_chunk = pd.DataFrame(rows, columns=cols)
                        df_chunk = format_chunk(df_chunk)
                        
                        parquet_schema = build_arrow_schema(df_chunk)
                        table = pa.Table.from_pandas(df_chunk, schema=parquet_schema, preserve_index=False)
                        
                        if writer is None:
                            writer = pq.ParquetWriter(output_parquet, parquet_schema, compression='snappy')
                            
                        writer.write_table(table)
                        total_rows += len(rows)
                        print(f"已流式写入 Parquet: {total_rows} 行...")
                        
                        rows = cursor.fetchmany(chunk_size)
                        if not rows:
                            break
                else:
                    print("查询返回空结果！")
                    
                if writer:
                    writer.close()
                
                print(f"[Success] Parquet 文件流式写入完成！共写入: {total_rows} 行，保存至: {output_parquet}")
                return True
                    
    except Exception as e:
        print("[Error] 数据库连接、查询或文件写入出错:")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fetch_main()
