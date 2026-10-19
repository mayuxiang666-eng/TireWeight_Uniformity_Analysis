@echo off
:: Auto Elevate to Administrator
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Administrator Privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Start TireWeight Uniformity Analysis Services (Port 8088)
echo ===================================================
echo   Starting TireWeight Dashboard Service (Port 8088)
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
cd /d "%ROOT_DIR%"

set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"

echo [1/1] Starting / Verifying FastAPI Service (Port 8088)...
if exist %NSSM_EXE% (
    %NSSM_EXE% start FastAPI-Service >nul 2>&1
)
net start FastAPI-Service >nul 2>&1

timeout /t 3 /nobreak >nul
netstat -ano | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo Standalone Python launching on Port 8088...
    powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8088 -ErrorAction SilentlyContinue; foreach ($c in $conns) { $p = $c.OwningProcess; if ($p -gt 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }"
    start "FastAPI_Port8088" python run_server.py
)

timeout /t 2 /nobreak >nul
echo.
echo ===================================================
echo [SUCCESS] Service Checked!
echo Access URL: http://10.246.97.159:8088
echo ===================================================
timeout /t 3
