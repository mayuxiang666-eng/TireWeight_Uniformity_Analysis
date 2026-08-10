import time
import sys
import argparse
from datetime import datetime
from backend.etl.run_pipeline import run_full_pipeline

def start_scheduler(interval_minutes=30, run_immediately=True):
    interval_seconds = interval_minutes * 60
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时 ETL 服务已启动。")
    print(f"配置: 运行间隔 = {interval_minutes} 分钟 ({interval_seconds} 秒)。")
    
    if run_immediately:
        print("\n>>> 立即执行第一轮 ETL 任务...")
        try:
            run_full_pipeline()
        except Exception as e:
            print(f"[Error] 本轮 ETL 运行异常: {e}")
            
    while True:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 进入定时休眠，下一次运行将在 {interval_minutes} 分钟后...")
        time.sleep(interval_seconds)
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时器触发，开始新一轮 ETL 任务...")
        try:
            run_full_pipeline()
        except Exception as e:
            print(f"[Error] 本轮 ETL 运行异常: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TireWeight Uniformity Analysis ETL Scheduler Daemon")
    parser.add_argument("--interval", type=int, default=30, help="定时轮询间隔 (单位: 分钟，默认 30 分钟)")
    parser.add_argument("--no-initial-run", action="store_true", help="启动时不立即运行，等待一个间隔后再执行")
    args = parser.parse_args()
    
    start_scheduler(interval_minutes=args.interval, run_immediately=not args.no_initial_run)
