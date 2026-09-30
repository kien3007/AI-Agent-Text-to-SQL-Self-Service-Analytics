"""
Unit tests for Data Ingestion Service.
Kiểm thử toàn diện chức năng nạp dữ liệu từ CSDL nguồn vào DuckDB (Full-refresh & Incremental).
"""

import os
import sys
import tempfile
import sqlite3
import unittest
from pathlib import Path
import duckdb

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.ingestion_service import DataIngestionService


class TestDataIngestionService(unittest.TestCase):
    """Kiểm thử tính năng trích xuất và đồng bộ dữ liệu vào DuckDB."""

    def setUp(self):
        # Tạo file SQLite tạm đóng vai trò CSDL nguồn (Source DB)
        self.source_db_fd, self.source_db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(self.source_db_fd)
        self.source_url = f"sqlite:///{self.source_db_path.replace(os.sep, '/')}"

        # Tạo đường dẫn file DuckDB tạm đóng vai trò Target Warehouse (chưa tạo file rỗng)
        import uuid
        self.target_db_path = os.path.join(tempfile.gettempdir(), f"test_duck_{uuid.uuid4().hex[:8]}.duckdb")

        # Tạo dữ liệu giả lập trong CSDL nguồn
        conn = sqlite3.connect(self.source_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                created_at TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                total_amount REAL,
                status TEXT,
                created_at TIMESTAMP
            );
        """)
        # Chèn dữ liệu mẫu
        cursor.executemany("""
            INSERT INTO customers VALUES (?, ?, ?, ?)
        """, [
            (1, "Nguyen Van A", "Hanoi", "2026-01-01 10:00:00"),
            (2, "Tran Thi B", "Da Nang", "2026-01-02 11:00:00"),
            (3, "Le Van C", "HCM", "2026-01-03 12:00:00"),
        ])
        cursor.executemany("""
            INSERT INTO orders VALUES (?, ?, ?, ?, ?)
        """, [
            (101, 1, 500000.0, "COMPLETED", "2026-01-05 09:00:00"),
            (102, 2, 750000.0, "COMPLETED", "2026-01-06 14:00:00"),
        ])
        conn.commit()
        conn.close()

        self.service = DataIngestionService(target_duckdb_path=self.target_db_path)

    def tearDown(self):
        # Dọn dẹp các file DB tạm
        for p in [self.source_db_path, self.target_db_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def test_sync_table_full_refresh(self):
        """Kiểm thử đồng bộ 1 bảng chế độ full_refresh."""
        result = self.service.sync_table(
            source_connection_url=self.source_url,
            table_name="customers",
            sync_mode="full_refresh",
            domain_id="ecommerce"
        )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["rows_ingested"], 3)
        self.assertEqual(result["table_name"], "customers")

        # Xác thực dữ liệu đã nằm trong DuckDB
        duck_conn = duckdb.connect(self.target_db_path, read_only=True)
        res = duck_conn.execute("SELECT COUNT(*) FROM customers").fetchone()
        self.assertEqual(res[0], 3)

        sample = duck_conn.execute("SELECT name, city FROM customers WHERE id = 1").fetchone()
        self.assertEqual(sample, ("Nguyen Van A", "Hanoi"))
        duck_conn.close()

    def test_sync_table_incremental(self):
        """Kiểm thử đồng bộ tăng dần incremental dựa trên watermark column."""
        # Lần 1: Đồng bộ toàn bộ
        res1 = self.service.sync_table(
            source_connection_url=self.source_url,
            table_name="customers",
            sync_mode="full_refresh",
            watermark_column="created_at"
        )
        self.assertEqual(res1["rows_ingested"], 3)

        # Chèn thêm 2 bản ghi mới vào nguồn
        conn = sqlite3.connect(self.source_db_path)
        conn.cursor().executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", [
            (4, "Pham Van D", "Can Tho", "2026-01-10 10:00:00"),
            (5, "Hoang Thi E", "Hai Phong", "2026-01-11 11:00:00"),
        ])
        conn.commit()
        conn.close()

        # Lần 2: Đồng bộ incremental
        res2 = self.service.sync_table(
            source_connection_url=self.source_url,
            table_name="customers",
            sync_mode="incremental",
            watermark_column="created_at"
        )
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(res2["rows_ingested"], 2)

        # Tổng số bản ghi trong DuckDB phải là 5
        duck_conn = duckdb.connect(self.target_db_path, read_only=True)
        total = duck_conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        self.assertEqual(total, 5)
        duck_conn.close()

    def test_sync_database_all_tables(self):
        """Kiểm thử đồng bộ hàng loạt bảng của CSDL nguồn."""
        summary = self.service.sync_database(
            source_connection_url=self.source_url,
            domain_id="ecommerce",
            sync_mode="full_refresh"
        )

        self.assertEqual(summary["status"], "SUCCESS")
        self.assertEqual(summary["tables_synced_count"], 2)
        self.assertEqual(summary["total_rows_ingested"], 5)  # 3 customers + 2 orders
        self.assertEqual(len(summary["failed_tables"]), 0)

    def test_sync_history_logging(self):
        """Kiểm thử ghi nhận lịch sử đồng bộ vào _ingestion_sync_log."""
        self.service.sync_table(
            source_connection_url=self.source_url,
            table_name="customers",
            sync_mode="full_refresh",
            domain_id="ecommerce"
        )

        history = self.service.get_sync_history(limit=10)
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertEqual(latest["table_name"], "customers")
        self.assertEqual(latest["status"], "SUCCESS")
        self.assertEqual(latest["rows_ingested"], 3)
        self.assertEqual(latest["sync_mode"], "full_refresh")


if __name__ == "__main__":
    unittest.main()
