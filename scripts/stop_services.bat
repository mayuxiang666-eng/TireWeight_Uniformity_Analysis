@echo off
:: Auto Elevate to Administrator
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Stop TireWeight Services
echo ===================================================
echo   Stopping TireWeight Uniformity Analysis Services
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
cd /d "%ROOT_DIR%"

set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"
if exist %NSSM_EXE% (
    %NSSM_EXE% stop FastAPI-Service >nul 2>&1
    %NSSM_EXE% stop Nginx-Service >nul 2>&1
)
net stop FastAPI-Service >nul 2>&1
net stop Nginx-Service >nul 2>&1

:: 强制清理任何占用 8088 和 8000 端口的进程与残留 nginx
taskkill /F /IM nginx.exe >nul 2>&1
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8088,8000 -ErrorAction SilentlyContinue; foreach ($c in $conns) { if ($c.OwningProcess -gt 0) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } }"

echo.
echo [OK] All Services Stopped cleanly.
timeout /t 2
