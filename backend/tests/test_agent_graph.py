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


class TestAgentStateMachine(unittest.TestCase):
    """Bộ kiểm thử cỗ máy trạng thái đa tác tử."""

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
        memory = ThreeTierMemory()

        # 1. Short-Term Memory
        err1 = memory.short_term.record_error(
            raw_error="Unknown column 'dien_tich' in 'field list'",
            vn_advice="Đổi 'dien_tich' thành 'area'",
            sql="SELECT dien_tich FROM real_estate_listings"
        )
        self.assertEqual(err1.category, "GRAMMAR")
        self.assertEqual(len(memory.short_term.grammar_errors), 1)

        feedback_prompt = memory.short_term.get_feedback_prompt()
        self.assertIn("SHORT-TERM MEMORY FEEDBACK", feedback_prompt)
        self.assertIn("dien_tich", feedback_prompt)

        # 2. Temporary Memory & Bellman Scoring
        # Step 1: Failed (-0.5)
        memory.temporary.add_step("sql_gen", {"error": "syntax"}, reward=-0.5)
        self.assertAlmostEqual(memory.temporary.get_latest_value(), -0.5)

        # Step 2: Succeeded (+1.0)
        memory.temporary.add_step("sql_val", {"status": "ok"}, reward=1.0)
        # v(S1) = -0.5 + 0.9 * (1.0) = 0.4; v(S2) = 1.0
        self.assertAlmostEqual(memory.temporary.get_latest_value(), 1.0)
        self.assertFalse(memory.temporary.is_stuck_in_loop())

        # 3. Long-Term Memory
        initial_good = len(memory.long_term.good_plans)
        memory.long_term.save_plan("Query test", "real_estate", "SELECT 1;", is_successful=True)
        self.assertEqual(len(memory.long_term.good_plans), initial_good + 1)

    def test_intent_clarifier_normal_query(self):
        """Kiểm tra câu hỏi rõ ràng được chuẩn hóa và không kích hoạt hỏi lại."""
        node = IntentClarifierNode(llm=self.llm)
        state = AgentState(user_query="Tìm mua chung cư tại Cầu Giấy dưới 3 tỷ")

        res_state = node(state)
        self.assertEqual(res_state.domain_id, "real_estate")
        self.assertFalse(res_state.clarification_needed)
        self.assertIsNone(res_state.clarification_question)
        self.assertEqual(res_state.extracted_entities.get("property_type"), "Căn hộ chung cư")
        self.assertEqual(res_state.extracted_entities.get("district"), "Cầu Giấy")
        self.assertIn("intent_clarifier", res_state.steps_executed)

    def test_intent_clarifier_vague_query_triggers_loop(self):
        """Kiểm tra câu hỏi mơ hồ kích hoạt hỏi lại (Clarification Loop)."""
        node = IntentClarifierNode(llm=self.llm)
        state = AgentState(user_query="xem giá")

        res_state = node(state)
        self.assertTrue(res_state.clarification_needed)
        self.assertIsNotNone(res_state.clarification_question)
        self.assertIn("anh/chị", res_state.clarification_question.lower())

    def test_orchestrator_e2e_real_estate(self):
        """Kiểm tra toàn bộ luồng E2E câu hỏi BĐS thông thường."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        query = "Thống kê giá chung cư tại Hà Nội tháng trước"
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
        self.assertIn("real_estate_listings", final_state.sql_query)
        self.assertIsNotNone(final_state.query_result)
        self.assertIsNotNone(final_state.final_response)
        self.assertIn("KẾT QUẢ PHÂN TÍCH", final_state.final_response)
        self.assertIsNotNone(final_state.chart_config)

    def test_orchestrator_self_correction_loop(self):
        """Kiểm tra cơ chế tự sửa lỗi (Self-Correction Loop) khi phát hiện cột gõ sai."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        # Giả lập Coder lần đầu trả về cột lỗi 'dien_tich' (gõ nhầm tiếng Việt), sau đó sửa thành 'area'
        attempt_counter = [0]
        def custom_mock_llm(prompt: str, system_prompt: str, role: str) -> str:
            if role == "coder":
                attempt_counter[0] += 1
                if attempt_counter[0] == 1:
                    # Lần 1: Cố tình sinh ra cột không tồn tại 'dien_tich'
                    return "```sql\nSELECT dien_tich, price FROM real_estate_listings LIMIT 10;\n```"
                else:
                    # Lần 2: Đã tiếp nhận feedback từ ShortTermMemory và sửa thành 'area'
                    return "```sql\nSELECT area, price FROM real_estate_listings LIMIT 10;\n```"
            return "Nhận định nghiệp vụ mẫu."

        orchestrator.llm.set_mock_handler(custom_mock_llm)

        query = "Xem diện tích và giá nhà"
        state = orchestrator.invoke(query)

        # Xác nhận đã kích hoạt vòng lặp tự sửa lỗi
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

        # Tạo một state đã được đánh dấu requires_hitl = True
        state = AgentState(
            user_query="Truy vấn toàn bộ dữ liệu 3.5 triệu bản ghi",
            domain_id="real_estate"
        )
        
        # Thiết lập giả lập validator đánh dấu requires_hitl = True
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

        query = "Thống kê căn hộ chung cư Hà Nội"
        events = list(orchestrator.stream(query))

        step_names = [e[0] for e in events]
        self.assertIn("intent_clarifier", step_names)
        self.assertIn("schema_linking", step_names)
        self.assertIn("sql_generator", step_names)
        self.assertIn("plan_validator", step_names)
        self.assertIn("executor", step_names)
        self.assertIn("response_formatter", step_names)

        # Kiểm tra đối tượng state của bước cuối
        final_state = events[-1][1]
        self.assertIsNotNone(final_state.final_response)
        self.assertIsNotNone(final_state.execution_time_ms)


if __name__ == "__main__":
    unittest.main()
