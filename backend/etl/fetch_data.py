import os
import sys
import json
import base64
import datetime
import psycopg2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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

def get_watermark_from_parquet(base_parquet=None):
    """
    直接从本地/服务器已有的原始大宽表 Parquet 中极速计算最大终检日期 (MAX(tu_first_loc_timestamp))。
    为防止生产线跨班次或重测数据延迟，将拉取起点安全回退 1 天（MAX日期 - 1天）。
    若大表不存在或为空，返回 None（自动触发全量 31 天拉取）。
    """
    if base_parquet is None:
        data_dir = get_data_dir()
        base_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    
    if not os.path.exists(base_parquet):
        print(f"[Watermark] 本地基准大表不存在 ({base_parquet})，将执行全量拉取。")
        return None
    
    try:
        import duckdb
        con = duckdb.connect()
        existing_cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{base_parquet}') LIMIT 1").fetchall()]
        time_field = "tu_first_loc_timestamp" if "tu_first_loc_timestamp" in existing_cols else ("tu_first_shift_date" if "tu_first_shift_date" in existing_cols else None)
        
        if not time_field:
            print("[Watermark] 未找到有效的时间字段，将执行全量拉取。")
            con.close()
            return None

        res = con.execute(f"""
            SELECT MAX(TRY_CAST({time_field} AS DATE)) as max_dt 
            FROM read_parquet('{base_parquet}')
            WHERE {time_field} IS NOT NULL
        """).fetchone()
        con.close()
        
        if not res or not res[0]:
            print("[Watermark] 本地基准大表无有效日期记录，将执行全量拉取。")
            return None
        
        max_dt = res[0]
        safe_watermark_dt = max_dt - datetime.timedelta(days=1)
        safe_watermark = safe_watermark_dt.strftime("%Y-%m-%d")
        print(f"[Watermark] 大表当前最大日期: {max_dt.strftime('%Y-%m-%d')}，设定安全抽取起点 (回退1天): {safe_watermark}")
        return safe_watermark
    except Exception as e:
        print(f"[Watermark Warning] 读取大表日期计算水位线失败 ({e})，将执行全量拉取。")
        return None

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
    if "://" in server:
        server = server.split("://", 1)[1]
    if ":" in server:
        server = server.split(":", 1)[0]
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
    date_cols = ["tu_first_loc_timestamp", "ct_shiftdate", "last_modified_utc_timestamp"]
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
    date_cols = ["tu_first_loc_timestamp", "ct_shiftdate", "last_modified_utc_timestamp"]
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
    y.article10_intended,
    y.barcode,

    y.tire_weight_target_first,
    y.tire_weight_actual_first,
    y.cony_first,

    y.ccs_workcenter,
    y.yt_workcenter,
    y.gt_workcenter,
    y.ct_workcenter,
    y.ct_shop,
    y.tu_first_loc_timestamp,

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

WHERE y.tu_first_loc_timestamp >= CURRENT_DATE - INTERVAL '31 day'
;
"""

# --- 增量查询 SQL：只拉取自上次水位线之后修改的记录 ---
SELECT_QUERY_INCREMENTAL = """
SELECT
    y.article10_intended,
    y.barcode,

    y.tire_weight_target_first,
    y.tire_weight_actual_first,
    y.cony_first,

    y.ccs_workcenter,
    y.yt_workcenter,
    y.gt_workcenter,
    y.ct_workcenter,
    y.ct_shop,
    y.tu_first_loc_timestamp,

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

