@echo off
:: TireWeight_Uniformity_Analysis Status Checker
title TireWeight Service Status Check
echo ===================================================
echo   TireWeight Uniformity Analysis Service Status
echo ===================================================
echo.

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
set DATA_PATH=%ROOT_DIR%\backend\data\yield_flat_table_joined_100_cleaned.parquet

:: 1. Check Nginx Port 8088
echo [1/4] Checking Nginx Frontend Web Server (Port 8088)...
netstat -aon | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Nginx is RUNNING on Port 8088 - Web UI: http://10.246.97.159:8088
) else (
    echo       [FAIL] Nginx is NOT listening on Port 8088
)
echo.

:: 2. Check FastAPI Port 8000
echo [2/4] Checking FastAPI Backend Service (Port 8000)...
netstat -aon | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] FastAPI Service is RUNNING on Port 8000
) else (
    echo       [FAIL] FastAPI Service is NOT listening on Port 8000
)
echo.

:: 3. Live API Health Inspection
echo [3/4] Probing Backend API Endpoints...
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/articles/all' -TimeoutSec 3; Write-Host ('      [OK] API Online. Active Articles: ' + $r.data.Count); } catch { Write-Host '      [FAIL] Backend API unresponsive' }"
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/etl/status' -TimeoutSec 3; Write-Host ('      [OK] ETL Data Loaded: ' + $r.data.loaded_rows + ' rows (Size: ' + $r.data.size_mb + ' MB)'); } catch { }"
echo.

:: 4. Check Cleaned Parquet Dataset on Disk
echo [4/4] Checking Cleaned Parquet Dataset on Disk...
if exist "%DATA_PATH%" (
    echo       [OK] Dataset exists: %DATA_PATH%
) else (
    echo       [FAIL] Dataset file missing at: %DATA_PATH%
)
echo.

echo ===================================================
echo Primary Access URL: http://10.246.97.159:8088
echo Direct Backend URL: http://10.246.97.159:8000
echo ===================================================
echo.
pause
