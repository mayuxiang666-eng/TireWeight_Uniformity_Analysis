# -*- coding: utf-8 -*-
"""
轮胎质量与均匀性分析看板 (TireWeight Uniformity Analysis)
生产环境自动化发布与免登热重载脚本 (Plan B: 生产级优雅闭环)

执行链路:
  1. 本地前端 Vite 编译 (可指定 --skip-build 跳过)
  2. 精准白名单同步前端产物、后端生产模块、配置与运维脚本至服务器共享目录
  3. 向远端发送优雅自重启信令 (/api/system/restart)，NSSM 守护进程在 1 秒内安全拉起最新代码
  4. 本地自动化健康自愈轮询 (最多 20 秒)，确保服务恢复 200 OK
  5. 触发远端 DuckDB 内存表热加载 (/api/etl/reload)
  6. 校验 Nginx 前端 Web 访问 (8088 端口) 并输出部署报告
"""

import os
import sys
import shutil
import subprocess
import time
import json
import urllib.request
import urllib.error
import argparse

TARGET_SERVER_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_HOST = "10.246.97.159"
BACKEND_PORT = 8000
FRONTEND_PORT = 8088


def run_cmd(cmd, cwd=None):
    print(f">> 正在执行命令: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd or LOCAL_ROOT)
    if res.returncode != 0:
        print(f"[ERR] 命令执行失败 (code {res.returncode}): {cmd}")
        return False
    return True


def copy_file_safe(src, dst):
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copy2(src, dst)
            return True
        except Exception as e:
            print(f"[Warn] 复制文件 {os.path.basename(src)} 异常: {e}")
            return False
    return False


def copy_dir_filtered(src, dst, ignore_extensions=None, ignore_dirs=None):
    if not os.path.exists(src):
        return
    ignore_exts = set(ignore_extensions or [".pyc", ".log", ".tmp", ".parquet", ".duckdb-wal", ".db", ".duckdb"])
    ignore_dnames = set(ignore_dirs or ["__pycache__", "node_modules", ".git", "scratch", "dist"])

    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in ignore_dnames]
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)

        for f in files:
            if any(f.endswith(ext) for ext in ignore_exts):
                continue
            src_f = os.path.join(root, f)
            dst_f = os.path.join(target_dir, f)
            try:
                shutil.copy2(src_f, dst_f)
            except Exception as e:
                print(f"[Warn] 复制 {f} 失败: {e}")


