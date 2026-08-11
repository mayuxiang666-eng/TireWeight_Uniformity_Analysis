@echo off
:: TireWeight_Uniformity_Analysis NSSM FastAPI Service Installer
echo ===================================================
echo 正在注册 FastAPI-Service Windows 系统服务...
echo ===================================================

set ROOT_DIR=D:\TU AI\TireWeight_Uniformity_Analysis
set BACKEND_DIR=%ROOT_DIR%\backend
set LOG_DIR=%ROOT_DIR%\logs\fastapi

mkdir "%LOG_DIR%" >nul 2>&1

set PYTHON_EXE=python.exe
if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe
) else if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe
) else if exist "C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe" (
    set PYTHON_EXE=C:\Users\uif77331\Desktop\111\111.venv\Scripts\python.exe
)

set NSSM_EXE=nssm.exe
if exist "%ROOT_DIR%\scripts\nssm.exe" (
    set NSSM_EXE="%ROOT_DIR%\scripts\nssm.exe"
) else if exist "D:\tools\nssm\nssm.exe" (
    set NSSM_EXE="D:\tools\nssm\nssm.exe"
) else if exist "C:\nssm\nssm.exe" (
    set NSSM_EXE="C:\nssm\nssm.exe"
)

echo 使用 Python 解析器: %PYTHON_EXE%
echo 使用 NSSM 主程序: %NSSM_EXE%

%NSSM_EXE% stop FastAPI-Service >nul 2>&1
%NSSM_EXE% remove FastAPI-Service confirm >nul 2>&1

echo 注册 FastAPI-Service...
%NSSM_EXE% install FastAPI-Service %PYTHON_EXE% "backend\run_server.py"
%NSSM_EXE% set FastAPI-Service AppDirectory "%ROOT_DIR%"
%NSSM_EXE% set FastAPI-Service DisplayName "TireWeight Uniformity Analysis FastAPI Service"
%NSSM_EXE% set FastAPI-Service Description "轮胎质量与均匀性分析看板 FastAPI 后端服务 (端口 8000)"
%NSSM_EXE% set FastAPI-Service Start SERVICE_AUTO_START
%NSSM_EXE% set FastAPI-Service AppStdout "%LOG_DIR%\fastapi_out.log"
%NSSM_EXE% set FastAPI-Service AppStderr "%LOG_DIR%\fastapi_err.log"

echo 启动 FastAPI-Service...
%NSSM_EXE% start FastAPI-Service

if %errorlevel% equ 0 (
    echo [SUCCESS] FastAPI-Service 已成功安装并设置为开机自启系统服务！
) else (
    echo [NOTICE] 注册需要管理员权限，请尝试右键以管理员身份运行此脚本。
)
echo ===================================================
pause
