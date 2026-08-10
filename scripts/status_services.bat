@echo off
:: TireWeight_Uniformity_Analysis Status Script
echo ===================================================
echo TireWeight_Uniformity_Analysis Status Check
echo ===================================================

echo [1/3] Backend Port 8000:
netstat -aon | findstr ":8000" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   -> Backend API: RUNNING
) else (
    echo   -> Backend API: STOPPED
)
echo.

echo [2/3] Frontend Port 5173:
netstat -aon | findstr ":5173" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   -> Frontend UI: RUNNING
) else (
    echo   -> Frontend UI: STOPPED
)
echo.

echo [3/3] ETL Data Status:
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/etl/status' -TimeoutSec 3; Write-Host ('  -> Data Path: ' + $r.data.data_path); Write-Host ('  -> Last Modified: ' + $r.data.last_modified); Write-Host ('  -> Data Size: ' + $r.data.size_mb + ' MB'); Write-Host ('  -> Loaded Rows: ' + $r.data.loaded_rows + ' rows'); } catch { Write-Host '  -> Backend API unreachable' }"

echo ===================================================
echo.
pause
