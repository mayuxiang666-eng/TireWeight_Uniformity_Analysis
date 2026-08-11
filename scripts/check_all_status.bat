@echo off
:: TireWeight_Uniformity_Analysis Inspection & Health Check
echo ===================================================
echo TireWeight_Uniformity_Analysis 全套生产服务巡检
echo ===================================================

echo [1/3] 检查 Nginx 前端托管服务 (HTTP 80 端口):
netstat -aon | findstr ":80" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   -> Nginx Web 服务 (Port 80): [RUNNING 正常运行中]
) else (
    echo   -> Nginx Web 服务 (Port 80): [STOPPED 未检测到 80 端口监听]
)
echo.

echo [2/3] 检查 FastAPI 后端系统服务 (端口 8000):
netstat -aon | findstr ":8000" | findstr "LISTENING"
if %errorlevel% equ 0 (
    echo   -> FastAPI 后端服务 (Port 8000): [RUNNING 正常运行中]
) else (
    echo   -> FastAPI 后端服务 (Port 8000): [STOPPED 未检测到 8000 端口监听]
)
echo.

echo [3/3] 检查 DuckDB 内存数据刷新状态与 Parquet 状态:
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/etl/status' -TimeoutSec 3; Write-Host ('  -> 数据路径: ' + $r.data.data_path); Write-Host ('  -> 最后更新时间: ' + $r.data.last_modified); Write-Host ('  -> 数据文件大小: ' + $r.data.size_mb + ' MB'); Write-Host ('  -> 已加载内存数据行数: ' + $r.data.loaded_rows + ' 行'); } catch { Write-Host '  -> 无法连接 FastAPI 后端获取 ETL 状态' }"

echo ===================================================
pause
