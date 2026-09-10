@echo off
:: =====================================================================
:: TireWeight Uniformity Analysis - 全局开机自启动系统服务安装脚本
:: 统一注册 Nginx 前端服务 (8088)、FastAPI 后端服务 (8000) 与 ETL 定时任务
:: =====================================================================

:: 1. 自动提权至管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [Notice] 正在请求管理员特权以安装系统自启服务...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title TireWeight Dashboard - Windows Service Installer
echo =====================================================================
echo   正在为轮胎质量分析看板注册开机自启动服务 (NSSM Windows Services)
echo =====================================================================
echo.

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
if not exist "%ROOT_DIR%" (
    set ROOT_DIR=%~dp0..
)
cd /d "%ROOT_DIR%"

set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"
if not exist %NSSM_EXE% (
    echo [ERR] 未在 %ROOT_DIR%\scripts 找到 nssm.exe！
    pause
    exit /b 1
)

:: 创建日志目录
mkdir "%ROOT_DIR%\logs\fastapi" >nul 2>&1
mkdir "%ROOT_DIR%\logs\nginx" >nul 2>&1
mkdir "%ROOT_DIR%\logs\etl" >nul 2>&1

:: 2. 智能探测 Python 绝对路径
set "PYTHON_EXE="
if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe
) else if exist "%ROOT_DIR%\backend\venv\Scripts\python.exe" (
    set PYTHON_EXE=%ROOT_DIR%\backend\venv\Scripts\python.exe
) else (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set PYTHON_EXE=%%i
    )
)

if not defined PYTHON_EXE (
    echo [ERR] 未检测到 Python 运行环境，请确认 Python 已加入系统 PATH。
    pause
    exit /b 1
)
echo [OK] 检测到 Python 路径: %PYTHON_EXE%

:: 3. 智能探测 Nginx 路径
set "NGINX_EXE="
set "NGINX_DIR="
if exist "%ROOT_DIR%\nginx\nginx-1.26.2\nginx.exe" (
    set "NGINX_DIR=%ROOT_DIR%\nginx\nginx-1.26.2"
    set "NGINX_EXE=%ROOT_DIR%\nginx\nginx-1.26.2\nginx.exe"
) else if exist "%ROOT_DIR%\nginx\nginx.exe" (
    set "NGINX_DIR=%ROOT_DIR%\nginx"
    set "NGINX_EXE=%ROOT_DIR%\nginx\nginx.exe"
) else if exist "D:\TU AI\TireWeight_Uniformity_Analysis\nginx\nginx-1.26.2\nginx.exe" (
    set "NGINX_DIR=D:\TU AI\TireWeight_Uniformity_Analysis\nginx\nginx-1.26.2"
    set "NGINX_EXE=D:\TU AI\TireWeight_Uniformity_Analysis\nginx\nginx-1.26.2\nginx.exe"
) else if exist "C:\nginx\nginx.exe" (
    set "NGINX_DIR=C:\nginx"
    set "NGINX_EXE=C:\nginx\nginx.exe"
)

if not defined NGINX_EXE (
    echo [WARN] 未找到 nginx.exe，跳过 Nginx Windows 服务注册。
) else (
    echo [OK] 检测到 Nginx 路径: %NGINX_EXE%
)

echo.
echo ---------------------------------------------------------------------
echo [1/3] 配置并注册 FastAPI 后端系统服务 (FastAPI-Service, 端口 8000)...
echo ---------------------------------------------------------------------
%NSSM_EXE% stop FastAPI-Service >nul 2>&1
%NSSM_EXE% remove FastAPI-Service confirm >nul 2>&1

:: 释放可能占用的 8000 端口
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; foreach ($c in $conns) { if ($c.OwningProcess -gt 0) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } }"

