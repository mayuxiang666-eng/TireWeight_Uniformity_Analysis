@echo off
:: TireWeight_Uniformity_Analysis AutoStart Task Installation Script
echo Registering Windows Startup Task...

set SCRIPT_PATH=%~dp0start_services.bat

schtasks /create /tn "TireWeight_Analysis_AutoStart" /tr "\"%SCRIPT_PATH%\"" /sc onstart /ru SYSTEM /f

if %errorlevel% equ 0 (
    echo [SUCCESS] Task "TireWeight_Analysis_AutoStart" registered successfully!
) else (
    echo [NOTICE] Admin rights required. Please right-click and 'Run as Administrator'.
)
echo ===================================================
echo.
pause
