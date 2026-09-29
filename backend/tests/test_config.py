"""
Unit test kiểm tra hệ thống quản lý biến môi trường tập trung (Config & .env).
"""

import os
import unittest
from pathlib import Path

# Đảm bảo import backend
import sys
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings, AppSettings


class TestConfigManagement(unittest.TestCase):
    """Kiểm tra việc nạp và chuẩn hóa cấu hình từ biến môi trường và file .env."""

    def test_default_settings_loaded(self):
        """Xác nhận các giá trị mặc định thiết yếu được khởi tạo chính xác."""
        self.assertEqual(settings.WAREHOUSE_BACKEND, "duckdb")
        self.assertIn("warehouse.duckdb", settings.DUCKDB_PATH)
        self.assertEqual(settings.APP_PORT, 8000)
        self.assertIn("*", settings.cors_origins_list)

    def test_hitl_threshold_defaults(self):
        """Xác nhận các ngưỡng an toàn Human-In-The-Loop đã được cấu hình."""
        self.assertGreaterEqual(settings.HITL_SCAN_TABLETS_THRESHOLD, 10)
        self.assertGreaterEqual(settings.HITL_ROW_COUNT_THRESHOLD, 100000)

    def test_custom_env_override(self):
        """Kiểm tra khả năng ghi đè giá trị qua tham số khởi tạo."""
        custom_cfg = AppSettings(
            WAREHOUSE_BACKEND="duckdb",
            DUCKDB_PATH="./custom/path.duckdb",
            APP_PORT=8080,
            CORS_ORIGINS="http://localhost:3000, https://app.example.com"
        )
        self.assertEqual(custom_cfg.WAREHOUSE_BACKEND, "duckdb")
        self.assertEqual(custom_cfg.DUCKDB_PATH, "./custom/path.duckdb")
        self.assertEqual(custom_cfg.APP_PORT, 8080)
        self.assertEqual(len(custom_cfg.cors_origins_list), 2)
        self.assertIn("http://localhost:3000", custom_cfg.cors_origins_list)


if __name__ == "__main__":
    unittest.main()
