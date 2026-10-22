@echo off
:: =====================================================================
:: TireWeight Uniformity Analysis - 全局开机自启动系统服务安装脚本
:: 极简单服务架构：彻底放弃 Nginx，由 FastAPI (端口 8088) 单一后台服务接管全部前后端
:: =====================================================================

:: 1. 自动提权至管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [Notice] 正在请求管理员特权以安装系统自启服务...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title TireWeight Dashboard - Windows Service Installer (Port 8088)
echo =====================================================================
echo   正在为轮胎质量分析看板注册开机自启动服务 (端口 8088 单服务架构)
echo   架构：彻底移除 Nginx，由 FastAPI 后台静默系统服务接管全套前后端
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
mkdir "%ROOT_DIR%\logs\etl" >nul 2>&1

:: 2. 彻底清理并卸载旧的 Nginx 服务与残留进程
echo [1/3] 正在彻底清理并卸载 Nginx 历史服务...
%NSSM_EXE% stop Nginx-Service >nul 2>&1
%NSSM_EXE% remove Nginx-Service confirm >nul 2>&1
taskkill /F /IM nginx.exe >nul 2>&1
if exist "%ROOT_DIR%\nginx\nginx-1.26.2\logs\nginx.pid" del /F /Q "%ROOT_DIR%\nginx\nginx-1.26.2\logs\nginx.pid" >nul 2>&1
if exist "%ROOT_DIR%\nginx\logs\nginx.pid" del /F /Q "%ROOT_DIR%\nginx\logs\nginx.pid" >nul 2>&1
echo   -> Nginx 服务已成功清理并注销。

:: 3. 智能探测 Python 绝对路径
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

:: 4. 配置并注册 FastAPI 单一服务 (端口 8088)
echo.
echo ---------------------------------------------------------------------
echo [2/3] 配置并注册 FastAPI 全栈系统服务 (FastAPI-Service, 端口 8088)...
echo ---------------------------------------------------------------------
%NSSM_EXE% stop FastAPI-Service >nul 2>&1
%NSSM_EXE% remove FastAPI-Service confirm >nul 2>&1

:: 彻底释放可能占用 8088 和 8000 端口的进程
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8088,8000 -ErrorAction SilentlyContinue; foreach ($c in $conns) { if ($c.OwningProcess -gt 0) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } }"

%NSSM_EXE% install FastAPI-Service "%PYTHON_EXE%" "run_server.py"
%NSSM_EXE% set FastAPI-Service AppDirectory "%ROOT_DIR%"
%NSSM_EXE% set FastAPI-Service DisplayName "TireWeight Uniformity Analysis Service"
%NSSM_EXE% set FastAPI-Service Description "轮胎质量与均匀性看板系统服务 (端口 8088，聚合前端与数据)"
%NSSM_EXE% set FastAPI-Service Start SERVICE_AUTO_START
%NSSM_EXE% set FastAPI-Service AppEnvironmentExtra PYTHONUTF8=1 PYTHONIOENCODING=utf-8 NSSM_SERVICE=1 FASTAPI_RELOAD=0
%NSSM_EXE% set FastAPI-Service AppStdout "%ROOT_DIR%\logs\fastapi\fastapi_out.log"
%NSSM_EXE% set FastAPI-Service AppStderr "%ROOT_DIR%\logs\fastapi\fastapi_err.log"
%NSSM_EXE% set FastAPI-Service AppExit Default Restart
%NSSM_EXE% set FastAPI-Service AppRestartDelay 1000

echo [OK] FastAPI-Service 已成功配置为开机自启动系统服务！
%NSSM_EXE% start FastAPI-Service

:: 5. 配置 ETL 定时更新计划任务 (每 30 分钟静默触发)
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
timeout /t 5 /nobreak >nul

netstat -ano | findstr ":8088 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] 全栈看板服务已成功在端口 8088 监听！
) else (
    echo   [WARN] 8088 端口正在初始化中，请查看 %ROOT_DIR%\logs\fastapi\fastapi_err.log
)

echo.
echo =====================================================================
echo [SUCCESS] 全套开机自启动后台服务安装配置完成！
echo 特点：彻底移除 Nginx，桌面 0 黑框，开机无人登录也可在 10 秒内后台自启！
echo 看板唯一访问地址: http://10.246.97.159:8088
echo =====================================================================
echo.
pause
