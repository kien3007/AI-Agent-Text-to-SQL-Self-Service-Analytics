# ==============================================================================
# Script khởi động cụm Airflow tinh gọn (LocalExecutor, < 1GB RAM)
# Sử dụng: .\infra\airflow\start-airflow.ps1
# ==============================================================================

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Khởi động Apache Airflow (Lightweight Orchestrator)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Tạo các thư mục cần thiết nếu chưa có
if (-not (Test-Path "dags")) { New-Item -ItemType Directory -Path "dags" | Out-Null }
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }
if (-not (Test-Path "plugins")) { New-Item -ItemType Directory -Path "plugins" | Out-Null }

Write-Host "`n1. Đang build & khởi động container Airflow..." -ForegroundColor Yellow
docker compose -f docker-compose.airflow.yml up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n Airflow đã khởi động thành công!" -ForegroundColor Green
    Write-Host " - Web UI: http://localhost:8080" -ForegroundColor White
    Write-Host " - Tài khoản: admin / admin" -ForegroundColor White
    Write-Host " - DAGs khả dụng: mssql_to_duckdb_pipeline, duckdb_maintenance" -ForegroundColor White
    Write-Host " - Metadata DB: PostgreSQL port 54323" -ForegroundColor White
    Write-Host " - Kho DuckDB: data/warehouse.duckdb" -ForegroundColor White
} else {
    Write-Host "`n❌ Có lỗi khi khởi động Docker containers. Vui lòng kiểm tra Docker Desktop." -ForegroundColor Red
}
