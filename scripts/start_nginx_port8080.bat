@echo off
:: TireWeight_Uniformity_Analysis Nginx Port 8080 Launcher
echo Starting Nginx Service on Port 8080...

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

echo Found Nginx executable in: %NGINX_DIR%

cd /d "%NGINX_DIR%"
nginx.exe -s stop >nul 2>&1
taskkill /F /IM nginx.exe >nul 2>&1

echo Starting Nginx on Port 8080 with config %ROOT_DIR%\scripts\nginx.conf ...
start "" nginx.exe -c "%ROOT_DIR%\scripts\nginx.conf"

timeout /t 2 >nul
netstat -aon | findstr ":8080 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [SUCCESS] Nginx is RUNNING on Port 8080!
    echo Access URL: http://10.246.97.159:8080
    echo ===================================================
) else (
    echo.
    echo [WARN] Could not find listener on Port 8080 yet.
)
echo.
pause
