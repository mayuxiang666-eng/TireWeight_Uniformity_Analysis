# -*- coding: utf-8 -*-
"""
轮胎质量与均匀性分析看板后端主入口 (Main Entry Point)
精简装配层 (< 80 行)：路由聚合挂载、CORS 中间件与前端静态资源代理
"""
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 保证双入口兼容 (从根目录 import backend.main 与从 backend/ 目录 import main)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from backend.core.config import FRONTEND_DIST
from backend.core.db import reload_duckdb_data
from backend.routers import articles, machines, cgrs, trend, system

app = FastAPI(title="轮胎质量分析看板 API", version="1.1.1")

# 注册 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 DuckDB 数据加载
reload_duckdb_data()

# 注册各高内聚业务路由
app.include_router(system.router, tags=["系统运维"])
app.include_router(articles.router, prefix="/api", tags=["规格看板"])
app.include_router(machines.router, prefix="/api", tags=["机台分析与工序流转"])
app.include_router(cgrs.router, prefix="/api", tags=["CGRS工艺调参"])
app.include_router(trend.router, prefix="/api", tags=["趋势与筛选"])

# 挂载前端静态页面 (必须保持在最后注册)
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
