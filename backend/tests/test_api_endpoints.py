"""
Unit and Integration Tests for FastAPI Web Endpoints (REST API, SSE Streaming, HITL, Multi-Database Connect).
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.agent.state import AgentState
from app.api.routers.chat import SESSION_STORE
from app.core.auth import create_access_token
from app.core.domain_manager import DomainManager
from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile


class TestApiEndpoints(unittest.TestCase):
    """Kiểm thử toàn bộ các endpoints REST API của FastAPI Backend."""

    @classmethod
    def setUpClass(cls):
        from app.db.warehouse_client import get_warehouse_client
        client = get_warehouse_client()
        client.execute_query("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id BIGINT PRIMARY KEY,
                total_amount DOUBLE
            );
        """)
        client.execute_query("DELETE FROM orders;")
        client.execute_query("INSERT INTO orders (order_id, total_amount) VALUES (101, 1000000.0), (102, 2000000.0);")

        # Đảm bảo có dynamic domain sẵn sàng phục vụ test
        dm = DomainManager()
        dm.register_domain(
            DomainConfig(
                domain_id="ecommerce",
                display_name="Thương Mại Điện Tử",
                description="Dữ liệu bán hàng & đơn hàng",
                tables={
                    "orders": TableProfile(
                        table_name="orders",
                        columns={
                            "order_id": ColumnProfile(name="order_id", data_type="BIGINT", is_primary_key=True),
                            "total_amount": ColumnProfile(name="total_amount", data_type="DOUBLE")
                        }
                    )
                }
            )
        )

    def setUp(self):
        self.client = TestClient(app)
        token = create_access_token({
            "sub": "admin",
            "user_id": "admin-01",
            "role": "admin",
            "display_name": "Administrator",
            "username": "admin"
        })
        self.client.headers["Authorization"] = f"Bearer {token}"

    def test_root_endpoint(self):
        """Kiểm tra endpoint gốc GET / trả về thông tin OpenAPI và phiên bản."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["version"], "2.0.0")

    def test_health_check_endpoint(self):
        """Kiểm tra endpoint GET /api/health trả về danh sách domain hoạt động."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ["healthy", "degraded"])
        self.assertGreaterEqual(data["total_domains"], 1)
        self.assertTrue(len(data["loaded_domains"]) >= 1)

    def test_list_domains_endpoint(self):
        """Kiểm tra endpoint GET /api/domains liệt kê chi tiết các domain."""
        response = self.client.get("/api/domains")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("domains", data)
        self.assertGreaterEqual(len(data["domains"]), 1)

    def test_get_domain_details_endpoint(self):
        """Kiểm tra endpoint GET /api/domains/{domain_id} lấy metadata bảng và metrics."""
        dm = DomainManager()
        active_id = dm.get_active_domain().domain_id
        response = self.client.get(f"/api/domains/{active_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["domain_id"], active_id)

    def test_connect_database_endpoint(self):
        """Kiểm tra endpoint POST /api/domains/connect gắn CSDL động (SQLite in-memory)."""
        payload = {
            "connection_url": "sqlite:///:memory:",
            "domain_id": "sqlite_dynamic_db",
            "db_name": "sqlite_dynamic_db",
            "display_name": "SQLite Dynamic In-Memory",
            "save_yaml": False
        }
        response = self.client.post("/api/domains/connect", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "connected")
        self.assertEqual(data["domain_id"], "sqlite_dynamic_db")

    def test_chat_sync_normal_query(self):
        """Kiểm tra endpoint POST /api/chat thực thi câu hỏi tự nhiên và trả về kết quả."""
        payload = {
            "query": "Thống kê tổng doanh thu đơn hàng",
            "domain_id": "ecommerce"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["session_id"])
        self.assertIsNotNone(data["sql_query"])
        self.assertIsNotNone(data["final_response"])
        self.assertFalse(data["clarification_needed"])

    def test_chat_sync_vague_query_clarification(self):
        """Kiểm tra endpoint POST /api/chat phát hiện câu hỏi mơ hồ và kích hoạt hỏi lại."""
        payload = {
            "query": "thống kê",
            "domain_id": "ecommerce"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIsNotNone(data["clarification_question"])

    def test_chat_hitl_approval_flow(self):
        """Kiểm tra luồng phê duyệt Human-In-The-Loop tại POST /api/chat/hitl."""
        test_session_id = "test_hitl_session_123"
        paused_state = AgentState(
            session_id=test_session_id,
            user_query="Xóa toàn bộ bảng dữ liệu",
            sql_query="SELECT * FROM orders LIMIT 1000000",
            requires_hitl=True,
            hitl_approved=None
        )
        SESSION_STORE[test_session_id] = paused_state

        payload = {
            "session_id": test_session_id,
            "approved": True
        }
        response = self.client.post("/api/chat/hitl", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], test_session_id)
        self.assertTrue(data["hitl_approved"])
        self.assertIsNotNone(data["final_response"])

        self.assertNotIn(test_session_id, SESSION_STORE)


if __name__ == "__main__":
    unittest.main()
