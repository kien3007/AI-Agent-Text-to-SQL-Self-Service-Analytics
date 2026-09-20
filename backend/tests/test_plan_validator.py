import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.agent.nodes.plan_validator import PlanValidator, ValidationResult
from app.schemas.schema_context import SchemaContext, ColumnContext


class TestPlanValidator(unittest.TestCase):
    """Kiểm thử PlanValidator với các tầng bảo vệ an toàn SQL, Cross-Join và Fan-Trap."""

    def setUp(self):
        self.validator = PlanValidator()
        self.schema_context = SchemaContext(
            selected_tables=["orders", "order_items"],
            table_name="orders",
            join_paths=["INNER JOIN order_items ON orders.id = order_items.order_id"],
            cardinality_warnings=["Quan hệ 1-N giữa 'orders' và 'order_items' có nguy cơ nhân bản dòng (Fan Trap)."],
            relevant_columns=[
                ColumnContext(name="id", table_name="orders", data_type="BIGINT", vn_name="Mã đơn", description="ID"),
                ColumnContext(name="total_amount", table_name="orders", data_type="DOUBLE", vn_name="Tổng tiền", description="Tiền"),
                ColumnContext(name="quantity", table_name="order_items", data_type="INT", vn_name="Số lượng", description="Số lượng")
            ],
            prompt_context=""
        )

    def test_valid_safe_sql(self):
        sql = "SELECT id, total_amount FROM orders WHERE total_amount > 1000000 LIMIT 10"
        res = self.validator.validate(sql, self.schema_context)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.risk_level, "SAFE")
        self.assertEqual(len(res.errors), 0)

    def test_block_destructive_sql(self):
        bad_sqls = [
            "DROP TABLE orders",
            "DELETE FROM orders WHERE id = 1",
            "TRUNCATE TABLE customers",
            "UPDATE orders SET total_amount = 0"
        ]
        for sql in bad_sqls:
            res = self.validator.validate(sql)
            self.assertFalse(res.is_valid, f"SQL phá hoại '{sql}' phải bị chặn!")
            self.assertEqual(res.risk_level, "BLOCKED")
            self.assertGreater(len(res.errors), 0)

    def test_detect_cartesian_cross_join(self):
        # 1. Dùng từ khóa CROSS JOIN
        cross_sql = "SELECT * FROM orders CROSS JOIN customers"
        res = self.validator.validate(cross_sql)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.risk_level, "BLOCKED")
        self.assertIn("Cartesian Product", " ".join(res.errors))

        # 2. Liệt kê nhiều bảng sau FROM không có WHERE
        comma_sql = "SELECT * FROM orders, customers"
        res2 = self.validator.validate(comma_sql)
        self.assertFalse(res2.is_valid)
        self.assertEqual(res2.risk_level, "BLOCKED")

    def test_detect_fan_trap_warning(self):
        # Truy vấn có SUM qua 2 bảng có quan hệ 1-N
        fan_trap_sql = "SELECT SUM(orders.total_amount) FROM orders INNER JOIN order_items ON orders.id = order_items.order_id"
        res = self.validator.validate(fan_trap_sql, self.schema_context)
        self.assertTrue(res.is_valid) # Hợp lệ về cú pháp nhưng có cảnh báo
        self.assertEqual(res.risk_level, "WARNING")
        self.assertTrue(any("Fan-Trap" in w for w in res.warnings))

    def test_column_typo_translation(self):
        # Người dùng/LLM gõ nhầm cột tiếng Việt dien_tich
        typo_sql = "SELECT dien_tich, price FROM real_estate_listings"
        res = self.validator.validate(typo_sql, self.schema_context)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.risk_level, "BLOCKED")
        self.assertTrue(any("dien_tich" in e for e in res.errors))


if __name__ == "__main__":
    unittest.main()
