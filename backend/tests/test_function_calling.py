import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.tools.definitions import SQL_GENERATION_TOOL, CLARIFICATION_TOOL
from app.agent.nodes.sql_generator import SQLGeneratorNode
from app.agent.nodes.intent_node import IntentClarifierNode


class TestQwenFunctionCalling(unittest.TestCase):
    """Kiểm tra chức năng Function Calling chuẩn của Qwen trong hệ thống."""

    def test_sql_generation_tool_definition(self):
        """Kiểm tra schema của tool generate_sql_query đúng chuẩn OpenAI/Qwen."""
        self.assertEqual(SQL_GENERATION_TOOL["type"], "function")
        fn = SQL_GENERATION_TOOL["function"]
        self.assertEqual(fn["name"], "generate_sql_query")
        self.assertIn("sql", fn["parameters"]["properties"])
        self.assertIn("tables_used", fn["parameters"]["properties"])
        self.assertIn("sql", fn["parameters"]["required"])

    def test_clarification_tool_definition(self):
        """Kiểm tra schema của tool ask_clarification đúng chuẩn OpenAI/Qwen."""
        self.assertEqual(CLARIFICATION_TOOL["type"], "function")
        fn = CLARIFICATION_TOOL["function"]
        self.assertEqual(fn["name"], "ask_clarification")
        self.assertIn("question", fn["parameters"]["properties"])
        self.assertIn("question", fn["parameters"]["required"])

    def test_call_with_tools_mock_handler(self):
        """Kiểm tra call_with_tools tự động đóng gói kết quả thành tool_call khi có mock_handler."""
        llm = DualModelLLM()

        def custom_handler(prompt, sys_prompt, role):
            return "```sql\nSELECT province_name, COUNT(*) FROM real_estate_listings GROUP BY 1;\n```"

        llm.set_mock_handler(custom_handler)

        res = llm.call_with_tools(
            messages=[{"role": "user", "content": "Thống kê số lượng tin theo tỉnh thành"}],
            tools=[SQL_GENERATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_sql_query"}},
            role="coder"
        )

        self.assertEqual(res["type"], "tool_call")
        self.assertEqual(len(res["tool_calls"]), 1)
        tool_call = res["tool_calls"][0]
        self.assertEqual(tool_call["name"], "generate_sql_query")
        self.assertIn("SELECT province_name", tool_call["arguments"]["sql"])
        self.assertIn("real_estate_listings", tool_call["arguments"]["tables_used"])

    def test_sql_generator_node_with_function_calling(self):
        """Kiểm tra SQLGeneratorNode trích xuất SQL trực tiếp từ Function Call arguments."""
        llm = DualModelLLM()

        def mock_tool_generator(prompt, sys_prompt, role):
            return "```sql\nSELECT title, price FROM real_estate_listings ORDER BY price DESC LIMIT 5;\n```"

        llm.set_mock_handler(mock_tool_generator)
        node = SQLGeneratorNode(llm=llm)

        state = AgentState(
            user_query="Top 5 bất động sản đắt nhất",
            domain_id="real_estate"
        )
        out_state = node(state)

        self.assertIsNotNone(out_state.sql_query)
        self.assertTrue(out_state.sql_query.upper().startswith("SELECT"))
        self.assertIn("real_estate_listings", out_state.sql_query)
        self.assertIn("LIMIT 5", out_state.sql_query)

    def test_intent_clarifier_with_clarification_tool(self):
        """Kiểm tra IntentClarifierNode kích hoạt Function Call ask_clarification khi câu hỏi mơ hồ."""
        llm = DualModelLLM()
        node = IntentClarifierNode(llm=llm)

        # Câu hỏi mơ hồ (< 3 từ, không có thực thể)
        state = AgentState(
            user_query="Xem giá",
            domain_id="real_estate"
        )
        out_state = node(state)

        self.assertTrue(out_state.clarification_needed)
        self.assertIsNotNone(out_state.clarification_question)
        self.assertTrue(len(out_state.clarification_question) > 10)


if __name__ == "__main__":
    unittest.main()
