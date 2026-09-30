"""
Unit and Integration Tests for Agent State Machine, Dual-Model LLM Orchestrator,
3-Tier Memory, Self-Correction Loop, HITL Gate, and Response Formatter.
"""

import os
import sys
import unittest
from typing import Dict, Any, List

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class MockEmbedding:
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Any) -> Any:
        return [[0.0] * 1024 for _ in input]


from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.memory.three_tier_memory import ThreeTierMemory, ShortTermMemory, TemporaryMemory, LongTermMemory
from app.agent.nodes.intent_node import IntentClarifierNode
from app.agent.nodes.schema_linking_node import SchemaLinkingNode
from app.agent.nodes.sql_generator import SQLGeneratorNode
from app.agent.nodes.validator_node import ValidatorNode
from app.agent.nodes.hitl_node import HITLNode
from app.agent.nodes.executor_node import ExecutorNode
from app.agent.nodes.response_formatter import ResponseFormatterNode
from app.agent.graph import AgentOrchestrator
from app.agent.nodes.plan_validator import ValidationResult
from app.db.warehouse_client import get_warehouse_client
from app.core.domain_manager import DomainManager
from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile


class TestAgentStateMachine(unittest.TestCase):
    """Bộ kiểm thử cỗ máy trạng thái đa tác tử."""

    @classmethod
    def setUpClass(cls):
        cls.client = get_warehouse_client()
        cls.client.execute_query("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id BIGINT PRIMARY KEY,
                customer_name VARCHAR,
                total_amount DOUBLE,
                area DOUBLE,
                price DOUBLE,
                order_status VARCHAR,
                created_at TIMESTAMP
            );
        """)
        cls.client.execute_query("DELETE FROM orders;")
        cls.client.execute_query("""
            INSERT INTO orders (order_id, customer_name, total_amount, area, price, order_status, created_at) VALUES 
            (1, 'Nguyen Van A', 1500000.0, 50.0, 1500000000.0, 'COMPLETED', '2026-03-01 10:00:00'),
            (2, 'Tran Thi B', 2500000.0, 75.0, 2500000000.0, 'COMPLETED', '2026-03-02 11:00:00');
        """)

        cls.dm = DomainManager()
        cls.test_domain = DomainConfig(
            domain_id="ecommerce",
            display_name="E-Commerce",
            description="Dữ liệu bán lẻ & đơn hàng",
            domain_keywords=["đơn hàng", "sản phẩm", "doanh thu", "khách hàng", "nhà", "giá"],
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    columns={
                        "order_id": ColumnProfile(name="order_id", data_type="BIGINT", is_primary_key=True),
                        "customer_name": ColumnProfile(name="customer_name", data_type="VARCHAR"),
                        "total_amount": ColumnProfile(name="total_amount", data_type="DOUBLE"),
                        "area": ColumnProfile(name="area", data_type="DOUBLE"),
                        "price": ColumnProfile(name="price", data_type="DOUBLE"),
                        "order_status": ColumnProfile(name="order_status", data_type="VARCHAR"),
                        "created_at": ColumnProfile(name="created_at", data_type="TIMESTAMP")
                    }
                )
            }
        )
        cls.dm.register_domain(cls.test_domain)

    def setUp(self):
        self.mock_emb = MockEmbedding()
        self.llm = DualModelLLM()

    def test_agent_state_basics(self):
        """Kiểm tra khởi tạo và ghi log trạng thái AgentState."""
        state = AgentState(user_query="Tìm chung cư Cầu Giấy dưới 3 tỷ")
        self.assertIsNotNone(state.session_id)
        self.assertEqual(state.user_query, "Tìm chung cư Cầu Giấy dưới 3 tỷ")
        self.assertEqual(state.retry_count, 0)
        self.assertFalse(state.clarification_needed)

        state.log_step("node_1")
        state.log_step("node_2")
        self.assertEqual(state.steps_executed, ["node_1", "node_2"])

        state_dict = state.to_dict()
        self.assertEqual(state_dict["user_query"], state.user_query)
        self.assertEqual(state_dict["steps_executed"], ["node_1", "node_2"])

    def test_three_tier_memory_operations(self):
        """Kiểm tra 3 tầng bộ nhớ: Short-term, Temporary (Bellman) và Long-term."""
        memory = ThreeTierMemory(embedding_function=self.mock_emb)

        # 1. Short-Term Memory
        err1 = memory.short_term.record_error(
            raw_error="Unknown column 'dien_tich' in 'field list'",
            vn_advice="Đổi 'dien_tich' thành 'area'",
            sql="SELECT dien_tich FROM orders"
        )
        self.assertEqual(err1.category, "GRAMMAR")
        self.assertEqual(len(memory.short_term.grammar_errors), 1)

        feedback_prompt = memory.short_term.get_feedback_prompt()
        self.assertIn("SHORT-TERM MEMORY FEEDBACK", feedback_prompt)
        self.assertIn("dien_tich", feedback_prompt)

        # 2. Temporary Memory & Bellman Scoring
        memory.temporary.add_step("sql_gen", {"error": "syntax"}, reward=-0.5)
        self.assertAlmostEqual(memory.temporary.get_latest_value(), -0.5)

        memory.temporary.add_step("sql_val", {"status": "ok"}, reward=1.0)
        self.assertAlmostEqual(memory.temporary.get_latest_value(), 1.0)
        self.assertFalse(memory.temporary.is_stuck_in_loop())

        # 3. Long-Term Memory
        initial_good = len(memory.long_term.good_plans)
        memory.long_term.save_plan("Query test", "ecommerce", "SELECT 1;", is_successful=True)
        self.assertEqual(len(memory.long_term.good_plans), initial_good + 1)

    def test_intent_clarifier_normal_query(self):
        """Kiểm tra câu hỏi rõ ràng được chuẩn hóa và không kích hoạt hỏi lại."""
        node = IntentClarifierNode(llm=self.llm)
        state = AgentState(user_query="Báo cáo doanh thu đơn hàng tháng này")

        res_state = node(state)
        self.assertFalse(res_state.clarification_needed)
        self.assertIsNone(res_state.clarification_question)
        self.assertIn("intent_clarifier", res_state.steps_executed)

    def test_intent_clarifier_vague_query_triggers_loop(self):
        """Kiểm tra câu hỏi mơ hồ kích hoạt hỏi lại (Clarification Loop)."""
        node = IntentClarifierNode(llm=self.llm)
        state = AgentState(user_query="xem giá")

        res_state = node(state)
        self.assertTrue(res_state.clarification_needed)
        self.assertIsNotNone(res_state.clarification_question)
        self.assertIn("anh/chị", res_state.clarification_question.lower())

    def test_orchestrator_e2e(self):
        """Kiểm tra toàn bộ luồng E2E câu hỏi phân tích thông thường."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        query = "Thống kê doanh thu đơn hàng trong tháng này"
        final_state = orchestrator.invoke(query)

        # Kiểm tra các bước thực thi đầy đủ
        expected_steps = [
            "intent_clarifier", "schema_linking", "sql_generator",
            "plan_validator", "executor", "response_formatter"
        ]
        for step in expected_steps:
            self.assertIn(step, final_state.steps_executed)

        self.assertFalse(final_state.clarification_needed)
        self.assertIsNotNone(final_state.sql_query)
        self.assertIn("SELECT", final_state.sql_query.upper())
        self.assertIsNotNone(final_state.query_result)
        self.assertIsNotNone(final_state.final_response)
        self.assertIn("KẾT QUẢ PHÂN TÍCH", final_state.final_response)

    def test_orchestrator_self_correction_loop(self):
        """Kiểm tra cơ chế tự sửa lỗi (Self-Correction Loop) khi phát hiện cột gõ sai."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        attempt_counter = [0]
        def custom_mock_llm(prompt: str, system_prompt: str, role: str) -> str:
            if role == "coder":
                attempt_counter[0] += 1
                if attempt_counter[0] == 1:
                    return "```sql\nSELECT dien_tich, price FROM orders LIMIT 10;\n```"
                else:
                    return "```sql\nSELECT area, price FROM orders LIMIT 10;\n```"
            return "Nhận định nghiệp vụ mẫu."

        orchestrator.llm.set_mock_handler(custom_mock_llm)

        query = "Xem diện tích và giá nhà"
        state = orchestrator.invoke(query)

        self.assertGreaterEqual(state.retry_count, 1)
        self.assertEqual(attempt_counter[0], 2)
        self.assertIn("area", state.sql_query)
        self.assertNotIn("dien_tich", state.sql_query)
        self.assertTrue(state.validation_result.is_valid)

    def test_orchestrator_hitl_gate(self):
        """Kiểm tra cổng kiểm duyệt Human-In-The-Loop: Tạm dừng và tiếp tục khi được phê duyệt."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        state = AgentState(
            user_query="Truy vấn toàn bộ dữ liệu 3.5 triệu bản ghi",
            domain_id="ecommerce"
        )
        
        def mock_validate(sql, schema_context=None, use_explain=False):
            return ValidationResult(
                is_valid=True,
                risk_level="WARNING",
                warnings=["Quét dung lượng lớn"],
                cardinality_estimate=2_000_000,
                tablets_scanned=120,
                requires_hitl=True
            )
        orchestrator.validator_node.plan_validator.validate = mock_validate

        # 1. Chạy invoke -> Phải dừng tại HITL Gate vì hitl_approved là None
        paused_state = orchestrator.invoke(state)
        self.assertTrue(paused_state.requires_hitl)
        self.assertIsNone(paused_state.hitl_approved)
        self.assertIn("[HITL_AWAITING_APPROVAL]", paused_state.final_response)
        self.assertNotIn("executor", paused_state.steps_executed)

        # 2. Người dùng phê duyệt (approved=True) -> Tiếp tục chạy đến executor và formatter
        resumed_state = orchestrator.resume_hitl(paused_state, approved=True)
        self.assertTrue(resumed_state.hitl_approved)
        self.assertIn("executor", resumed_state.steps_executed)
        self.assertIn("response_formatter", resumed_state.steps_executed)
        self.assertIsNotNone(resumed_state.final_response)
        self.assertNotIn("[HITL_AWAITING_APPROVAL]", resumed_state.final_response)

    def test_orchestrator_streaming(self):
        """Kiểm tra cơ chế stream phát ra các bước tuần tự phục vụ SSE."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        query = "Thống kê đơn hàng tháng này"
        events = list(orchestrator.stream(query))

        step_names = [e[0] for e in events]
        self.assertIn("intent_clarifier", step_names)
        self.assertIn("schema_linking", step_names)
        self.assertIn("sql_generator", step_names)
        self.assertIn("plan_validator", step_names)
        self.assertIn("executor", step_names)
        self.assertIn("response_formatter", step_names)

        final_state = events[-1][1]
        self.assertIsNotNone(final_state.final_response)
        self.assertIsNotNone(final_state.execution_time_ms)


if __name__ == "__main__":
    unittest.main()