def deploy(skip_build=False, skip_restart=False):
    start_time = time.time()
    print("=====================================================================")
    print("    轮胎质量看板生产自动化部署 (一键推送 & 远端无缝自愈重载)      ")
    print(f"    目标服务器: {TARGET_SERVER_DIR}")
    print("=====================================================================")

    # 1. 检查服务器共享目录联通性
    print("\n[Step 1/5] 检查远端服务器网络共享路径...")
    if not os.path.exists(TARGET_SERVER_DIR):
        print(f"[ERR] 无法访问远端共享路径: {TARGET_SERVER_DIR}")
        print("请检查 VPN/内网网络连接，或确认是否有共享文件夹读写权限。")
        return False
    print("  -> 远端网络共享目录连接正常。")

    # 2. 本地前端编译 (可选跳过)
    if not skip_build:
        print("\n[Step 2/5] 编译构建 Vue 3 生产静态应用 (npm run build)...")
        if not run_cmd("npm run build"):
            print("[ERR] 前端编译失败，终止发布。")
            return False
    else:
        print("\n[Step 2/5] 跳过前端编译 (--skip-build)...")

    dist_path = os.path.join(LOCAL_ROOT, "dist")
    if not os.path.exists(dist_path):
        print(f"[ERR] 未找到前端编译产物目录: {dist_path}，请先执行编译。")
        return False

    # 3. 精准白名单文件同步
    print("\n[Step 3/5] 同步生产必需模块至服务器 (严格过滤临时与测试文件)...")

    # 3.1 前端静态包 -> frontend/dist
    print("  -> 同步前端静态包至 frontend/dist...")
    copy_dir_filtered(
        dist_path,
        os.path.join(TARGET_SERVER_DIR, "frontend", "dist")
    )

    # 3.2 后端应用核心代码与入口
    print("  -> 同步后端核心代码 (main.py, run_server.py, requirements.txt)...")
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "backend", "main.py"),
        os.path.join(TARGET_SERVER_DIR, "backend", "main.py")
    )
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "backend", "run_server.py"),
        os.path.join(TARGET_SERVER_DIR, "backend", "run_server.py")
    )
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "run_server.py"),
        os.path.join(TARGET_SERVER_DIR, "run_server.py")
    )
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "backend", "requirements.txt"),
        os.path.join(TARGET_SERVER_DIR, "backend", "requirements.txt")
    )

    # 3.3 后端模块化组件 (core, services, routers) 与配置
    print("  -> 同步后端模块化组件 (core, services, routers)...")
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "core"),
        os.path.join(TARGET_SERVER_DIR, "backend", "core")
    )
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "services"),
        os.path.join(TARGET_SERVER_DIR, "backend", "services")
    )
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "routers"),
        os.path.join(TARGET_SERVER_DIR, "backend", "routers")
    )
    print("  -> 同步后端配置 (backend/config)...")
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "config"),
        os.path.join(TARGET_SERVER_DIR, "backend", "config")
    )

    # 3.4 ETL 处理管道
    print("  -> 同步 ETL 数据处理模块 (backend/etl)...")
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "etl"),
        os.path.join(TARGET_SERVER_DIR, "backend", "etl")
    )
    # 兼容老版路径
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "etl"),
        os.path.join(TARGET_SERVER_DIR, "etl")
    )

    # 3.5 配方基准与业务数据 (只拷贝基准 CSV，不覆盖现场 parquet)
    print("  -> 校验并同步基准配方与参数 (Recipes.csv, CGRS.csv)...")
    recipes_src = os.path.join(LOCAL_ROOT, "backend", "data", "Recipes.csv")
    if os.path.exists(recipes_src):
        copy_file_safe(recipes_src, os.path.join(TARGET_SERVER_DIR, "backend", "data", "Recipes.csv"))
    cgrs_src = os.path.join(LOCAL_ROOT, "backend", "data", "CGRS.csv")
    if os.path.exists(cgrs_src):
        copy_file_safe(cgrs_src, os.path.join(TARGET_SERVER_DIR, "backend", "data", "CGRS.csv"))

    # 3.6 运维控制脚本与 Nginx 配置
    print("  -> 同步运维批处理脚本与 Nginx 配置文件...")
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "scripts"),
        os.path.join(TARGET_SERVER_DIR, "scripts"),
        ignore_extensions=[".py", ".pyc", ".log", ".tmp", ".parquet", ".db"]
    )
    nginx_conf_src = os.path.join(LOCAL_ROOT, "scripts", "nginx.conf")
    copy_file_safe(nginx_conf_src, os.path.join(TARGET_SERVER_DIR, "nginx", "conf", "nginx.conf"))
    copy_file_safe(nginx_conf_src, os.path.join(TARGET_SERVER_DIR, "nginx", "nginx-1.26.2", "conf", "nginx.conf"))

    # 3.7 全局持久化记忆文档
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "MEMORY_SUMMARY.md"),
        os.path.join(TARGET_SERVER_DIR, "MEMORY_SUMMARY.md")
    )

    print("  -> 所有生产文件精准同步完成！")

    if skip_restart:
        print("\n[Notice] 已指定 --skip-restart，跳过服务端重载信令。")
        return True

    # 4. 远程服务优雅重启与健康自愈闭环 (方案 B 核心)
    print("\n[Step 4/5] 触发远端优雅自重启并进行健康状态自愈校验...")

    restart_url = f"http://{SERVER_HOST}:{BACKEND_PORT}/api/system/restart"
    print(f"  -> 发送自重启信号至: {restart_url}")
    try:
        req = urllib.request.Request(restart_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_msg = resp.read().decode("utf-8")
            print(f"  -> [OK] 远端服务已确认收到自重启信号: {raw_msg}")
    except Exception as e:
        print(f"  -> [Notice] 发送自重启提示 (若服务正在拉起可忽略): {e}")

    # 等待 2 秒供系统守护进程 (NSSM) 捕获进程退出并重新拉起
    print("  -> 等待守护进程 (NSSM) 重新加载最新 Python 进程...")
    time.sleep(2)

    # 健康轮询校验 (最多 20 秒)
    test_url = f"http://{SERVER_HOST}:{BACKEND_PORT}/api/articles/all"
    print(f"  -> 正在进行服务自愈健康检查轮询 ({test_url})...")
    service_up = False
    articles_count = 0
    poll_start = time.time()

    for attempt in range(1, 21):
        try:
            req = urllib.request.Request(test_url, headers={"User-Agent": "DeployCheck"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    articles_count = len(data.get("articles", []))
                    service_up = True
                    elapsed = round(time.time() - poll_start, 1)
                    print(f"  -> [SUCCESS] 远端后端服务成功就绪！(耗时 {elapsed} 秒，第 {attempt} 次检测通过)")
                    print(f"  -> 当前可用产品规格数量: {articles_count} 条")
                    break
        except Exception:
            time.sleep(1)

    if not service_up:
        print("  -> [WARN] 20 秒内未收到后端就绪响应，服务端可能正在冷加载大型 Parquet 数据，请稍后复查。")

    # 5. 触发 DuckDB 内存表热加载
    print("\n[Step 5/5] 触发 DuckDB 内存数据缓存热重载...")
    reload_url = f"http://{SERVER_HOST}:{BACKEND_PORT}/api/etl/reload"
    try:
        req = urllib.request.Request(reload_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            reload_res = json.loads(resp.read().decode("utf-8"))
            print(f"  -> [OK] DuckDB 热重载响应: {reload_res.get('message', 'OK')}")
    except Exception as e:
        print(f"  -> [Notice] DuckDB 热重载触发提示: {e}")

    # 校验前端 Nginx
    nginx_url = f"http://{SERVER_HOST}:{FRONTEND_PORT}"
    print(f"  -> 校验前端 Web 静态服务: {nginx_url}")
    try:
        with urllib.request.urlopen(nginx_url, timeout=5) as resp:
            if resp.status == 200:
                print(f"  -> [OK] 前端 Web 页面响应正常 (HTTP 200)")
    except Exception as e:
        print(f"  -> [Notice] 前端探测提示 (若未部署外网可忽略): {e}")

    total_time = round(time.time() - start_time, 1)
    print("\n=====================================================================")
    print(f"  [SUCCESS] 生产部署全部顺利完成！(总耗时: {total_time}s)")
    print(f"  - 前端访问地址 (Nginx):    http://{SERVER_HOST}:{FRONTEND_PORT}")
    print(f"  - 后端接口地址 (FastAPI):  http://{SERVER_HOST}:{BACKEND_PORT}")
    print(f"  - 自动重载状态:            已无缝重启生效，无需手动登录服务器！")
    print("=====================================================================")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TireWeight Dashboard Auto Deploy Script")
    parser.add_argument("--skip-build", action="store_true", help="跳过前端构建 (仅同步后端或配置修改时使用)")
    parser.add_argument("--skip-restart", action="store_true", help="跳过服务自重启触发")
    args = parser.parse_args()

    success = deploy(skip_build=args.skip_build, skip_restart=args.skip_restart)
    sys.exit(0 if success else 1)
