@echo off
echo =======================================================
echo CGRS Database Daily Parquet Exporter
echo =======================================================

pushd "%~dp0.." 2>nul

python "%~dp0..\backend\etl\export_cgrs_parquet.py" --days 3

if %ERRORLEVEL% EQU 0 (
    echo CGRS Data Export Success!
) else (
    echo CGRS Data Export Failed! Please check logs/cgrs_export.log
)

popd 2>nul
pause
