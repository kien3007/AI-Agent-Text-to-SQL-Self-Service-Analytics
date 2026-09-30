"""
CLI Script nạp dữ liệu từ CSDL nguồn (SQL Server / PostgreSQL / MySQL) vào DuckDB.
Được gọi từ Airflow DAG (BashOperator/PythonOperator) hoặc cron job.

Cách dùng:
  python backend/scripts/ingest_to_duckdb.py --source "mssql+pymssql://..." --domain ecommerce --mode full_refresh
  python backend/scripts/ingest_to_duckdb.py --source "postgresql://..." --tables orders,customers --mode incremental
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.ingestion_service import DataIngestionService


def main():
    parser = argparse.ArgumentParser(description="Đồng bộ CSDL nguồn vào DuckDB")
    parser.add_argument("--source", type=str, default=os.getenv("EXTERNAL_DATABASE_URL", ""),
                        help="Connection URL của CSDL nguồn (MSSQL, PostgreSQL, MySQL...)")
    parser.add_argument("--schema", type=str, default=None,
                        help="Schema nguồn (vd: dbo, public, vietnam_ecommerce)")
    parser.add_argument("--domain", type=str, default="default",
                        help="Mã domain mục tiêu")
    parser.add_argument("--tables", type=str, default=None,
                        help="Danh sách bảng cần sync, phân tách bằng dấu phẩy (vd: orders,customers)")
    parser.add_argument("--mode", type=str, choices=["full_refresh", "incremental"], default="full_refresh",
                        help="Chế độ đồng bộ: full_refresh hoặc incremental")
    parser.add_argument("--duckdb-path", type=str, default=None,
                        help="Đường dẫn file DuckDB đích (mặc định data/warehouse.duckdb)")

    args = parser.parse_args()

    if not args.source:
        print("❌ Lỗi: Cần cung cấp --source connection URL hoặc biến môi trường EXTERNAL_DATABASE_URL.")
        sys.exit(1)

    tables_list = [t.strip() for t in args.tables.split(",")] if args.tables else None

    print("================================================================")
    print("🚀 BẮT ĐẦU ĐỒNG BỘ DỮ LIỆU VÀO DUCKDB (DATA INGESTION)")
    print(f" - Nguồn: {args.source.split('@')[-1] if '@' in args.source else args.source[:30]}...")
    print(f" - Domain: {args.domain}")
    print(f" - Chế độ: {args.mode}")
    print(f" - Bảng chọn: {tables_list or 'Toàn bộ schema'}")
    print("================================================================")

    service = DataIngestionService(target_duckdb_path=args.duckdb_path)
    result = service.sync_database(
        source_connection_url=args.source,
        source_schema=args.schema,
        selected_tables=tables_list,
        sync_mode=args.mode,
        domain_id=args.domain
    )

    print("\n✅ KẾT QUẢ ĐỒNG BỘ:")
    print(f" - Trạng thái: {result['status']}")
    print(f" - Số bảng đã nạp: {result['tables_synced_count']}/{result['total_tables']}")
    print(f" - Tổng số dòng nạp: {result['total_rows_ingested']}")
    print(f" - Thời gian thực thi: {result['duration_sec']}s")

    if result["failed_tables"]:
        print(f" ⚠️ Các bảng lỗi: {result['failed_tables']}")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
