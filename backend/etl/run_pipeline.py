import os
import sys
import argparse
import urllib.request
import json
from datetime import datetime

from backend.etl.fetch_data import fetch_main
from backend.etl.clean_data import clean_main

def notify_backend_reload(backend_url="http://127.0.0.1:8000/api/etl/reload"):
    try:
        req = urllib.request.Request(
            backend_url, 
            data=b"{}", 
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = response.read().decode('utf-8')
            print(f"[Notify Success] 后端 DuckDB 热加载回应: {res_data}")
            return True
    except Exception as e:
        print(f"[Notify Notice] 尝试通知后端热加载失败 (若后端服务未启动可忽略): {e}")
        return False

def run_full_pipeline(skip_fetch=False, notify=True):
    print(f"\n================ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始全流程 ETL 流水线 ================")
    
    if not skip_fetch:
        print("\n--- 阶段 1: 从 Amazon Redshift 数据库抓取最新数据 ---")
        fetch_ok = fetch_main()
        if not fetch_ok:
            print("[ERR] 数据拉取步骤失败，终止流水线。")
            return False
    else:
        print("\n--- 阶段 1: 已跳过数据抓取 (--skip-fetch) ---")
        
    print("\n--- 阶段 2: 执行数据清洗与异常标记计算 ---")
    clean_ok = clean_main()
    if not clean_ok:
        print("[ERR] 数据清洗步骤失败。")
        return False
        
    print("\n--- 阶段 3: 触发后端 DuckDB 内存热加载 ---")
    if notify:
        notify_backend_reload()
        
    print(f"================ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ETL 流水线顺利完成 ================\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TireWeight Uniformity Analysis ETL Pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过从 Redshift 提取数据，直接进行清洗")
    parser.add_argument("--no-notify", action="store_true", help="不通知后端触发在线热重载")
    args = parser.parse_args()
    
    success = run_full_pipeline(skip_fetch=args.skip_fetch, notify=not args.no_notify)
    sys.exit(0 if success else 1)
