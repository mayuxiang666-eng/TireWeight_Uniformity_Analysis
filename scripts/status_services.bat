@echo off
:: TireWeight_Uniformity_Analysis Status Script
echo ===================================================
echo TireWeight_Uniformity_Analysis Status Check
echo ===================================================

echo [1/2] Web UI & Backend API (Port 8000):
netstat -aon | findstr ":8000" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   -> Unified Web UI & Backend API: RUNNING
) else (
    echo   -> Unified Web UI & Backend API: STOPPED
)
echo.

echo [2/2] ETL Data Status:
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/etl/status' -TimeoutSec 3; Write-Host ('  -> Data Path: ' + $r.data.data_path); Write-Host ('  -> Last Modified: ' + $r.data.last_modified); Write-Host ('  -> Data Size: ' + $r.data.size_mb + ' MB'); Write-Host ('  -> Loaded Rows: ' + $r.data.loaded_rows + ' rows'); } catch { Write-Host '  -> Service unreachable' }"

echo ===================================================
echo.
pause
