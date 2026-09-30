"""
Airflow DAG: duckdb_maintenance
Bảo trì định kỳ kho dữ liệu DuckDB:
1. CHECKPOINT: Ghi toàn bộ dữ liệu từ Write-Ahead Log (WAL) vào storage chính.
2. VACUUM: Thu hồi dung lượng đĩa trống sau khi xóa/cập nhật bảng.
3. ANALYZE: Thu thập thống kê phân phối dữ liệu cho optimizer tối ưu truy vấn AI Agent.
4. CLEANUP_LOGS: Tự động dọn dẹp các bản ghi log đồng bộ cũ hơn 30 ngày trong _ingestion_sync_log.
"""

from datetime import datetime, timedelta
import os
import sys
import logging
import duckdb

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger("airflow.task")

default_args = {
    "owner": "data_engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def task_checkpoint_and_vacuum(**context):
    """Thực thi CHECKPOINT và VACUUM trên file DuckDB."""
    duckdb_path = os.getenv("DUCKDB_PATH", "/opt/airflow/data/warehouse.duckdb")
    if not os.path.exists(duckdb_path):
        logger.warning(f"File DuckDB chưa tồn tại tại {duckdb_path}. Bỏ qua bảo trì.")
        return {"status": "SKIPPED", "reason": "Database file not found"}

    initial_size = os.path.getsize(duckdb_path)
    logger.info(f"Bắt đầu CHECKPOINT và VACUUM trên {duckdb_path} (Kích thước hiện tại: {initial_size / (1024*1024):.2f} MB)...")

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute("CHECKPOINT;")
        logger.info(" Đã hoàn tất CHECKPOINT.")
        conn.execute("VACUUM;")
        logger.info(" Đã hoàn tất VACUUM.")
    finally:
        conn.close()

    new_size = os.path.getsize(duckdb_path)
    saved_bytes = initial_size - new_size
    logger.info(f" Sau bảo trì: {new_size / (1024*1024):.2f} MB (Tiết kiệm: {saved_bytes / (1024*1024):.2f} MB)")
    return {
        "initial_size_mb": round(initial_size / (1024 * 1024), 2),
        "new_size_mb": round(new_size / (1024 * 1024), 2),
        "saved_mb": round(saved_bytes / (1024 * 1024), 2)
    }


def task_analyze_statistics(**context):
    """Cập nhật thống kê phân phối dữ liệu (ANALYZE) cho công cụ tối ưu truy vấn DuckDB."""
    duckdb_path = os.getenv("DUCKDB_PATH", "/opt/airflow/data/warehouse.duckdb")
    if not os.path.exists(duckdb_path):
        return {"status": "SKIPPED"}

    logger.info(f"Đang thu thập số liệu thống kê (ANALYZE) cho DuckDB...")
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute("ANALYZE;")
        logger.info(" Thu thập thống kê ANALYZE hoàn tất!")
    finally:
        conn.close()
    return {"status": "SUCCESS"}


def task_clean_old_logs(**context):
    """Dọn dẹp các bản ghi log trong _ingestion_sync_log đã cũ hơn 30 ngày."""
    duckdb_path = os.getenv("DUCKDB_PATH", "/opt/airflow/data/warehouse.duckdb")
    if not os.path.exists(duckdb_path):
        return {"status": "SKIPPED"}

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        # Kiểm tra bảng có tồn tại không
        tbl_check = conn.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '_ingestion_sync_log'").fetchone()[0]
        if tbl_check > 0:
            del_result = conn.execute("""
                DELETE FROM _ingestion_sync_log 
                WHERE executed_at < CURRENT_TIMESTAMP - INTERVAL 30 DAY;
            """)
            logger.info(" Đã dọn dẹp các bản ghi ingestion sync log cũ hơn 30 ngày.")
        else:
            logger.info(" Bảng _ingestion_sync_log chưa có dữ liệu.")
    finally:
        conn.close()
    return {"status": "SUCCESS"}


with DAG(
    dag_id="duckdb_maintenance",
    default_args=default_args,
    description="Bảo trì định kỳ kho DuckDB: CHECKPOINT, VACUUM, ANALYZE và dọn dẹp log",
    schedule_interval="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["maintenance", "duckdb"],
) as dag:

    checkpoint_vacuum = PythonOperator(
        task_id="checkpoint_and_vacuum",
        python_callable=task_checkpoint_and_vacuum,
        provide_context=True,
    )

    analyze_stats = PythonOperator(
        task_id="analyze_statistics",
        python_callable=task_analyze_statistics,
        provide_context=True,
    )

    clean_logs = PythonOperator(
        task_id="clean_old_logs",
        python_callable=task_clean_old_logs,
        provide_context=True,
    )

    checkpoint_vacuum >> analyze_stats >> clean_logs
