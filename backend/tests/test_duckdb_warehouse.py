"""
Unit tests for DuckDB Data Warehouse Client and Integration.
Kiểm thử toàn diện DuckDBClient, Factory WarehouseClient, ExecutorNode và PlanValidator.
"""

import os
import sys
import unittest
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.duckdb_client import DuckDBClient
from app.db.warehouse_client import get_warehouse_client
from app.agent.nodes.executor_node import ExecutorNode
from app.agent.nodes.plan_validator import PlanValidator
from app.agent.state import AgentState


class TestDuckDBWarehouse(unittest.TestCase):
    """Bộ kiểm thử DuckDB Client cho Data Warehouse OLAP."""

    @classmethod
    def setUpClass(cls):
        # Sử dụng database warehouse.duckdb sẵn có hoặc tạo in-memory table
        cls.client = DuckDBClient()
        # Đảm bảo có bảng/view test
        conn = cls.client.get_connection(read_only=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_orders (
                id INTEGER PRIMARY KEY,
                customer_name VARCHAR,
                amount DOUBLE,
                created_at TIMESTAMP
            );
            DELETE FROM test_orders;
            INSERT INTO test_orders VALUES 
                (1, 'Alice', 150.0, '2026-01-10 10:00:00'),
                (2, 'Bob', 250.5, '2026-01-11 11:30:00'),
                (3, 'Charlie', 50.0, '2026-01-12 09:15:00');
        """)
        conn.close()

    def test_execute_query_tuple(self):
        cols, rows = self.client.execute_query("SELECT id, customer_name, amount FROM test_orders ORDER BY id")
        self.assertEqual(cols, ["id", "customer_name", "amount"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][1], "Alice")

    def test_execute_query_dict(self):
        records = self.client.execute_query_dict("SELECT * FROM test_orders ORDER BY id")
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["customer_name"], "Alice")
        self.assertEqual(records[0]["amount"], 150.0)
        self.assertIn("created_at", records[0])
        # Đảm bảo datetime đã được serialize string an toàn
        self.assertIsInstance(records[0]["created_at"], str)

    def test_explain_query(self):
        explain_res = self.client.explain_query("SELECT customer_name, SUM(amount) FROM test_orders GROUP BY customer_name")
        self.assertTrue(explain_res["success"])
        self.assertIn("raw_explain", explain_res)
        self.assertGreaterEqual(explain_res["tablets_scanned"], 1)

    def test_warehouse_factory(self):
        w_client = get_warehouse_client(backend="duckdb")
        self.assertIsInstance(w_client, DuckDBClient)

    def test_executor_node_with_duckdb(self):
        executor = ExecutorNode(warehouse_client=self.client)
        state = AgentState(
            user_query="Tổng tiền của Bob",
            domain_id="ecommerce",
            sql_query="SELECT customer_name, amount FROM test_orders WHERE customer_name = 'Bob'"
        )
        out_state = executor.execute(state)
        self.assertIsNotNone(out_state.query_result)
        self.assertEqual(len(out_state.query_result), 1)
        self.assertEqual(out_state.query_result[0]["customer_name"], "Bob")
        self.assertEqual(out_state.query_result[0]["amount"], 250.5)

    def test_plan_validator_with_duckdb_explain(self):
        validator = PlanValidator(warehouse_client=self.client)
        # Truy vấn hợp lệ
        res = validator.validate("SELECT * FROM test_orders LIMIT 10", use_explain=True)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.risk_level, "SAFE")

        # Truy vấn có lỗi cú pháp
        res_err = validator.validate("SELECT non_existent_col FROM test_orders", use_explain=True)
        self.assertFalse(res_err.is_valid)
        self.assertEqual(res_err.risk_level, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
