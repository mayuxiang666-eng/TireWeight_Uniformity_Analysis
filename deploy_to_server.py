import os
import sys
import shutil
import subprocess

TARGET_SERVER_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

def run_cmd(cmd, cwd=None):
    print(f">> 正在执行本地构建命令: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd or LOCAL_ROOT)
    if res.returncode != 0:
        print(f"[Error] 构建命令执行失败: {cmd}")
        return False
    return True

def copy_file_safe(src, dst):
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[Warn] 复制文件 {os.path.basename(src)} 提示: {e}")

def copy_dir_filtered(src, dst, ignore_names=None):
    if not os.path.exists(src):
        return
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        
        # 过滤目录
        dirs[:] = [d for d in dirs if d not in (ignore_names or [])]
        os.makedirs(target_dir, exist_ok=True)
        
        for f in files:
            if any(f.endswith(ext) for ext in [".parquet", ".duckdb-wal", ".pyc", ".log", ".tmp"]):
                continue
            src_f = os.path.join(root, f)
            dst_f = os.path.join(target_dir, f)
            try:
                shutil.copy2(src_f, dst_f)
            except Exception as e:
                print(f"[Warn] 复制 {f} 跳过: {e}")

def deploy():
    print("===================================================")
    print(f"开始按照规范目录部署发布至: {TARGET_SERVER_DIR}")
    print("===================================================")
    
    # 1. 本地前端编译
    print("\n[Step 1/4] 编译构建 Vue 静态应用 (dist)...")
    if not run_cmd("npm run build"):
        print("[ERR] 前端编译失败，终止发布。")
        return False
        
    # 2. 创建服务器端规范根目录及子目录
    os.makedirs(TARGET_SERVER_DIR, exist_ok=True)
    dirs_to_create = [
        "frontend/dist",
        "backend/config",
        "etl/output",
        "nginx/conf",
        "logs/fastapi",
        "logs/nginx",
        "logs/etl",
        "scripts"
    ]
    for d in dirs_to_create:
        os.makedirs(os.path.join(TARGET_SERVER_DIR, d), exist_ok=True)
        
    print(f"\n[Step 2/4] 同步前端与后端模块...")
    # 前端静态包
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "dist"),
        os.path.join(TARGET_SERVER_DIR, "frontend", "dist")
    )
    
    # 后端应用
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend"),
        os.path.join(TARGET_SERVER_DIR, "backend"),
        ignore_names=["__pycache__", "etl", "data"]
    )
    
    # 后端配置
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "config"),
        os.path.join(TARGET_SERVER_DIR, "backend", "config")
    )
    
    print(f"\n[Step 3/4] 同步 ETL 数据处理管道与配方表...")
    # ETL 逻辑
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend", "etl"),
        os.path.join(TARGET_SERVER_DIR, "etl"),
        ignore_names=["__pycache__"]
    )
    
    # 配方基准表 Recipes.csv
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "backend", "data", "Recipes.csv"),
        os.path.join(TARGET_SERVER_DIR, "etl", "output", "Recipes.csv")
    )
    
    print(f"\n[Step 4/4] 同步 Nginx 配置与运维控制脚本...")
    # Nginx 配置
    copy_file_safe(
        os.path.join(LOCAL_ROOT, "scripts", "nginx.conf"),
        os.path.join(TARGET_SERVER_DIR, "nginx", "conf", "nginx.conf")
    )
    
    # 控制脚本
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "scripts"),
        os.path.join(TARGET_SERVER_DIR, "scripts")
    )
    
    print("\n[SUCCESS] 发布校验通过！项目文件已成功同步至服务器规范目录：")
    print(f"  - 前端静态包: {TARGET_SERVER_DIR}\\frontend\\dist")
    print(f"  - 后端应用:   {TARGET_SERVER_DIR}\\backend")
    print(f"  - ETL 模块:   {TARGET_SERVER_DIR}\\etl")
    print(f"  - 运维脚本:   {TARGET_SERVER_DIR}\\scripts")
    print("===================================================")
    return True

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
