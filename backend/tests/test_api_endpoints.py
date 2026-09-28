"""
Unit and Integration Tests for FastAPI Web Endpoints (REST API, SSE Streaming, HITL).
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


class TestApiEndpoints(unittest.TestCase):
    """Kiểm thử toàn bộ các endpoints REST API của FastAPI Backend."""

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
        self.assertIn("real_estate", data["loaded_domains"])
        self.assertGreaterEqual(data["total_domains"], 1)

    def test_list_domains_endpoint(self):
        """Kiểm tra endpoint GET /api/domains liệt kê chi tiết các domain."""
        response = self.client.get("/api/domains")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("domains", data)
        domain_ids = [d["domain_id"] for d in data["domains"]]
        self.assertIn("real_estate", domain_ids)

    def test_get_domain_details_endpoint(self):
        """Kiểm tra endpoint GET /api/domains/{domain_id} lấy metadata bảng và metrics."""
        response = self.client.get("/api/domains/real_estate")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["domain_id"], "real_estate")
        self.assertGreater(len(data["tables"]), 0)

    def test_chat_sync_normal_query(self):
        """Kiểm tra endpoint POST /api/chat thực thi câu hỏi tự nhiên và trả về kết quả."""
        payload = {
            "query": "Thống kê giá nhà theo quận tại Cầu Giấy",
            "domain_id": "real_estate"
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
            "domain_id": "real_estate"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["clarification_needed"])
        self.assertIsNotNone(data["clarification_question"])

    def test_chat_hitl_approval_flow(self):
        """Kiểm tra luồng phê duyệt Human-In-The-Loop tại POST /api/chat/hitl."""
        # Giả lập một phiên đang chờ duyệt HITL trong SESSION_STORE
        test_session_id = "test_hitl_session_123"
        paused_state = AgentState(
            session_id=test_session_id,
            user_query="Xóa toàn bộ bảng dữ liệu",
            sql_query="SELECT * FROM real_estate_listings LIMIT 1000000",
            requires_hitl=True,
            hitl_approved=None
        )
        SESSION_STORE[test_session_id] = paused_state

        # Gửi quyết định phê duyệt
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

        # Xác nhận session đã được dọn khỏi SESSION_STORE
        self.assertNotIn(test_session_id, SESSION_STORE)


if __name__ == "__main__":
    unittest.main()
