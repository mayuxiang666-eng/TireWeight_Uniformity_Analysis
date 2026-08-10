import os
import sys
import subprocess

# 1. 自动检查并安装 Python 生产依赖包
REQUIRED_PACKAGES = ["fastapi", "uvicorn", "duckdb", "pandas", "sklearn", "psycopg2", "pyarrow"]

def ensure_dependencies():
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
            
    if missing:
        print(f"[Notice] 检测到缺少依赖包 {missing}，正在自动为您安装...")
        req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("[SUCCESS] 依赖包安装完成！")
        except Exception as e:
            print(f"[Warn] pip 默认安装失败，尝试以 --user 方式安装: {e}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "--user"])

ensure_dependencies()

import uvicorn

if __name__ == "__main__":
    # 在生产部署环境中设置 reload=False 避免多进程 Spawn 时的加载死锁
    print("正在启动 FastAPI 后端服务 (端口 8000)...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
