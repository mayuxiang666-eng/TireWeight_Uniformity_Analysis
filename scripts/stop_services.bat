@echo off
:: Auto Elevate to Administrator
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Administrator Privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Stop TireWeight Uniformity Analysis Services
echo ===================================================
echo   Stopping TireWeight Uniformity Analysis Services
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
cd /d "%ROOT_DIR%"

set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"

echo [1/3] Stopping Windows System Services (FastAPI & Nginx)...
if exist %NSSM_EXE% (
    %NSSM_EXE% stop FastAPI-Service >nul 2>&1
    %NSSM_EXE% stop Nginx-Service >nul 2>&1
)
net stop FastAPI-Service >nul 2>&1
net stop Nginx-Service >nul 2>&1

echo [2/3] Terminating any orphan processes on Port 8000 & Nginx...
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($c in $conns) { $p = $c.OwningProcess; if ($p -gt 0) { Write-Host ('Terminating Port 8000 PID: ' + $p); Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }"
taskkill /F /IM nginx.exe >nul 2>&1

echo [3/3] Stopping any background ETL Scheduler processes...
wmic process where "commandline like '%%backend.etl.scheduler%%'" call terminate >nul 2>&1

timeout /t 1 /nobreak >nul
echo.
echo ===================================================
echo [SUCCESS] All TireWeight services stopped successfully!
echo ===================================================
timeout /t 3
