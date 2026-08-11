@echo off
:: TireWeight_Uniformity_Analysis Nginx Port 8088 Launcher
echo Starting Nginx Service on Port 8088 for TireWeight Uniformity Analysis...

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
set NGINX_DIR=%ROOT_DIR%\nginx

if exist "%NGINX_DIR%\nginx-1.26.2\nginx.exe" (
    set NGINX_DIR=%NGINX_DIR%\nginx-1.26.2
) else if exist "%NGINX_DIR%\nginx-1.26.1\nginx.exe" (
    set NGINX_DIR=%NGINX_DIR%\nginx-1.26.1
) else if exist "%ROOT_DIR%\nginx-1.26.2\nginx.exe" (
    set NGINX_DIR=%ROOT_DIR%\nginx-1.26.2
) else if exist "C:\nginx\nginx.exe" (
    set NGINX_DIR=C:\nginx
) else if exist "D:\nginx\nginx.exe" (
    set NGINX_DIR=D:\nginx
)

if not exist "%NGINX_DIR%\nginx.exe" (
    echo [ERROR] Could not find nginx.exe in %NGINX_DIR%
    pause
    exit /b 1
)

copy /Y "%ROOT_DIR%\scripts\nginx.conf" "%NGINX_DIR%\conf\nginx.conf" >nul 2>&1

cd /d "%NGINX_DIR%"
nginx.exe -s stop >nul 2>&1
taskkill /F /IM nginx.exe >nul 2>&1

echo Starting Nginx with TireWeight Uniformity Analysis config...
start "" nginx.exe -c "%ROOT_DIR%\scripts\nginx.conf"

timeout /t 2 >nul
netstat -aon | findstr ":8088 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [SUCCESS] TireWeight Dashboard Nginx is RUNNING on Port 8088!
    echo Access URL: http://10.246.97.159:8088
    echo ===================================================
) else (
    echo.
    echo [WARN] Could not find listener on Port 8088 yet.
)
echo.
pause
