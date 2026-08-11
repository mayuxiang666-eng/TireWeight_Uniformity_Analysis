@echo off
:: TireWeight_Uniformity_Analysis Windows Task Scheduler Installer for ETL
echo ===================================================
echo 正在注册 ETL_JOB 每 30 分钟轮询 Windows 计划任务...
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
set LOG_DIR=%ROOT_DIR%\logs\etl
mkdir "%LOG_DIR%" >nul 2>&1

set PYTHON_EXE=python.exe
if exist "%ROOT_DIR%\backend\venv\Scripts\python.exe" (
    set PYTHON_EXE=%ROOT_DIR%\backend\venv\Scripts\python.exe
) else if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe
) else if exist "C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe" (
    set PYTHON_EXE=C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe
)

echo 注册计划任务 ETL_JOB (每 30 分钟触发拉取清洗与热更新)...
schtasks /create /tn "ETL_JOB" /tr "\"%PYTHON_EXE%\" -m backend.etl.run_pipeline" /sc minute /mo 30 /ru SYSTEM /f

if %errorlevel% equ 0 (
    echo [SUCCESS] Windows 计划任务 "ETL_JOB" 注册成功！
    echo 触发频率: 每 30 分钟全自动轮询 Redshift 拉取清洗并通知热重载。
) else (
    echo [NOTICE] 注册需管理员权限，请尝试右键以管理员身份运行此脚本。
)
echo ===================================================
pause
