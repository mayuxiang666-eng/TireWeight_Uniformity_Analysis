@echo off
:: TireWeight_Uniformity_Analysis Free Port 80 & Launch Nginx Script
echo ===================================================
echo 正在排查并释放服务器 80 端口 (停止 IIS 占用)...
echo ===================================================

:: 1. 停止 Windows IIS Web 服务 (W3SVC) 释放 80 端口
echo [1/3] 停止服务器自带的 IIS (W3SVC) 服务...
net stop w3svc /y >nul 2>&1
sc config w3svc start= disabled >nul 2>&1

echo [2/3] 检查 80 端口占用情况...
netstat -aon | findstr ":80 " | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo [NOTICE] 80 端口仍被其他进程占用，请查看 PID。
) else (
    echo [SUCCESS] 80 端口已成功释放！
)

:: 2. 修改 nginx.conf 为 80 端口
set NGINX_CONF=D:\TU AI\TireWeight_Uniformity_Analysis\scripts\nginx.conf
powershell -Command "(Get-Content '%NGINX_CONF%') -replace 'listen       8080;', 'listen       80;' | Set-Content '%NGINX_CONF%'" >nul 2>&1

:: 3. 启动 Nginx
set NGINX_DIR=D:\TU AI\TireWeight_Uniformity_Analysis\nginx
if not exist "%NGINX_DIR%\nginx.exe" (
    if exist "C:\nginx\nginx.exe" set NGINX_DIR=C:\nginx
    if exist "D:\nginx\nginx.exe" set NGINX_DIR=D:\nginx
)

if exist "%NGINX_DIR%\nginx.exe" (
    echo [3/3] 在 80 端口启动 Nginx...
    cd /d "%NGINX_DIR%"
    nginx.exe -s stop >nul 2>&1
    taskkill /F /IM nginx.exe >nul 2>&1
    start "" nginx.exe -c "%NGINX_CONF%"
    echo [SUCCESS] Nginx 已成功在 80 端口启动！
    echo 现在可以通过 http://10.246.97.159 直接访问！
) else (
    echo [WARN] 未在 %NGINX_DIR% 找到 nginx.exe
)

echo ===================================================
pause
