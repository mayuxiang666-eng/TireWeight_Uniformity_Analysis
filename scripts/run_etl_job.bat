@echo off
:: TireWeight_Uniformity_Analysis ETL Job Execution Script for Windows Task Scheduler
echo ===================================================
echo 正在执行 30 分钟 ETL 数据拉取、清洗与热重载...
echo ===================================================

:: 1. 强制切换到项目绝对根目录，确保 Python 模块包路径正常解析
cd /d "D:\TU AI\TireWeight_Uniformity_Analysis"

:: 2. 设置 UTF-8 编码环境
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 3. 寻找 Python 绝对路径
set PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PYTHON_EXE%" (
    if exist "D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe" (
        set PYTHON_EXE=D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe
    ) else (
        set PYTHON_EXE=python.exe
    )
)

:: 4. 创建日志目录
mkdir logs\etl >nul 2>&1

:: 5. 执行 ETL 管道并追加记录日志
echo. >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log
echo [%date% %time%] 启动定时 ETL 数据抽取与清洗... >> logs\etl\etl.log

"%PYTHON_EXE%" -m backend.etl.run_pipeline >> logs\etl\etl.log 2>&1

echo [%date% %time%] ETL 任务完成，退出码: %errorlevel% >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log

echo.
echo ===================================================
echo [SUCCESS] ETL 流程执行完毕，已记录日志至 logs\etl\etl.log
echo ===================================================
