@echo off
chcp 65001 >nul
echo ===================================================
echo 正在注册开机自动静默启动计划任务...
echo ===================================================

set SCRIPT_PATH=%~dp0start_services.bat

schtasks /create /tn "TireWeight_Analysis_AutoStart" /tr "\"%SCRIPT_PATH%\"" /sc onstart /ru SYSTEM /f

if %errorlevel% equ 0 (
    echo [SUCCESS] 开机自启计划任务 "TireWeight_Analysis_AutoStart" 注册成功！
) else (
    echo [NOTICE] 注册需管理员权限，请尝试以管理员身份运行此脚本。
)
echo ===================================================
