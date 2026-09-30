"""
Executor Node (Node 6).
Thực thi câu lệnh SQL an toàn trên Data Warehouse (DuckDB) và thu thập tập kết quả.
"""

import logging
from typing import Optional, List, Dict, Any, Callable, Union
from app.agent.state import AgentState
from app.db.duckdb_client import DuckDBClient
from app.db.warehouse_client import get_warehouse_client

logger = logging.getLogger("ExecutorNode")


class ExecutorNode:
    """Node thực thi câu truy vấn SQL và lưu kết quả vào AgentState."""

    def __init__(
        self,
        warehouse_client: Optional[DuckDBClient] = None
    ):
        self._explicit_client = warehouse_client
        self.warehouse_client = warehouse_client or get_warehouse_client()
        self._mock_executor: Optional[Callable[[str], List[Dict[str, Any]]]] = None

    def set_mock_executor(self, executor: Optional[Callable[[str], List[Dict[str, Any]]]]) -> None:
        """Cho phép gán executor giả lập phục vụ unit test."""
        self._mock_executor = executor

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("executor")

        # Nếu không có câu SQL hoặc trước đó đã bị dừng
        if not state.sql_query:
            state.query_result = []
            state.column_names = []
            return state

        # 1. Sử dụng mock executor nếu có (dành riêng cho unit tests)
        if self._mock_executor:
            results = self._mock_executor(state.sql_query)
            state.query_result = results
            state.column_names = list(results[0].keys()) if results else []
            return state

        # 2. Định tuyến client theo domain_id nếu không được chỉ định cố định
        client = self._explicit_client or get_warehouse_client(domain_id=state.domain_id)

        # 3. Thực thi trực tiếp trên Data Warehouse thật
        try:
            results = client.execute_query_dict(state.sql_query, max_rows=500)
            state.query_result = results
            state.column_names = list(results[0].keys()) if results else []
            return state
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Lỗi thực thi truy vấn trên Data Warehouse ({err_msg}).")
            state.error_message = f"Lỗi thực thi SQL: {err_msg}"
            state.query_result = []
            state.column_names = []
            return state

