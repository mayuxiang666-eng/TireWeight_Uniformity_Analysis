@echo off
:: TireWeight_Uniformity_Analysis Windows Task Scheduler Installer for ETL
echo ===================================================
echo Registering ETL_JOB Task Scheduler (30-min interval)...
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
set LOG_DIR=%ROOT_DIR%\logs\etl

mkdir "%LOG_DIR%" >nul 2>&1

set JOB_BAT=%ROOT_DIR%\scripts\run_etl_job.bat

if not exist "%JOB_BAT%" (
    echo [ERROR] Launcher script not found: %JOB_BAT%
    pause
    exit /b 1
)

echo Creating Task Scheduler "ETL_JOB"...
schtasks /create /tn "ETL_JOB" /tr "\"%JOB_BAT%\"" /sc minute /mo 30 /ru SYSTEM /f

if %errorlevel% equ 0 (
    echo [SUCCESS] Windows Task Scheduler "ETL_JOB" created successfully!
    echo Frequency: Every 30 minutes automatic data fetch, clean and reload.
) else (
    echo [NOTICE] Administrator privileges required. Please right-click and run as Administrator.
)
echo ===================================================
pause
