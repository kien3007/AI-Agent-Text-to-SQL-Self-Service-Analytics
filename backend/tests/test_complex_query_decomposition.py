"""
Unit and Integration Tests for DIN-SQL Complex Query Decomposition (Sub-task & CTE Decomposition).
"""

import os
import sys
import unittest
from typing import List, Dict, Any

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

class MockEmbedding:
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: List[str]) -> List[List[float]]:
        return [[0.0] * 1024 for _ in input]


from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.nodes.intent_node import IntentClarifierNode
from app.agent.nodes.sql_generator import SQLGeneratorNode
from app.agent.nodes.response_formatter import ResponseFormatterNode
from app.agent.graph import AgentOrchestrator


class TestComplexQueryDecomposition(unittest.TestCase):
    """Kiểm thử kỹ thuật phân rã câu hỏi phức tạp thành các bài toán con / CTEs (kế thừa DIN-SQL)."""

    @classmethod
    def setUpClass(cls):
        from app.db.warehouse_client import get_warehouse_client
        from app.core.domain_manager import DomainManager
        from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile

        cls.client = get_warehouse_client()
        cls.client.execute_query("DROP TABLE IF EXISTS monthly_sales;")
        cls.client.execute_query("""
            CREATE TABLE monthly_sales (
                district VARCHAR,
                category VARCHAR,
                price DOUBLE,
                metric_val DOUBLE,
                published_at VARCHAR,
                year_month VARCHAR
            );
        """)
        cls.client.execute_query("DELETE FROM monthly_sales;")
        cls.client.execute_query("""
            INSERT INTO monthly_sales (district, category, price, metric_val, published_at, year_month) VALUES 
            ('Cầu Giấy', 'Chung cư', 3500000000.0, 3500000000.0, '2026-02-15', '2026-02'),
            ('Cầu Giấy', 'Chung cư', 3000000000.0, 3000000000.0, '2026-01-15', '2026-01');
        """)

        cls.dm = DomainManager()
        cls.test_domain = DomainConfig(
            domain_id="retail_analytics",
            display_name="Retail Analytics",
            description="Dữ liệu phân tích bán lẻ & doanh thu",
            domain_keywords=["giá", "quận", "so sánh", "tháng"],
            tables={
                "monthly_sales": TableProfile(
                    table_name="monthly_sales",
                    columns={
                        "district": ColumnProfile(name="district", data_type="VARCHAR"),
                        "category": ColumnProfile(name="category", data_type="VARCHAR"),
                        "price": ColumnProfile(name="price", data_type="DOUBLE"),
                        "metric_val": ColumnProfile(name="metric_val", data_type="DOUBLE"),
                        "published_at": ColumnProfile(name="published_at", data_type="VARCHAR"),
                        "year_month": ColumnProfile(name="year_month", data_type="VARCHAR")
                    }
                )
            }
        )
        cls.dm.register_domain(cls.test_domain)

    def setUp(self):
        self.mock_emb = MockEmbedding()
        self.intent_node = IntentClarifierNode()
        self.formatter_node = ResponseFormatterNode()

    def test_intent_node_complexity_classification(self):
        """Kiểm tra phân loại mức độ phức tạp (EASY, MEDIUM, COMPLEX) từ DIN-SQL."""
        # 1. Câu hỏi Mức 1: Đơn giản (Filter trực tiếp)
        easy_state = AgentState(user_query="Giá nhà Cầu Giấy dưới 3 tỷ", domain_id="real_estate")
        easy_res = self.intent_node(easy_state)
        self.assertEqual(easy_res.complexity_level, "EASY")
        self.assertIsNone(easy_res.decomposition_plan)

        # 2. Câu hỏi Mức 2: Trung bình (Group by / Filter nhiều điều kiện)
        medium_state = AgentState(user_query="Thống kê số lượng tin đăng theo từng quận và chi tiết loại nhà", domain_id="real_estate")
        medium_res = self.intent_node(medium_state)
        self.assertEqual(medium_res.complexity_level, "MEDIUM")

        # 3. Câu hỏi Mức 3: Phức tạp (So sánh chu kỳ thời gian YoY/MoM)
        complex_state = AgentState(
            user_query="So sánh giá trung bình từng quận tháng 2 so với tháng 1 và tính tỷ lệ tăng trưởng",
            domain_id="real_estate"
        )
        complex_res = self.intent_node(complex_state)
        self.assertEqual(complex_res.complexity_level, "COMPLEX")
        self.assertIsNotNone(complex_res.decomposition_plan)

    def test_intent_node_decomposition_plan_period_comparison(self):
        """Kiểm tra kế hoạch phân rã CTEs cho dạng PERIOD_COMPARISON (YoY / MoM)."""
        state = AgentState(
            user_query="So sánh biến động giá bất động sản theo từng quận giữa tháng 2 và tháng 1",
            domain_id="real_estate"
        )
        res = self.intent_node(state)
        self.assertEqual(res.complexity_level, "COMPLEX")
        plan = res.decomposition_plan
        self.assertIsNotNone(plan)
        self.assertEqual(plan["type"], "PERIOD_COMPARISON")
        self.assertIn("cur_period", plan["cte_names"])
        self.assertIn("prev_period", plan["cte_names"])
        self.assertEqual(plan["target_metric"], "growth_pct")
        self.assertEqual(len(plan["sub_tasks"]), 3)

    def test_intent_node_decomposition_plan_window_ranking(self):
        """Kiểm tra kế hoạch phân rã CTEs cho dạng WINDOW_RANKING (ROW_NUMBER PARTITION BY)."""
        state = AgentState(
            user_query="Top 3 bất động sản giá cao nhất từng quận",
            domain_id="real_estate"
        )
        res = self.intent_node(state)
        self.assertEqual(res.complexity_level, "COMPLEX")
        plan = res.decomposition_plan
        self.assertIsNotNone(plan)
        self.assertEqual(plan["type"], "WINDOW_RANKING")
        self.assertIn("ranked_items", plan["cte_names"])
        self.assertTrue(any("ROW_NUMBER()" in step for step in plan["sub_tasks"]))

    def test_sql_generator_incorporates_decomposition_plan(self):
        """Kiểm tra SQLGeneratorNode tự động chèn Kế hoạch phân rã CTEs vào prompt và sinh SQL có WITH."""
        from app.agent.memory.three_tier_memory import ThreeTierMemory
        sql_node = SQLGeneratorNode(memory=ThreeTierMemory(embedding_function=self.mock_emb))

        captured_prompt = []
        original_generate = sql_node.llm.generate

        def mock_generate(prompt, **kwargs):
            captured_prompt.append(prompt)
            return original_generate(prompt, **kwargs)

        sql_node.llm.generate = mock_generate

        state = AgentState(
            user_query="So sánh giá căn hộ tháng 2 so với tháng 1 từng quận",
            domain_id="real_estate",
            complexity_level="COMPLEX",
            decomposition_plan={
                "type": "PERIOD_COMPARISON",
                "cte_names": ["cur_period", "prev_period"],
                "target_metric": "growth_pct",
                "sub_tasks": [
                    "Bước 1 (CTE cur_period): Tính avg_price tháng 2.",
                    "Bước 2 (CTE prev_period): Tính avg_price tháng 1.",
                    "Bước 3 (Main Query): JOIN và tính tỷ lệ growth_pct."
                ]
            }
        )

        res_state = sql_node(state)

        # 1. Kiểm tra prompt chứa chỉ dẫn phân rã DIN-SQL
        self.assertTrue(len(captured_prompt) > 0)
        self.assertIn("KẾ HOẠCH PHÂN RÃ BÀI TOÁN CON (DECOMPOSITION PLAN - DIN-SQL)", captured_prompt[0])
        self.assertIn("PERIOD_COMPARISON", captured_prompt[0])
        self.assertIn("cur_period, prev_period", captured_prompt[0])

        # 2. Kiểm tra SQL sinh ra tuân thủ cấu trúc CTE WITH
        self.assertIsNotNone(res_state.sql_query)
        self.assertTrue(res_state.sql_query.upper().startswith("WITH"))
        self.assertIn("cur_period", res_state.sql_query)
        self.assertIn("prev_period", res_state.sql_query)
        self.assertIn("growth_pct", res_state.sql_query)

    def test_response_formatter_growth_pct_formatting(self):
        """Kiểm tra ResponseFormatterNode định dạng cột growth_pct có dấu (+/-) và ký hiệu %."""
        sample_rows = [
            {"district": "Cầu Giấy", "avg_price_cur": 3_500_000_000, "avg_price_prev": 3_000_000_000, "growth_pct": 16.67},
            {"district": "Ba Đình", "avg_price_cur": 4_000_000_000, "avg_price_prev": 4_200_000_000, "growth_pct": -4.76},
            {"district": "Tây Hồ", "avg_price_cur": 5_000_000_000, "avg_price_prev": 5_000_000_000, "growth_pct": 0.0}
        ]

        formatted = self.formatter_node._format_table_data(sample_rows)

        self.assertEqual(formatted[0]["growth_pct"], "+16.67%")
        self.assertEqual(formatted[1]["growth_pct"], "-4.76%")
        self.assertEqual(formatted[2]["growth_pct"], "0.0%")

        # Kiểm tra tiền tệ vẫn được định dạng tỷ VNĐ
        self.assertIn("tỷ VNĐ", formatted[0]["avg_price_cur"])

    def test_end_to_end_orchestrator_complex_query(self):
        """Kiểm tra toàn bộ luồng End-to-End State Machine cho câu hỏi phân tích Mức 3."""
        orchestrator = AgentOrchestrator(embedding_function=self.mock_emb)

        query = "So sánh giá bất động sản theo từng quận giữa tháng 02/2026 và tháng 01/2026"
        state = orchestrator.invoke(input_val=query, domain_id="retail_analytics")

        # 1. Trạng thái phân loại Mức 3 (COMPLEX)
        self.assertEqual(state.complexity_level, "COMPLEX")
        self.assertIsNotNone(state.decomposition_plan)
        self.assertEqual(state.decomposition_plan["type"], "PERIOD_COMPARISON")

        # 2. Câu SQL đã thực thi chứa CTE
        self.assertIsNotNone(state.sql_query)
        self.assertTrue(state.sql_query.upper().startswith("WITH"))
        self.assertIn("growth_pct", state.sql_query)

        # 3. Kết quả phản hồi hoàn chỉnh
        self.assertIsNotNone(state.final_response)
        self.assertTrue("Nhận định Chuyên sâu" in state.final_response or "Thông báo dữ liệu" in state.final_response or len(state.final_response) > 50)


if __name__ == "__main__":
    unittest.main()
