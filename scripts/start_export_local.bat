@echo off
title CGRS 数据自动同步与导出
echo =======================================================
echo     CGRS 数据同步 (增量参数偏移 + 全量生效配方)
echo =======================================================
echo.

set "PYTHON_EXE=C:\Users\uif35346\AppData\Local\Programs\Python\Python312\python.exe"
set "BASE_DIR=\\10.246.97.159\d\TU AI\TireWeight_Uniformity_Analysis"

echo [1/2] 正在运行 CGRS 关键参数偏移增量导出 (119 KM + 125 PU + 123 Curing)...
"%PYTHON_EXE%" "%BASE_DIR%\backend\etl\export_cgrs_parquet.py"
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 增量导出遇到问题，退出码: %ERRORLEVEL%
) else (
    echo [完成] 增量导出顺利完成！
)
echo.

echo [2/2] 正在运行 CGRS 全量生效配方参数每日自检校准与补齐导出...
"%PYTHON_EXE%" "%BASE_DIR%\backend\etl\export_cgrs_full_history.py"
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 全量配方导出遇到问题，退出码: %ERRORLEVEL%
) else (
    echo [完成] 全量配方导出顺利完成！
)
echo.

echo =======================================================
echo 数据已自动同步并存储至服务器：
echo   - 增量数据: %BASE_DIR%\cgrs_data
echo   - 全量配方: %BASE_DIR%\CGRS_full_history_data
echo =======================================================

if "%~1"=="--silent" goto :end
if "%~1"=="silent" goto :end

echo.
echo 同步任务已全部执行完毕。
pause

:end
