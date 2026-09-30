"""
Unit & Integration Tests for Microsoft SQL Server (MSSQL) Connection & Multi-Schema Domains.
Kiểm tra:
1. Parser chuyển đổi JDBC URL sang SQLAlchemy mssql+pymssql:// URL.
2. Tự động khám phá đa schema (Multi-schema Introspection).
3. Đăng ký DomainConfig cho các schema nghiệp vụ trong cơ sở dữ liệu đa schema.
4. Cú pháp T-SQL thích ứng (SELECT TOP N thay vì LIMIT).
"""

import os
import sys
import socket
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.warehouse_client import parse_jdbc_url, _ROUTER, get_warehouse_client
from app.core.domain_manager import DomainManager
from app.agent.nodes.sql_generator import SQLGeneratorNode


def _is_host_reachable(host: str, port: int = 1433, timeout: float = 1.5) -> bool:
    """Kiểm tra máy chủ CSDL có thể kết nối được qua TCP hay không."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


# Đọc URL từ biến môi trường (bảo mật), không lưu cứng URL trong code
DEFAULT_MSSQL_URL = os.getenv("MSSQL_DATABASE_URL", os.getenv("EXTERNAL_DATABASE_URL", ""))


class TestMSSQLIntegration(unittest.TestCase):

    jdbc_url = DEFAULT_MSSQL_URL
    server_online = False
    dm = None

    @classmethod
    def setUpClass(cls):
        cls.dm = DomainManager()
        if not cls.jdbc_url:
            cls.server_online = False
            return

        # Chỉ thử kết nối nếu chuỗi kết nối đã được cấu hình kèm tài khoản mật khẩu
        has_credentials = any(k in cls.jdbc_url.lower() for k in ["user=", "username=", "user id="]) or "@" in cls.jdbc_url
        if not has_credentials:
            cls.server_online = False
            return

        # Trích xuất host và port từ URL để kiểm tra TCP socket
        import re
        m = re.search(r"://([^:/;]+)(?::(\d+))?", cls.jdbc_url)
        host = m.group(1) if m else None
        port = int(m.group(2)) if m and m.group(2) else 1433
        if not host:
            cls.server_online = False
            return

        cls.server_online = _is_host_reachable(host, port, timeout=1.5)
        if cls.server_online:
            try:
                cls.dm.connect_and_register_database(
                    connection_url_or_client=cls.jdbc_url,
                    register_all_schemas=True
                )
            except Exception as e:
                cls.server_online = False
                print(f"[WARN] Không thể kết nối MSSQL: {e}")

    def test_parse_jdbc_url(self):
        """Kiểm tra parser chuyển đổi JDBC URL sang SQLAlchemy connection string."""
        sample_jdbc = "jdbc:sqlserver://sqlserver.example.com:1433;databaseName=mock_db;user=test_user;password=test_pass;encrypt=true"
        sqlalchemy_url = parse_jdbc_url(sample_jdbc)
        self.assertTrue(sqlalchemy_url.startswith("mssql+pymssql://"))
        self.assertIn("sqlserver.example.com:1433", sqlalchemy_url)
        self.assertIn("mock_db", sqlalchemy_url)
        self.assertIn("test_user", sqlalchemy_url)

    def test_sql_generator_tsql_adaptation(self):
        """Kiểm tra cơ chế self-healing tự động đổi LIMIT sang SELECT TOP N cho MSSQL."""
        node = SQLGeneratorNode()
        # Test trường hợp SELECT bình thường có LIMIT
        sql_with_limit = "SELECT order_sn, total_order_value FROM vietnam_ecommerce.shopee_orders LIMIT 10;"
        adapted = node._adapt_to_mssql(sql_with_limit)
        self.assertIn("TOP (10)", adapted)
        self.assertNotIn("LIMIT", adapted)

        # Test trường hợp SELECT DISTINCT có LIMIT
        sql_distinct = "SELECT DISTINCT order_status FROM vietnam_ecommerce.shopee_orders LIMIT 5;"
        adapted_distinct = node._adapt_to_mssql(sql_distinct)
        self.assertIn("TOP (5)", adapted_distinct)
        self.assertNotIn("LIMIT", adapted_distinct)

    def test_connect_and_register_all_schemas(self):
        """Kiểm tra các schema nghiệp vụ đã được đăng ký thành domain riêng khi server online."""
        if not self.server_online:
            self.skipTest("Bỏ qua test live do máy chủ MSSQL từ xa chưa được cấu hình hoặc không online.")

        all_domains = self.dm.list_domains()
        self.assertIn("vietnam_ecommerce", all_domains)
        self.assertIn("fmcg_sales", all_domains)
        self.assertIn("retails", all_domains)

        vn_ecom = self.dm.get_domain("vietnam_ecommerce")
        self.assertIsNotNone(vn_ecom)
        self.assertIn("vietnam_ecommerce.shopee_orders", vn_ecom.tables)
        self.assertIn("vietnam_ecommerce.tiktok_orders", vn_ecom.tables)

    def test_domain_routing(self):
        """Kiểm tra DomainManager tự động nhận diện domain chính xác từ câu hỏi tiếng Việt."""
        if not self.server_online:
            self.skipTest("Bỏ qua test live routing do máy chủ MSSQL không online.")

        routed_1 = self.dm.detect_domain("Thống kê số lượng đơn hàng trên Shopee theo ngày")
        self.assertEqual(routed_1, "vietnam_ecommerce")

    def test_live_query_execution(self):
        """Kiểm tra thực thi truy vấn thật tới máy chủ MSSQL từ xa qua SQLAlchemyClient."""
        if not self.server_online:
            self.skipTest("Bỏ qua test live query do máy chủ MSSQL không online.")

        client = get_warehouse_client(connection_url=self.jdbc_url)
        cols, rows = client.execute_query(
            "SELECT TOP (2) order_sn, order_status, total_order_value, shop_name FROM vietnam_ecommerce.shopee_orders"
        )
        self.assertEqual(len(cols), 4)
        self.assertIn("order_sn", cols)
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
