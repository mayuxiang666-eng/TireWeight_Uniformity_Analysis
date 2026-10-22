@echo off
:: TireWeight_Uniformity_Analysis ETL Job Execution Script

:: ===== 全链路 UTF-8 编码锁定 =====
chcp 65001 >nul 2>&1

echo ===================================================
echo  ETL Data Fetch, Clean and Reload
echo ===================================================

:: 1. Change directory to project root (parent directory of scripts/)
cd /d "%~dp0.."

:: 2. Set UTF-8 environment variables for Python
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8:replace
set PYTHONUNBUFFERED=1

:: 3. Find Python absolute path
set "PYTHON_EXE="
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
) else if exist "d:\Ava\untitled1\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=d:\Ava\untitled1\.venv\Scripts\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe"
) else if exist "%~dp0..\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\backend\venv\Scripts\python.exe"
) else if exist "%~dp0..\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python313\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
) else if exist "C:\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python313\python.exe"
) else (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)
if not defined PYTHON_EXE set "PYTHON_EXE=python.exe"

:: 4. Create log directory
mkdir logs\etl >nul 2>&1

echo.
echo [%date% %time%] Starting ETL Pipeline...
echo ---------------------------------------------------
echo Starting ETL pipeline... please wait.
echo ---------------------------------------------------

:: 5. Run Python with full UTF-8 chain:
::    - PowerShell sets its own console encoding to UTF-8
::    - Python -X utf8 forces UTF-8 mode at interpreter level
::    - Tee-Object -Encoding UTF8 writes log file as UTF-8
set "LOG_FILE=logs\etl\etl.log"
"%PYTHON_EXE%" -u -X utf8 -m backend.etl.run_pipeline 2>&1 | "%PYTHON_EXE%" -u -X utf8 scripts\tee_utf8.py "%LOG_FILE%"
set EXIT_CODE=%errorlevel%

echo.
echo ---------------------------------------------------
if %EXIT_CODE% equ 0 (
    echo [SUCCESS] ETL Pipeline finished successfully!
) else (
    echo [ERROR] ETL Pipeline failed, exit code: %EXIT_CODE%
)
echo Log saved to: %LOG_FILE%
echo ---------------------------------------------------

timeout /t 20
exit /b %EXIT_CODE%

:: 3. Find Python absolute path (Intelligent multi-tier fallback)
set "PYTHON_EXE="
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
) else if exist "d:\Ava\untitled1\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=d:\Ava\untitled1\.venv\Scripts\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe"
) else if exist "%~dp0..\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\backend\venv\Scripts\python.exe"
) else if exist "%~dp0..\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python313\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
) else if exist "C:\Program Files\Python311\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
) else if exist "C:\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python313\python.exe"
) else (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE set "PYTHON_EXE=python.exe"

:: 4. Create log directory
mkdir logs\etl >nul 2>&1

:: 5. Write start timestamp to log
echo. >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log
echo [%date% %time%] Starting ETL Pipeline... >> logs\etl\etl.log

:: 6. Run Python ETL pipeline and show output on screen while appending to log
echo ---------------------------------------------------
echo 正在执行增量数据拉取与清洗管道...
echo (实时进度与耗时将同步显示在控制台，并记录至 logs\etl\etl.log)
echo ---------------------------------------------------

powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%PYTHON_EXE%' -u -m backend.etl.run_pipeline | Tee-Object -FilePath 'logs\etl\etl.log' -Append"
set EXIT_CODE=%errorlevel%

echo [%date% %time%] ETL Pipeline finished with exit code: %EXIT_CODE% >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log

echo.
echo ===================================================
if %EXIT_CODE% equ 0 (
    echo [SUCCESS] ETL Pipeline 运行成功！
) else (
    echo [ERROR] ETL Pipeline 运行异常，退出码: %EXIT_CODE%
)
echo 详细日志已同步保存在: logs\etl\etl.log
echo ===================================================

:: 倒计时等待，方便手动双击验证时查看执行耗时与日志
timeout /t 15
exit /b %EXIT_CODE%
