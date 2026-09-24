@echo off
:: TireWeight_Uniformity_Analysis Full 31-Day Fetch Script
echo ===================================================
echo Starting Full 31-Day Data Fetch from Amazon Redshift...
echo ===================================================

cd /d "%~dp0.."

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Find Python absolute path (Intelligent multi-tier fallback)
set "PYTHON_EXE="
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
) else if exist "d:\Ava\untitled1\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=d:\Ava\untitled1\.venv\Scripts\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python313\python.exe"
) else if exist "C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\uif45510\AppData\Local\Programs\Python\Python311\python.exe"
) else if exist "%~dp0..\backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\backend\venv\Scripts\python.exe"
) else if exist "%~dp0..\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\venv\Scripts\python.exe"
) else if exist "C:\Program Files\Python313\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
) else if exist "C:\Program Files\Python311\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
) else if exist "C:\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python313\python.exe"
) else (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE set "PYTHON_EXE=python.exe"

mkdir logs\etl >nul 2>&1

echo. >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log
echo [%date% %time%] Starting FULL 31-Day ETL Pipeline... >> logs\etl\etl.log

"%PYTHON_EXE%" -m backend.etl.run_pipeline --full-fetch

echo [%date% %time%] Full ETL finished with exit code: %errorlevel% >> logs\etl\etl.log
echo =================================================== >> logs\etl\etl.log

echo.
echo ===================================================
echo [SUCCESS] Full 31-Day Data Fetch & Clean Completed!
echo ===================================================
pause
