@echo off
:: TireWeight_Uniformity_Analysis Full 31-Day Fetch Script
echo ===================================================
echo Starting Full 31-Day Data Fetch from Amazon Redshift...
echo ===================================================

cd /d "D:\TU AI\TireWeight_Uniformity_Analysis"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PYTHON_EXE%" (
    if exist "D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe" (
        set PYTHON_EXE=D:\TU AI\TireWeight_Uniformity_Analysis\backend\venv\Scripts\python.exe
    ) else (
        set PYTHON_EXE=python.exe
    )
)

mkdir logs\etl >nul 2>&1

echo. >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log
echo [%date% %time%] Starting FULL 31-Day ETL Pipeline... >> logs\etl\etl.log

"%PYTHON_EXE%" -m backend.etl.run_pipeline --full-fetch

echo [%date% %time%] Full ETL finished with exit code: %errorlevel% >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log

echo.
echo ===================================================
echo [SUCCESS] Full 31-Day Data Fetch & Clean Completed!
echo ===================================================
pause
