@echo off
:: TireWeight_Uniformity_Analysis Nginx Port 8080 Launcher
echo Starting Nginx Service on Port 8080...

set NGINX_DIR=D:\TU AI\TireWeight_Uniformity_Analysis\nginx
if not exist "%NGINX_DIR%\nginx.exe" (
    if exist "C:\nginx\nginx.exe" set NGINX_DIR=C:\nginx
    if exist "D:\nginx\nginx.exe" set NGINX_DIR=D:\nginx
)

if not exist "%NGINX_DIR%\nginx.exe" (
    echo [ERROR] Could not find nginx.exe in %NGINX_DIR%
    echo Please download and extract Nginx into D:\TU AI\TireWeight_Uniformity_Analysis\nginx
    pause
    exit /b 1
)

cd /d "%NGINX_DIR%"
nginx.exe -s stop >nul 2>&1
taskkill /F /IM nginx.exe >nul 2>&1

echo Starting Nginx with configuration D:\TU AI\TireWeight_Uniformity_Analysis\scripts\nginx.conf ...
start "" nginx.exe -c "D:\TU AI\TireWeight_Uniformity_Analysis\scripts\nginx.conf"

timeout /t 2 >nul
netstat -aon | findstr ":8080 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo [SUCCESS] Nginx is RUNNING on Port 8080!
    echo Access URL: http://10.246.97.159:8080
) else (
    echo [WARN] Could not bind to Port 8080. Please check logs/error.log.
)
echo ===================================================
pause
