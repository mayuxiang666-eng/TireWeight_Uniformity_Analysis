@echo off
:: TireWeight_Uniformity_Analysis Stop Services Script
echo Stopping TireWeight_Uniformity_Analysis Services...

echo [1/2] Terminating Backend & Web Service on Port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/2] Terminating Python ETL Scheduler Daemon...
wmic process where "commandline like '%%backend.etl.scheduler%%'" call terminate >nul 2>&1

echo [SUCCESS] All services stopped successfully.
echo ===================================================