WHERE y.tu_first_loc_timestamp >= %(watermark)s
ORDER BY y.tu_first_loc_timestamp ASC
;
"""

def _get_db_connection(config, user, password, max_retries=3, retry_delay=5):
    """创建并返回 psycopg2 数据库连接（含 SSL 支持与网络瞬断 3 次重试机制）"""
    import time
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=config['server'],
                port=config.get('port', 5439),
                database=config['database'],
                user=user,
                password=password,
                sslmode=config.get('sslmode', 'require'),
                connect_timeout=30,
                # 强制服务端以 UTF-8 编码返回数据，防止 Latin-1 等字符导致解码崩溃
                options="-c client_encoding=UTF8"
            )
            return conn
        except psycopg2.OperationalError as oe:
            last_err = oe
            print(f"[Network Warning] Redshift 数据库连接尝试 ({attempt}/{max_retries}) 遇到网络或 SSL 抖动: {oe}")
            if attempt < max_retries:
                print(f"  将于 {retry_delay} 秒后尝试第 {attempt + 1} 次重连...")
                time.sleep(retry_delay)

    # 若 sslmode='require' 重试仍失败，尝试备用降级连接 (不指定 sslmode)
    try:
        print("[Network Fallback] 尝试备用模式建立 Redshift 连接...")
        return psycopg2.connect(
            host=config['server'],
            port=config.get('port', 5439),
            database=config['database'],
            user=user,
            password=password,
            connect_timeout=30,
            options="-c client_encoding=UTF8"
        )
    except Exception:
        raise last_err



def _load_db_credentials():
    """加载并解密数据库配置，返回 (config_dict, user, password)"""
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
    except Exception:
        print("[Error] 账户或密码解密失败，请检查配置文件与密阐。")
        return None, None, None
    return config, user, password


def _stream_query_to_parquet(conn, sql, params, output_parquet, cursor_name="etl_stream_cursor"):
    """
    将一个 SQL 查询结果流式写入 Parquet 文件。
    优化：将 chunk_size 调整为 20000 行，配合显式垃圾回收，防止 66 列海量 Python 对象引发 MemoryError。
    返回 (total_rows, max_last_modified) 元组，失败报错。
    """
    import gc
    chunk_size = 20000
    total_rows = 0
    writer = None
    max_ts = None

    with conn.cursor(name=cursor_name) as cursor:
        cursor.itersize = chunk_size
        print("正在执行查询 SQL...")
        cursor.execute(sql, params)

        rows = cursor.fetchmany(chunk_size)
        if not rows:
            print("查询返回空结果！")
            return 0, None

        cols = [desc[0] for desc in cursor.description]
        print(f"查询执行成功，返回列数: {len(cols)}")

        while True:
            # 容错解码
            try:
                df_chunk = pd.DataFrame(rows, columns=cols)
            except UnicodeDecodeError as ude:
                print(f"[Warning] 当前批次含无法解码的字符，尝试逐行容错处理: {ude}")
                safe_rows = []
                for row in rows:
                    try:
                        safe_row = tuple(
                            v.encode('utf-8', errors='replace').decode('utf-8')
                            if isinstance(v, str) else v
                            for v in row
                        )
                        safe_rows.append(safe_row)
                    except Exception:
                        pass
                if not safe_rows:
                    del rows
                    gc.collect()
                    try:
                        rows = cursor.fetchmany(chunk_size)
                    except Exception:
                        break
                    if not rows:
                        break
                    continue
                df_chunk = pd.DataFrame(safe_rows, columns=cols)

            df_chunk = format_chunk(df_chunk)

            # 记录当前批次的最大日期（增量模式下用于更新水位线）
            if "tu_first_loc_timestamp" in df_chunk.columns:
                dates_temp = pd.to_datetime(df_chunk["tu_first_loc_timestamp"], errors="coerce")
                chunk_max = dates_temp.max()
                if pd.notna(chunk_max):
                    chunk_max_str = chunk_max.strftime("%Y-%m-%d")
                    if max_ts is None or chunk_max_str > max_ts:
                        max_ts = chunk_max_str

            parquet_schema = build_arrow_schema(df_chunk)
            table = pa.Table.from_pandas(df_chunk, schema=parquet_schema, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(output_parquet, parquet_schema, compression='snappy', use_dictionary=False)

            writer.write_table(table)
            chunk_len = len(df_chunk)
            total_rows += chunk_len
            print(f"已流式写入 Parquet: {total_rows} 行...")

            # 显式清理上一批次的内存对象并触发 GC
            del df_chunk, table, rows
            gc.collect()

            try:
                rows = cursor.fetchmany(chunk_size)
            except UnicodeDecodeError as ude:
                print(f"[Warning] fetchmany 解码异常，跳过当前批次继续: {ude}")
                try:
                    rows = cursor.fetchmany(chunk_size)
                except Exception:
                    break
            except Exception as fe:
                print(f"[Warning] fetchmany 提取异常: {fe}")
                break

            if not rows:
                break

    if writer:
        writer.close()

    return total_rows, max_ts



def fetch_full(output_parquet=None):
    """全量拉取近 31 天数据并覆盖写入 Parquet（与原 fetch_main 逻辑相同）"""
    config, user, password = _load_db_credentials()
    if config is None:
        return False

    print("正在连接 Amazon Redshift 数据库...")

    if output_parquet is None:
        data_dir = get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        output_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
    else:
        os.makedirs(os.path.dirname(output_parquet), exist_ok=True)

    conn = None
    try:
        conn = _get_db_connection(config, user, password)
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

            total_rows, _ = _stream_query_to_parquet(
                conn, SELECT_QUERY, None, output_parquet,
                cursor_name="redshift_full_stream_cursor"
            )

        print(f"[Success] 全量 Parquet 写入完成！共写入: {total_rows} 行，保存至: {output_parquet}")
        return True

    except Exception as e:
        print("[Error] 数据库连接、查询或文件写入出错:")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()


# 向后兼容别名（run_pipeline.py 中旧引用不需修改）
fetch_main = fetch_full


def fetch_incremental(output_parquet=None):
    """
    自愈式增量拉取：
    直接基于本地/服务器已有的原始大宽表的最大生产日期（安全回退1天）从 Redshift 提取最新数据。
    - 若大表不存在或无有效数据，自动回退为全量拉取近 31 天数据。
    - 返回 (success: bool, new_max_ts: str|None, incremental_parquet_path: str|None)
    """
    watermark = get_watermark_from_parquet()
    run_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    if not watermark:
        print("[Incremental] 未探测到有效的大表水位线，自动回退为全量拉取模式（近 31 天）...")
        if output_parquet is None:
            data_dir = get_data_dir()
            output_parquet = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")
        ok = fetch_full(output_parquet)
        return ok, None, output_parquet

    print(f"[Incremental] 本次增量抽取范围: tu_first_shift_date >= {watermark}")

    config, user, password = _load_db_credentials()
    if config is None:
        return False, None, None

    # 增量数据先写入临时文件
    if output_parquet is None:
        data_dir = get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        inc_parquet = os.path.join(data_dir, "yield_incremental.parquet.tmp")
    else:
        inc_parquet = output_parquet + ".incremental.tmp"
        os.makedirs(os.path.dirname(inc_parquet), exist_ok=True)

    conn = None
    try:
        print("正在连接 Amazon Redshift 数据库...")
        conn = _get_db_connection(config, user, password)
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

            params = {"watermark": watermark, "run_time": run_time}
            total_rows, max_ts = _stream_query_to_parquet(
                conn, SELECT_QUERY_INCREMENTAL, params, inc_parquet,
                cursor_name="redshift_incremental_stream_cursor"
            )

        if total_rows == 0:
            print("[Incremental] 本轮无新增/修改记录，跳过合并。")
            if os.path.exists(inc_parquet):
                os.remove(inc_parquet)
            return True, None, None

        print(f"[Incremental] 共拉取新/更新记录: {total_rows} 行，临时文件: {inc_parquet}")
        return True, str(max_ts) if max_ts else run_time, inc_parquet

    except Exception as e:
        print("[Error] 增量拉取出错:")
        import traceback
        traceback.print_exc()
        return False, None, None
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Redshift Data")
    parser.add_argument("--setup", action="store_true", help="重新配置/更换 Redshift 数据库账号密码与连接配置")
    args = parser.parse_args()

    if args.setup:
        setup_config()
    else:
        fetch_full()