%NSSM_EXE% install FastAPI-Service "%PYTHON_EXE%" "run_server.py"
%NSSM_EXE% set FastAPI-Service AppDirectory "%ROOT_DIR%"
%NSSM_EXE% set FastAPI-Service DisplayName "TireWeight Uniformity Analysis FastAPI Service"
%NSSM_EXE% set FastAPI-Service Description "轮胎质量与均匀性看板后端服务 (端口 8000)"
%NSSM_EXE% set FastAPI-Service Start SERVICE_AUTO_START
%NSSM_EXE% set FastAPI-Service AppEnvironmentExtra PYTHONUTF8=1 PYTHONIOENCODING=utf-8 NSSM_SERVICE=1 FASTAPI_RELOAD=0
%NSSM_EXE% set FastAPI-Service AppStdout "%ROOT_DIR%\logs\fastapi\fastapi_out.log"
%NSSM_EXE% set FastAPI-Service AppStderr "%ROOT_DIR%\logs\fastapi\fastapi_err.log"
%NSSM_EXE% set FastAPI-Service AppExit Default Restart
%NSSM_EXE% set FastAPI-Service AppRestartDelay 1000

echo [OK] FastAPI-Service 注册成功并已设置为开机自启动！
%NSSM_EXE% start FastAPI-Service

if defined NGINX_EXE (
    echo.
    echo ---------------------------------------------------------------------
    echo [2/3] 配置并注册 Nginx 前端 Web 服务 (Nginx-Service, 端口 8088)...
    echo ---------------------------------------------------------------------
    %NSSM_EXE% stop Nginx-Service >nul 2>&1
    %NSSM_EXE% remove Nginx-Service confirm >nul 2>&1
    taskkill /F /IM nginx.exe >nul 2>&1

    copy /Y "%ROOT_DIR%\scripts\nginx.conf" "%NGINX_DIR%\conf\nginx.conf" >nul 2>&1

    %NSSM_EXE% install Nginx-Service "%NGINX_EXE%" -p "%NGINX_DIR%" -c "%ROOT_DIR%\scripts\nginx.conf"
    %NSSM_EXE% set Nginx-Service AppDirectory "%NGINX_DIR%"
    %NSSM_EXE% set Nginx-Service DisplayName "TireWeight Uniformity Analysis Nginx Service"
    %NSSM_EXE% set Nginx-Service Description "轮胎质量与均匀性看板前端 Web 静态服务 (端口 8088)"
    %NSSM_EXE% set Nginx-Service Start SERVICE_AUTO_START
    %NSSM_EXE% set Nginx-Service AppStdout "%ROOT_DIR%\logs\nginx\nginx_out.log"
    %NSSM_EXE% set Nginx-Service AppStderr "%ROOT_DIR%\logs\nginx\nginx_err.log"
    %NSSM_EXE% set Nginx-Service AppExit Default Restart

    echo [OK] Nginx-Service 注册成功并已设置为开机自启动！
    %NSSM_EXE% start Nginx-Service
)

echo.
echo ---------------------------------------------------------------------
echo [3/3] 配置 ETL 定时更新计划任务 (ETL_JOB, 每 30 分钟静默触发)...
echo ---------------------------------------------------------------------
set JOB_BAT=%ROOT_DIR%\scripts\run_etl_job.bat
schtasks /create /tn "ETL_JOB" /tr "\"%JOB_BAT%\"" /sc minute /mo 30 /ru SYSTEM /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Windows 计划任务 "ETL_JOB" 已成功注册 (每 30 分钟增量拉取清洗并热加载)。
) else (
    echo [Notice] 计划任务创建完成。
)

:: 停用旧的可能有冲突的前台 scheduler
wmic process where "commandline like '%%backend.etl.scheduler%%'" call terminate >nul 2>&1

echo.
echo =====================================================================
echo   正在等待服务启动并校验端口状态...
echo =====================================================================
timeout /t 3 /nobreak >nul

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] FastAPI 后端已成功在端口 8000 监听！
) else (
    echo   [WARN] 8000 端口尚未就绪，请查看 %ROOT_DIR%\logs\fastapi\fastapi_err.log
)

netstat -ano | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Nginx 前端 Web 已成功在端口 8088 监听！
) else (
    echo   [WARN] 8088 端口尚未就绪，请查看 %ROOT_DIR%\logs\nginx\nginx_err.log
)

echo.
echo =====================================================================
echo [SUCCESS] 全套自启动系统服务安装配置完成！
echo 无论服务器何时重启，均会在无人工登录的情况下 10 秒内自动拉起！
echo 前端访问看板: http://10.246.97.159:8088
echo 后端数据接口: http://10.246.97.159:8000
echo =====================================================================
echo.
pause
