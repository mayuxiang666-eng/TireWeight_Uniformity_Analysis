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

echo [1/3] Starting FastAPI Backend (Port 8000)...
start /B "" %PYTHON_CMD% backend\run_server.py > logs_backend.log 2>&1

echo [2/3] Starting ETL Scheduler Daemon (Every 30 Minutes)...
start /B "" %PYTHON_CMD% -m backend.etl.scheduler --interval 30 > logs_etl.log 2>&1

echo [3/3] Starting Frontend Service (Port 5173)...
start /B "" npx vite preview --host 0.0.0.0 --port 5173 > logs_frontend.log 2>&1

echo.
echo [SUCCESS] Services launched in background.
echo Backend API: http://127.0.0.1:8000
echo Frontend UI: http://127.0.0.1:5173
echo ===================================================
