@echo off
chcp 65001 >nul
title TireWeight Uniformity Analysis Health Check

echo ===================================================
echo TireWeight_Uniformity_Analysis Health Check
echo ===================================================

echo [1/3] Checking Port 80 (Nginx):
netstat -aon | findstr ":80 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   STATUS: RUNNING (Port 80 is listening)
) else (
    echo   STATUS: STOPPED (Port 80 not listening)
)
echo.

echo [2/3] Checking Port 8000 (FastAPI Backend):
netstat -aon | findstr ":8000 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   STATUS: RUNNING (Port 8000 is listening)
) else (
    echo   STATUS: STOPPED (Port 8000 not listening)
)
echo.

echo [3/3] Fetching DuckDB Data Status...
powershell -NoProfile -Command "$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/etl/status' -ErrorAction SilentlyContinue; if ($r) { Write-Host ('  -> Data Path: ' + $r.data.data_path); Write-Host ('  -> Last Modified: ' + $r.data.last_modified); Write-Host ('  -> Loaded Rows: ' + $r.data.loaded_rows + ' rows'); } else { Write-Host '  -> Backend API loading or unreachable'; }"

echo ===================================================
echo.
echo Press any key to exit status check...
pause >nul
