@echo off
:: TireWeight_Uniformity_Analysis Stop Services Script
echo Stopping TireWeight_Uniformity_Analysis Services...

echo [1/3] Terminating Backend API on Port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] Terminating Frontend on Port 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [3/3] Terminating Python ETL Scheduler...
wmic process where "commandline like '%%backend.etl.scheduler%%'" call terminate >nul 2>&1

echo [SUCCESS] All services stopped successfully.
