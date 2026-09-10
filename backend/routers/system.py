# -*- coding: utf-8 -*-
"""
系统与运维 API 路由 (System & Maintenance Router)
包含服务热重启、ETL 数据在线重载、数据源状态检测与首页静态资源代理
"""
import os
import threading
import time
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.core.config import FRONTEND_DIST, DATA_PATH, get_cleaned_data_path
from backend.core.db import reload_duckdb_data, qry, CACHED_ROW_COUNT

router = APIRouter()


@router.post("/api/system/restart")
@router.get("/api/system/restart")
def restart_service():
    """重启后端服务进程（由 NSSM 服务监控守护进程自动拉起最新代码）"""
    def _do_restart():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"status": "success", "message": "后端服务正在重启重载..."}


@router.get("/")
def root():
    """根路径欢迎信息或返回前端首页 index.html"""
    index_file = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "message": "轮胎质量分析看板 API 运行中"}


@router.post("/api/etl/reload")
@router.get("/api/etl/reload")
def reload_etl_data():
    """在线重载最新的 Cleaned Parquet 数据到 DuckDB 内存表"""
    try:
        success = reload_duckdb_data()
        if not success:
            return {"status": "error", "message": f"未找到数据文件: {DATA_PATH}"}
        
        row_res = qry("SELECT COUNT(*) as n FROM clean_yield")
        row_count = row_res[0]['n'] if row_res else 0
        return {
            "status": "success", 
            "message": "DuckDB 内存数据刷新成功", 
            "data_path": DATA_PATH,
            "row_count": row_count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/etl/status")
def get_etl_status():
    """查看数据源状态与最后修改时间"""
    try:
        current_path = get_cleaned_data_path()
        file_exists = os.path.exists(current_path)
        mtime_str = None
        size_bytes = 0
        if file_exists:
            mtime = os.path.getmtime(current_path)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_bytes = os.path.getsize(current_path)
            
        row_count = CACHED_ROW_COUNT if file_exists else 0
        
        return {
            "status": "success",
            "data": {
                "data_path": DATA_PATH,
                "exists": file_exists,
                "last_modified": mtime_str,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "loaded_rows": row_count
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
