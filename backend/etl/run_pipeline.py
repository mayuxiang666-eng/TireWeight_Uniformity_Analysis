import os
import sys
import argparse
import urllib.request
import json
from datetime import datetime

etl_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(etl_dir)
root_dir = os.path.dirname(backend_dir)
for p in [etl_dir, backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from fetch_data import fetch_incremental, fetch_full
    from clean_data import clean_main, get_data_dir
    from merge_data import merge_main
except (ModuleNotFoundError, ImportError):
    try:
        from etl.fetch_data import fetch_incremental, fetch_full
        from etl.clean_data import clean_main, get_data_dir
        from etl.merge_data import merge_main
    except (ModuleNotFoundError, ImportError):
        from backend.etl.fetch_data import fetch_incremental, fetch_full
        from backend.etl.clean_data import clean_main, get_data_dir
        from backend.etl.merge_data import merge_main

def notify_backend_reload(backend_url="http://127.0.0.1:8000/api/etl/reload"):
    try:
        req = urllib.request.Request(
            backend_url, 
            data=b"{}", 
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = response.read().decode('utf-8')
            print(f"[Notify Success] 后端 DuckDB 热加载回应: {res_data}")
            return True
    except Exception as e:
        print(f"[Notify Notice] 尝试通知后端热加载失败 (若后端服务未启动可忽略): {e}")
        return False

def run_full_pipeline(skip_fetch=False, notify=True, full_fetch=False):
    print(f"\n================ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始全流程 ETL 流水线 ================")

    if not skip_fetch:
        if full_fetch:
            # --- 阶段 1: 手动触发全量覆盖拉取 ---
            print("\n--- 阶段 1: 全量覆盖模式（--full-fetch）从 Amazon Redshift 抓取近 31 天数据 ---")
            fetch_ok = fetch_full()
            if not fetch_ok:
                print("[ERR] 全量数据拉取步骤失败，终止流水线。")
                return False
            print("\n--- 阶段 1.5: 全量模式跳过增量合并阶段 ---")

        else:
            # --- 阶段 1: 增量拉取 ---
            print("\n--- 阶段 1: 从 Amazon Redshift 增量抓取最新数据 ---")
            fetch_ok, new_watermark, inc_parquet = fetch_incremental()
            if not fetch_ok:
                print("[ERR] 增量数据拉取步骤失败，终止流水线。")
                return False

            data_dir = get_data_dir()
            cleaned_base = os.path.join(data_dir, "yield_flat_table_joined_100_cleaned.parquet")
            raw_base = os.path.join(data_dir, "yield_flat_table_joined_100.parquet")

            if inc_parquet is not None:
                # --- 阶段 1.5: 增量极速清洗 (仅清洗新拉取的增量临时文件，秒级超低内存) ---
                print("\n--- 阶段 1.5: 增量极速清洗（仅清洗增量新记录，秒级低内存完成）---")
                inc_cleaned_parquet = inc_parquet.replace(".tmp", ".cleaned.tmp")
                clean_ok = clean_main(input_path=inc_parquet, output_path=inc_cleaned_parquet)
                if not clean_ok:
                    print("[ERR] 增量清洗步骤失败。")
                    return False

                # --- 阶段 1.6: 合并清洗增量至看板清洗大表 (upsert + 31天窗口裁剪) ---
                if os.path.exists(cleaned_base):
                    print("\n--- 阶段 1.6: 合并增量清洗数据到主看板清洗表（upsert + 31天滚动裁剪）---")
                    merge_clean_ok = merge_main(
                        incremental_parquet=inc_cleaned_parquet,
                        base_parquet=cleaned_base,
                        new_watermark=new_watermark
                    )
                    if not merge_clean_ok:
                        print("[ERR] 增量清洗表合并失败。")
                        return False
                else:
                    print("\n[Notice] 主清洗表不存在，执行一次全量清洗初始化...")
                    clean_main()

                # --- 阶段 1.7: 归档合并增量到原始大底表 ---
                print("\n--- 阶段 1.7: 归档合并增量到原始大底表（upsert + 滚动窗口）---")
                merge_ok = merge_main(
                    incremental_parquet=inc_parquet,
                    base_parquet=raw_base,
                    new_watermark=new_watermark
                )
                if not merge_ok:
                    print("[ERR] 原始大底表增量合并步骤失败。")
                    return False

                # 清理临时增量清洗文件
                if os.path.exists(inc_cleaned_parquet):
                    try:
                        os.remove(inc_cleaned_parquet)
                    except Exception:
                        pass
            else:
                print("\n--- 阶段 1.5: 本轮无新增数据，跳过增量清洗与合并 ---")
                if not os.path.exists(cleaned_base):
                    clean_main()
    else:
        print("\n--- 阶段 1: 已跳过数据抓取 (--skip-fetch) ---")
        print("--- 阶段 1.5: 已跳过增量合并 ---")

    # --- 阶段 2: 数据清洗与异常标记 ---
    if full_fetch or skip_fetch:
        print("\n--- 阶段 2: 执行全量数据清洗与异常标记计算 ---")
        clean_ok = clean_main()
        if not clean_ok:
            print("[ERR] 数据清洗步骤失败。")
            return False
    else:
        print("\n--- 阶段 2: 增量清洗已在前序步骤无缝合流，跳过冗余的全量重算 ---")

    # --- 阶段 3: 触发后端热加载 ---
    print("\n--- 阶段 3: 触发后端 DuckDB 内存热加载 ---")
    if notify:
        notify_backend_reload()

    print(f"================ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ETL 流水线顺利完成 ================\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TireWeight Uniformity Analysis ETL Pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过从 Redshift 提取数据，直接进行清洗")
    parser.add_argument("--no-notify", action="store_true", help="不通知后端触发在线热重载")
    parser.add_argument("--full-fetch", action="store_true", help="强制全量覆盖拉取近 31 天数据（忽略水位线）")
    args = parser.parse_args()

    success = run_full_pipeline(
        skip_fetch=args.skip_fetch,
        notify=not args.no_notify,
        full_fetch=args.full_fetch
    )
    sys.exit(0 if success else 1)
