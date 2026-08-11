@echo off
:: TireWeight_Uniformity_Analysis Service Status Checker
echo ===================================================
echo   TireWeight Uniformity Analysis Status Check
echo ===================================================
echo.

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
set DATA_PATH=%ROOT_DIR%\backend\data\yield_flat_table_joined_100_cleaned.parquet

:: 1. Check Nginx Port 8088
echo [1/3] Checking Nginx Port 8088...
netstat -aon | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] Nginx is RUNNING on Port 8088
) else (
    echo       [FAIL] Nginx is NOT listening on Port 8088
)
echo.

:: 2. Check FastAPI Port 8000
echo [2/3] Checking FastAPI Backend Port 8000...
netstat -aon | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo       [OK] FastAPI Service is RUNNING on Port 8000
) else (
    echo       [FAIL] FastAPI Service is NOT listening on Port 8000
)
echo.

:: 3. Check Parquet Data File Status
echo [3/3] Checking Parquet Dataset...
if exist "%DATA_PATH%" (
    echo       [OK] Cleaned Parquet file exists:
    dir "%DATA_PATH%" | findstr "cleaned.parquet"
) else (
    echo       [FAIL] Cleaned Parquet file missing at %DATA_PATH%
)
echo.

echo ===================================================
echo Status Inspection Completed!
echo Primary Access URL:   http://10.246.97.159:8088
echo Direct FastAPI URL:   http://10.246.97.159:8000
echo ===================================================
pause
