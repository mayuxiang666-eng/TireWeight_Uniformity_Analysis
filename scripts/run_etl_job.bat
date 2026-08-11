@echo off
:: TireWeight_Uniformity_Analysis ETL Job Execution Script
echo ===================================================
echo Starting 30-minute ETL Data Fetch, Clean and Reload...
echo ===================================================

:: 1. Change directory to absolute project root
cd /d "D:\TU AI\TireWeight_Uniformity_Analysis"

:: 2. Set UTF-8 environment
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 3. Find Python absolute path
set PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PYTHON_EXE%" (
    if exist "D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe" (
        set PYTHON_EXE=D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe
    ) else (
        set PYTHON_EXE=python.exe
    )
)

:: 4. Create log directory
mkdir logs\etl >nul 2>&1

:: 5. Write start timestamp to log
echo. >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log
echo [%date% %time%] Starting ETL Pipeline... >> logs\etl\etl.log

:: 6. Run Python ETL pipeline directly to show LIVE REAL-TIME output on console
"%PYTHON_EXE%" -m backend.etl.run_pipeline

echo [%date% %time%] ETL Pipeline finished with exit code: %errorlevel% >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log

echo.
echo ===================================================
echo [SUCCESS] ETL Pipeline execution completed!
echo Log file appended to logs\etl\etl.log
echo ===================================================
pause
