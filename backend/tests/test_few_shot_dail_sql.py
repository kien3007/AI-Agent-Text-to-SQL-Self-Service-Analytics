"""
Unit and Integration Tests for DAIL-SQL Dynamic Few-Shot In-Context Learning and Auto-Learning Loop.
"""

import os
import sys
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

class MockEmbedding(EmbeddingFunction):
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.0] * 1024 for _ in input]


from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.memory.three_tier_memory import LongTermMemory, ThreeTierMemory
from app.agent.nodes.sql_generator import SQLGeneratorNode
from app.agent.graph import AgentOrchestrator
from app.schemas.schema_context import SchemaContext, ColumnContext


class TestFewShotDailSQL(unittest.TestCase):
    """Kiểm thử kỹ thuật Dynamic Few-Shot In-Context Learning (kế thừa DAIL-SQL)."""

    def setUp(self):
        self.mock_emb = MockEmbedding()
        self.ltm = LongTermMemory(seed_defaults=True)

    def test_long_term_memory_seeds(self):
        """Kiểm tra LongTermMemory được khởi tạo sẵn với các mẫu dbt Marts và Steiner Tree joins."""
        self.assertGreaterEqual(len(self.ltm.good_plans), 4)

        domains = {p["domain_id"] for p in self.ltm.good_plans}
        self.assertIn("real_estate", domains)
        self.assertIn("ecommerce", domains)
        self.assertIn("healthcare", domains)

        # Kiểm tra sự xuất hiện của dbt Marts trong seed
        sqls = [p["sql"] for p in self.ltm.good_plans]
        self.assertTrue(any("fct_district_monthly_summary" in s for s in sqls))
        self.assertTrue(any("fct_real_estate_analytics" in s for s in sqls))

    def test_dynamic_few_shot_retrieval(self):
        """Kiểm tra hàm get_relevant_few_shots tìm đúng ví dụ mẫu phù hợp ngữ cảnh."""
        # 1. Câu hỏi về xu hướng thị trường -> Tìm ra fct_district_monthly_summary
        results_re = self.ltm.get_relevant_few_shots(
            query="Thống kê biến động giá chung cư Cầu Giấy",
            domain_id="real_estate",
            top_k=1
        )
        self.assertEqual(len(results_re), 1)
        self.assertIn("fct_district_monthly_summary", results_re[0]["sql"])

        # 2. Câu hỏi E-commerce GMV -> Tìm ra customers JOIN orders
        results_ecom = self.ltm.get_relevant_few_shots(
            query="Tính doanh thu GMV của khách hàng",
            domain_id="ecommerce",
            top_k=1
        )
        self.assertEqual(len(results_ecom), 1)
        self.assertIn("customers", results_ecom[0]["sql"])
        self.assertIn("orders", results_ecom[0]["sql"])

    def test_sql_generator_prompt_incorporates_few_shot(self):
        """Kiểm tra SQLGeneratorNode tự động ghép khối Few-Shot vào prompt."""
        captured_prompts = []

        def mock_llm_handler(prompt: str, system_prompt: str, role: str) -> str:
            captured_prompts.append(prompt)
            return "```sql\nSELECT 1;\n```"

        llm = DualModelLLM()
        llm.set_mock_handler(mock_llm_handler)

        node = SQLGeneratorNode(llm=llm, long_term_memory=self.ltm)
        state = AgentState(
            user_query="Biến động giá chung cư Cầu Giấy qua các tháng",
            domain_id="real_estate"
        )
        state.schema_context = SchemaContext(
            selected_tables=["fct_district_monthly_summary"],
            relevant_columns=[],
            prompt_context="### SCHEMA: fct_district_monthly_summary"
        )

        node(state)

        self.assertEqual(len(captured_prompts), 1)
        sent_prompt = captured_prompts[0]
        self.assertIn("DYNAMIC FEW-SHOT TỪ LONG-TERM MEMORY", sent_prompt)
        self.assertIn("fct_district_monthly_summary", sent_prompt)

    def test_auto_learning_loop_e2e(self):
        """Kiểm tra vòng tự học (Continuous Auto-Learning Loop): Query mới thành công -> Trở thành Good Plan."""
        orchestrator = AgentOrchestrator(
            embedding_function=self.mock_emb,
            use_explain=False
        )

        initial_count = len(orchestrator.memory.long_term.good_plans)

        new_query = "Tìm biệt thự tại Tây Hồ giá trên 30 tỷ"
        state = orchestrator.invoke(new_query)

        # Kiểm tra câu query đã được thực thi và tự động lưu vào Good Plans
        self.assertIsNotNone(state.sql_query)
        self.assertGreater(len(orchestrator.memory.long_term.good_plans), initial_count)

        # Kiểm tra câu hỏi tiếp theo có thể truy xuất lại câu vừa học
        matched = orchestrator.memory.long_term.get_relevant_few_shots(
            query="Mua biệt thự Tây Hồ",
            domain_id="real_estate",
            top_k=2
        )
        matched_queries = [m["query"] for m in matched]
        self.assertIn(new_query, matched_queries)


if __name__ == "__main__":
    unittest.main()
