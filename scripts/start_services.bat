@echo off
:: Auto Elevate to Administrator
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Administrator Privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Start TireWeight Uniformity Analysis Services
echo ===================================================
echo   Starting TireWeight Uniformity Analysis Services
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
cd /d "%ROOT_DIR%"

set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"

echo [1/2] Starting / Verifying FastAPI Backend (Port 8000)...
if exist %NSSM_EXE% (
    %NSSM_EXE% start FastAPI-Service >nul 2>&1
)
net start FastAPI-Service >nul 2>&1

timeout /t 2 /nobreak >nul
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo Standalone Python launching on Port 8000...
    powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($c in $conns) { $p = $c.OwningProcess; if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }"
    start "FastAPI_Port8000" python run_server.py
)

echo [2/2] Starting / Verifying Nginx Frontend (Port 8088)...
if exist %NSSM_EXE% (
    %NSSM_EXE% start Nginx-Service >nul 2>&1
)
net start Nginx-Service >nul 2>&1

timeout /t 2 /nobreak >nul
netstat -ano | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo Standalone Nginx launching on Port 8088...
    if exist "%ROOT_DIR%\scripts\start_nginx.bat" (
        call "%ROOT_DIR%\scripts\start_nginx.bat"
    )
)

timeout /t 2 /nobreak >nul
echo.
echo ===================================================
echo [SUCCESS] Services Checked!
echo Frontend Web UI: http://10.246.97.159:8088
echo Backend API:     http://10.246.97.159:8000
echo ===================================================
timeout /t 3
