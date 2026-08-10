import os
import sys
import shutil
import subprocess

TARGET_SERVER_DIR = r"\\10.246.97.159\tu ai\TireWeight_Uniformity_Analysis"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

def run_cmd(cmd, cwd=None):
    print(f">> 正在执行命令: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd or LOCAL_ROOT)
    if res.returncode != 0:
        print(f"[Error] 命令执行失败: {cmd}")
        return False
    return True

def copy_dir_filtered(src, dst, ignore_patterns=None):
    if not os.path.exists(src):
        return
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel_path) if rel_path != "." else dst
        
        # 过滤忽略目录
        dirs[:] = [d for d in dirs if d not in (ignore_patterns or [])]
        
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            if any(f.endswith(ext) for ext in [".parquet", ".duckdb-wal", ".pyc", ".log"]):
                continue
            src_file = os.path.join(root, f)
            dst_file = os.path.join(target_dir, f)
            try:
                shutil.copy2(src_file, dst_file)
            except Exception as e:
                print(f"[Warn] 复制文件 {f} 跳过或遇到占用: {e}")

def deploy():
    print(f"===================================================")
    print(f"开始发布项目至服务器: {TARGET_SERVER_DIR}")
    print(f"===================================================")
    
    # 1. 编译前端
    print("\n[Step 1/3] 编译构建前端 dist...")
    if not run_cmd("npm run build"):
        print("[ERR] 前端编译失败，中断部署。")
        return False
        
    # 2. 创建目标目录
    os.makedirs(TARGET_SERVER_DIR, exist_ok=True)
    
    # 3. 同步文件
    print(f"\n[Step 2/3] 同步文件至服务器共享目录 {TARGET_SERVER_DIR}...")
    
    # 静态前端产物 dist
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "dist"), 
        os.path.join(TARGET_SERVER_DIR, "dist")
    )
    
    # 后端应用与 ETL backend
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "backend"), 
        os.path.join(TARGET_SERVER_DIR, "backend"),
        ignore_patterns=["__pycache__"]
    )
    
    # 运维控制脚本 scripts
    copy_dir_filtered(
        os.path.join(LOCAL_ROOT, "scripts"), 
        os.path.join(TARGET_SERVER_DIR, "scripts")
    )
    
    # 项目元文件
    meta_files = ["package.json", "package-lock.json", "README.md", "vite.config.js"]
    for mf in meta_files:
        src_f = os.path.join(LOCAL_ROOT, mf)
        if os.path.exists(src_f):
            shutil.copy2(src_f, os.path.join(TARGET_SERVER_DIR, mf))
            
    print(f"\n[Step 3/3] 校验服务器文件同步状态...")
    if os.path.exists(os.path.join(TARGET_SERVER_DIR, "backend", "main.py")):
        print(f"[SUCCESS] 项目文件已成功部署至 {TARGET_SERVER_DIR}")
        return True
    else:
        print(f"[ERR] 部署校验未通过！")
        return False

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
