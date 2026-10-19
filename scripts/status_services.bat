@echo off
:: TireWeight_Uniformity_Analysis Status Checker (Port 8088)
title TireWeight Service Status Check (Port 8088)
echo ===================================================
echo   TireWeight Uniformity Analysis Service Status
echo ===================================================
echo.

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
set DATA_PATH=%ROOT_DIR%\backend\data\yield_flat_table_joined_100_cleaned.parquet

:: 1. Check Port 8088
echo [1/3] Checking All-in-One Dashboard Service (Port 8088)...
netstat -aon | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Service is RUNNING on Port 8088 - URL: http://10.246.97.159:8088
) else (
    echo       [FAIL] Service is NOT listening on Port 8088
)
echo.

:: 2. Live API Health Inspection
echo [2/3] Probing Live Health Endpoints...
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/api/articles/all' -TimeoutSec 3; Write-Host ('      [OK] API & Web Online. Active Articles: ' + $r.data.Count); } catch { Write-Host '      [FAIL] Backend API unresponsive' }"
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/api/etl/status' -TimeoutSec 3; Write-Host ('      [OK] ETL Data Loaded: ' + $r.data.loaded_rows + ' rows (Size: ' + $r.data.size_mb + ' MB)'); } catch { }"
echo.

:: 3. Check Cleaned Parquet Dataset on Disk
echo [3/3] Checking Cleaned Parquet Dataset on Disk...
if exist "%DATA_PATH%" (
    echo       [OK] Dataset exists: %DATA_PATH%
) else (
    echo       [FAIL] Dataset file missing at: %DATA_PATH%
)
echo.

echo ===================================================
echo Primary Access URL: http://10.246.97.159:8088
echo Architecture:       Pure FastAPI (Unified Web & API)
echo ===================================================
echo.
pause
