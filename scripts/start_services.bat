@echo off
:: TireWeight_Uniformity_Analysis Start Services Script
echo Starting TireWeight_Uniformity_Analysis Services...

set ROOT_DIR=%~dp0..
cd /d "%ROOT_DIR%"

set PYTHON_CMD=python
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set PYTHON_CMD="%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe" (
    set PYTHON_CMD="C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe"
)

echo [1/2] Starting Unified FastAPI Backend & Frontend Web Service (Port 8000)...
start "Backend_API_Port8000" %PYTHON_CMD% backend\run_server.py

echo [2/2] Starting ETL Scheduler Daemon (Every 30 Minutes)...
start "ETL_Scheduler_30Min" %PYTHON_CMD% -m backend.etl.scheduler --interval 30

echo.
echo [SUCCESS] All Production Services Launched!
echo Web UI & API: http://127.0.0.1:8000
echo ===================================================
