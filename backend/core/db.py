# -*- coding: utf-8 -*-
"""
DuckDB 内存常驻连接管理与数据热重载模块
"""
import os
import duckdb
from backend.core.config import get_cleaned_data_path, get_cgrs_data_path

# 全局 DuckDB 常驻连接与内存表，将 Parquet 数据与 CGRS 载入内存以提升并发检索速度
db_conn = duckdb.connect()
CACHED_ROW_COUNT = 0


def reload_duckdb_data() -> bool:
    """重新加载数据并重建内存表"""
    global CACHED_ROW_COUNT
    data_path = get_cleaned_data_path()
    if os.path.exists(data_path):
        db_conn.execute(f"CREATE OR REPLACE TABLE clean_yield AS SELECT * FROM read_parquet('{data_path}')")
        try:
            cols = [r[0] for r in db_conn.execute("DESCRIBE clean_yield").fetchall()]
            if 'tu_first_shift_date' not in cols:
                db_conn.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_shift_date VARCHAR")
            if 'tu_first_loc_timestamp' in cols:
                db_conn.execute("UPDATE clean_yield SET tu_first_shift_date = STRFTIME(CAST((TRY_CAST(tu_first_loc_timestamp AS TIMESTAMP) - INTERVAL 8 HOUR) AS DATE), '%Y-%m-%d')")
            elif 'tu_first_shift_date' in cols and 'tu_first_loc_timestamp' not in cols:
                db_conn.execute("ALTER TABLE clean_yield ADD COLUMN tu_first_loc_timestamp VARCHAR")
                db_conn.execute("UPDATE clean_yield SET tu_first_loc_timestamp = tu_first_shift_date")
            
            if 'group' not in cols:
                db_conn.execute("ALTER TABLE clean_yield ADD COLUMN \"group\" VARCHAR DEFAULT 'GROUP 1'")
                db_conn.execute("UPDATE clean_yield SET \"group\" = 'GROUP 1'")
            
            cnt_res = db_conn.execute("SELECT COUNT(*) FROM clean_yield").fetchone()
            CACHED_ROW_COUNT = cnt_res[0] if cnt_res else 0
        except Exception:
            pass

    
    cgrs_path = get_cgrs_data_path()
    if cgrs_path and os.path.exists(cgrs_path):
        normalized_cgrs = cgrs_path.replace('\\', '/')
        if os.path.isdir(cgrs_path) or 'cgrs_data' in normalized_cgrs or normalized_cgrs.endswith('.parquet'):
            parquet_target = os.path.join(normalized_cgrs, "*.parquet").replace('\\', '/') if os.path.isdir(cgrs_path) else normalized_cgrs
            db_conn.execute(f"""
                CREATE OR REPLACE TABLE cgrs_records AS 
                SELECT 
                    *,
                    TRY_CAST(TechOffsetHistoryLocalDate AS DATE) AS match_date,
                    TRY_CAST(TechOffsetHistoryLocalDate AS TIMESTAMP) AS event_timestamp
                FROM read_parquet('{parquet_target}', union_by_name=True)
            """)
        else:
            db_conn.execute(f"""
                CREATE OR REPLACE TABLE cgrs_records AS 
                SELECT 
                    *,
                    COALESCE(
                        TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetHistoryLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
                        TRY_CAST(SPLIT_PART(TechOffsetHistoryLocalDate, ' ', 1) AS DATE),
                        TRY_CAST(STRPTIME(SPLIT_PART(TechOffsetLocalDate, ' ', 1), '%Y/%m/%d') AS DATE),
                        TRY_CAST(SPLIT_PART(TechOffsetLocalDate, ' ', 1) AS DATE)
                    ) AS match_date,
                    COALESCE(
                        TRY_CAST(STRPTIME(TechOffsetHistoryLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetHistoryLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
                        TRY_CAST(TechOffsetHistoryLocalDate AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M') AS TIMESTAMP),
                        TRY_CAST(STRPTIME(TechOffsetLocalDate, '%Y/%m/%d %H:%M:%S') AS TIMESTAMP),
                        TRY_CAST(TechOffsetLocalDate AS TIMESTAMP)
                    ) AS event_timestamp
                FROM read_csv_auto('{normalized_cgrs}', all_varchar=True)
            """)
        return True
    return os.path.exists(data_path)


def qry(sql: str, params=None):
    """执行 DuckDB 查询，使用线程安全 Cursor 并支持参数化绑定以消除 SQL 注入风险，支持自愈式热加载"""
    global CACHED_ROW_COUNT
    cursor = db_conn.cursor()
    try:
        if params:
            rel = cursor.execute(sql, params)
        else:
            rel = cursor.execute(sql)
    except duckdb.CatalogException as ce:
        if "clean_yield" in str(ce):
            reload_duckdb_data()
            if params:
                rel = cursor.execute(sql, params)
            else:
                rel = cursor.execute(sql)
        else:
            cursor.close()
            raise ce
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    cursor.close()
    return [dict(zip(cols, r)) for r in rows]

