# ==============================================================================
# Script dừng cụm Airflow tinh gọn
# Sử dụng: .\infra\airflow\stop-airflow.ps1
# ==============================================================================

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "⏸️ Dừng Apache Airflow Orchestrator" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

docker compose -f docker-compose.airflow.yml down

Write-Host "`n Airflow đã dừng an toàn. Dữ liệu metadata & log được bảo toàn." -ForegroundColor Green
