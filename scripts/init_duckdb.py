"""
Script khởi tạo và quản lý DuckDB Data Warehouse linh hoạt cho dự án.
Cho phép khởi tạo kho dữ liệu sạch, hoặc nạp/ánh xạ dữ liệu từ file Parquet/CSV/SQLite bất kỳ.
"""

import os
import sys
import argparse
from pathlib import Path
import duckdb

# UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "warehouse.duckdb"


def init_warehouse(db_path: Path = DB_PATH, import_path: str = None, table_name: str = None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📦 Đang kết nối DuckDB tại: {db_path}")
    conn = duckdb.connect(str(db_path))

    if import_path and table_name:
        clean_path = str(import_path).replace("\\", "/")
        print(f"📥 Đang nạp dữ liệu từ '{clean_path}' vào bảng '{table_name}'...")
        if clean_path.endswith(".parquet"):
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{clean_path}');")
        elif clean_path.endswith(".csv"):
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{clean_path}');")
        else:
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{clean_path}';")
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"✅ Đã nạp thành công {count:,} bản ghi vào bảng '{table_name}'!")
    else:
        tables = conn.execute("SHOW TABLES;").fetchall()
        print(f"ℹ️ Warehouse hiện có {len(tables)} bảng: {[t[0] for t in tables]}")

    conn.close()
    print("🎉 Khởi tạo DuckDB Warehouse hoàn tất!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Khởi tạo DuckDB Warehouse linh hoạt")
    parser.add_argument("--db-path", type=str, default=str(DB_PATH), help="Đường dẫn file DuckDB")
    parser.add_argument("--import-file", type=str, default=None, help="Đường dẫn file dữ liệu (parquet, csv) cần nạp")
    parser.add_argument("--table-name", type=str, default=None, help="Tên bảng đích")
    args = parser.parse_args()

    init_warehouse(
        db_path=Path(args.db_path),
        import_path=args.import_file,
        table_name=args.table_name
    )
