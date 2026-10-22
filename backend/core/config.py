# -*- coding: utf-8 -*-
"""
数据文件与静态页面路径探测配置模块
"""
import os
import glob

# 动态定位项目路径
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(_CORE_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)

_static_base = ROOT_DIR
_frontend_dist_candidate = os.path.join(_static_base, "frontend", "dist")
_root_dist_candidate = os.path.join(_static_base, "dist")
FRONTEND_DIST = _frontend_dist_candidate if os.path.isdir(_frontend_dist_candidate) else _root_dist_candidate


def get_cleaned_data_path() -> str:
    """自动探测清洗后的 Parquet 文件路径 (多候选路径自适应探测)"""
    _BASE = BACKEND_DIR
    root_dir = ROOT_DIR
    candidates = [
        os.path.join(_BASE, "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(root_dir, "backend", "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(root_dir, "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(os.getcwd(), "backend", "data", "yield_flat_table_joined_100_cleaned.parquet"),
        os.path.join(os.getcwd(), "data", "yield_flat_table_joined_100_cleaned.parquet"),
        "d:/Ava/untitled1/untitled1/src/yield_flat_table_joined_100_cleaned.parquet"
    ]
    existing = [c for c in candidates if os.path.exists(c)]
    if existing:
        return max(existing, key=os.path.getmtime)
    return os.path.join(_BASE, "data", "yield_flat_table_joined_100_cleaned.parquet")


def get_cgrs_data_path() -> str:
    """自动探测 CGRS 数据源路径 (优先检查每日 Parquet 增量目录，备用单文件)"""
    _BASE = BACKEND_DIR
    root_dir = ROOT_DIR
    # 优先检查 cgrs_data 目录（包含每日 Parquet 增量文件，优先使用服务器共享或项目根目录路径）
    dir_candidates = [
        r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data",
        os.path.join(root_dir, "cgrs_data"),
        os.path.join(_BASE, "..", "cgrs_data"),
        os.path.join(_BASE, "data", "cgrs_data"),
        os.path.join(root_dir, "backend", "data", "cgrs_data"),
        os.path.join(root_dir, "data", "cgrs_data"),
        os.path.join(os.getcwd(), "cgrs_data"),
        os.path.join(os.getcwd(), "backend", "data", "cgrs_data"),
        os.path.join(os.getcwd(), "data", "cgrs_data"),
    ]
    for d in dir_candidates:
        if os.path.isdir(d):
            if glob.glob(os.path.join(d, "*.parquet")):
                return os.path.abspath(d) if not d.startswith("\\\\") else d
    
    # 备用兼容单个 CGRS.parquet 或 CGRS.csv 文件
    candidates = [
        r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data\CGRS.parquet",
        os.path.join(root_dir, "cgrs_data", "CGRS.parquet"),
        os.path.join(_BASE, "data", "CGRS.parquet"),
        os.path.join(root_dir, "backend", "data", "CGRS.parquet"),
        os.path.join(_BASE, "data", "CGRS.csv"),
        os.path.join(root_dir, "backend", "data", "CGRS.csv"),
        os.path.join(root_dir, "data", "CGRS.csv"),
        os.path.join(os.getcwd(), "backend", "data", "CGRS.csv"),
        os.path.join(os.getcwd(), "data", "CGRS.csv"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c) if not c.startswith("\\\\") else c
    return r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis\cgrs_data"


DATA_PATH = get_cleaned_data_path()
