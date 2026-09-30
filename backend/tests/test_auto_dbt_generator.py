"""
Unit and Integration Tests for Autonomous dbt Auto-Adapter (AutoDbtGenerator) and Anti-Blindness Guardrails.
"""

import os
import sys
import unittest
import shutil

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile
from app.core.domain_manager import DomainManager
from app.core.dbt_generator import AutoDbtGenerator


class TestAutoDbtGenerator(unittest.TestCase):
    """Kiểm thử cỗ máy tự sinh dbt pipeline và các tầng guardrails chống mù quáng."""

    def setUp(self):
        self.generator = AutoDbtGenerator()
        self.dm = DomainManager()

    def test_anti_blindness_junk_table_filtering(self):
        """Guardrail 1: Kiểm tra tự động loại bỏ bảng rác, bảng kỹ thuật (logs, audit, session)."""
        junk_tables = [
            "log_user_events", "login_audit", "session_cache",
            "temp_import_data", "alembic_version", "flyway_schema_history"
        ]
        business_tables = [
            "orders", "customers", "order_items", "products",
            "hospital_encounters", "real_estate_listings"
        ]

        for jt in junk_tables:
            self.assertTrue(self.generator.is_ignorable_table(jt), f"Bảng {jt} phải bị loại bỏ!")

        for bt in business_tables:
            self.assertFalse(self.generator.is_ignorable_table(bt), f"Bảng {bt} là bảng nghiệp vụ hợp lệ!")

    def test_heuristic_column_categorization_and_timestamp_priority(self):
        """Guardrail 2: Kiểm tra phân loại cột và ưu tiên mốc thời gian hoàn tất trước mốc tạo đơn."""
        table = TableProfile(
            table_name="orders",
            vn_name="Đơn Hàng",
            columns={
                "order_id": ColumnProfile(name="order_id", vn_name="Mã đơn", description="Mã đơn hàng", data_type="INT", is_primary_key=True),
                "customer_id": ColumnProfile(name="customer_id", vn_name="Mã khách", description="Mã khách hàng", data_type="INT", foreign_key="customers.id"),
                "created_at": ColumnProfile(name="created_at", vn_name="Ngày tạo", description="Ngày tạo đơn", data_type="DATETIME"),
                "delivered_at": ColumnProfile(name="delivered_at", vn_name="Ngày giao", description="Ngày giao hàng", data_type="DATETIME"),
                "total_price": ColumnProfile(name="total_price", vn_name="Tổng tiền", description="Tổng tiền đơn", data_type="DECIMAL(12,2)"),
                "quantity": ColumnProfile(name="quantity", vn_name="Số lượng", description="Số lượng sản phẩm", data_type="INT"),
                "status": ColumnProfile(name="status", vn_name="Trạng thái", description="Trạng thái đơn hàng", data_type="VARCHAR(50)"),
                "payment_channel": ColumnProfile(name="payment_channel", vn_name="Kênh thanh toán", description="Kênh thanh toán", data_type="VARCHAR(50)")
            }
        )

        cat = self.generator.categorize_columns(table)

        # 1. Khóa
        self.assertEqual(cat["primary_keys"], ["order_id"])
        self.assertEqual(cat["foreign_keys"], ["customer_id"])

        # 2. Thời gian: delivered_at phải đứng TRƯỚC created_at do điểm ưu tiên cao hơn
        self.assertEqual(cat["time_columns"][0], "delivered_at")
        self.assertIn("created_at", cat["time_columns"])

        # 3. Metrics
        self.assertIn("total_price", cat["metric_columns"])
        self.assertIn("quantity", cat["metric_columns"])

        # 4. Dimensions
        self.assertIn("status", cat["dimension_columns"])
        self.assertIn("payment_channel", cat["dimension_columns"])

    def test_generate_staging_model_clean_syntax(self):
        """Kiểm tra mã SQL và YAML Staging được sinh ra đúng chuẩn dbt với TRIM và CAST."""
        table = TableProfile(
            table_name="customers",
            vn_name="Khách Hàng",
            columns={
                "customer_id": ColumnProfile(name="customer_id", vn_name="Mã khách", description="Mã khách hàng", data_type="INT", is_primary_key=True),
                "full_name": ColumnProfile(name="full_name", vn_name="Họ tên", description="Họ và tên", data_type="VARCHAR(100)"),
                "registration_date": ColumnProfile(name="registration_date", vn_name="Ngày đăng ký", description="Ngày đăng ký thành viên", data_type="DATE"),
                "loyalty_score": ColumnProfile(name="loyalty_score", vn_name="Điểm tích lũy", description="Điểm thành viên", data_type="INT")
            }
        )
        cat = self.generator.categorize_columns(table)
        sql, yml = self.generator.generate_staging_model(table, "ecommerce", cat)

        # Kiểm tra SQL
        self.assertIn("config(materialized='view')", sql)
        self.assertIn("TRIM(CAST(full_name AS VARCHAR))", sql)
        self.assertIn("CAST(registration_date AS DATE)", sql)
        self.assertIn("WHERE customer_id IS NOT NULL", sql)

        # Kiểm tra YAML
        self.assertIn("version: 2", yml)
        self.assertIn("stg_customers", yml)
        self.assertIn("unique", yml)
        self.assertIn("not_null", yml)

    def test_generate_marts_model_formula_and_dimensionality_cap(self):
        """Guardrail 3 & 4: Tự tính công thức kết hợp price * quantity và giới hạn số chiều dimensions."""
        table = TableProfile(
            table_name="order_items",
            vn_name="Chi Tiết Đơn Hàng",
            columns={
                "item_id": ColumnProfile(name="item_id", vn_name="Mã chi tiết", description="Mã chi tiết", data_type="INT", is_primary_key=True),
                "order_id": ColumnProfile(name="order_id", vn_name="Mã đơn", description="Mã đơn hàng", data_type="INT", foreign_key="orders.id"),
                "created_at": ColumnProfile(name="created_at", vn_name="Ngày tạo", description="Ngày tạo", data_type="DATETIME"),
                "unit_price": ColumnProfile(name="unit_price", vn_name="Đơn giá", description="Đơn giá sản phẩm", data_type="DECIMAL(10,2)"),
                "quantity": ColumnProfile(name="quantity", vn_name="Số lượng", description="Số lượng mua", data_type="INT"),
                "discount_amount": ColumnProfile(name="discount_amount", vn_name="Giảm giá", description="Tiền chiết khấu", data_type="DECIMAL(10,2)"),
                "category": ColumnProfile(name="category", vn_name="Ngành hàng", description="Phân loại ngành hàng", data_type="VARCHAR(50)"),
                "status": ColumnProfile(name="status", vn_name="Trạng thái", description="Trạng thái giao", data_type="VARCHAR(50)"),
                "city": ColumnProfile(name="city", vn_name="Thành phố", description="Tỉnh thành", data_type="VARCHAR(50)"),
                "warehouse": ColumnProfile(name="warehouse", vn_name="Kho", description="Kho xuất", data_type="VARCHAR(50)"),
                "shipper": ColumnProfile(name="shipper", vn_name="Đơn vị ship", description="Đơn vị vận chuyển", data_type="VARCHAR(50)")
            }
        )
        cat = self.generator.categorize_columns(table)
        res = self.generator.generate_marts_model(table, "ecommerce", cat)
        self.assertIsNotNone(res)

        sql, yml, meta = res

        # 1. Kiểm tra Guardrail 3: Tự động phát hiện price * quantity -> gross revenue
        self.assertIn("SUM(unit_price * quantity)", sql)
        self.assertIn("total_gross_revenue", sql)

        # 2. Kiểm tra Guardrail 4: Giới hạn tối đa 3 dimensions (GROUP BY time_col + max 3 dims)
        self.assertIn("GROUP BY", sql)
        self.assertIn("category", sql)
        self.assertIn("status", sql)
        self.assertIn("city", sql)
        group_by_clause = sql.split("GROUP BY")[1].split("ORDER BY")[0]
        self.assertNotIn("warehouse", group_by_clause)
        self.assertNotIn("shipper", group_by_clause)

        # 3. Kiểm tra Semantic Metrics được khai báo
        metric_names = [m["name"] for m in meta]
        self.assertTrue(any("total_gross_revenue" in mn for mn in metric_names))
        self.assertTrue(any("total_unit_price" in mn for mn in metric_names))

    def test_end_to_end_auto_dbt_and_agent_sync(self):
        """Kiểm tra toàn bộ luồng tạo dbt cho domain E-commerce và đồng bộ thẳng vào DomainManager."""
        ecommerce_config = DomainConfig(
            domain_id="ecommerce",
            display_name="E-Commerce",
            description="Hệ thống bán hàng thương mại điện tử",
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    columns={
                        "order_id": ColumnProfile(name="order_id", data_type="BIGINT", is_primary_key=True),
                        "order_date": ColumnProfile(name="order_date", data_type="TIMESTAMP"),
                        "total_amount": ColumnProfile(name="total_amount", data_type="DOUBLE"),
                        "status": ColumnProfile(name="status", data_type="VARCHAR")
                    }
                ),
                "customers": TableProfile(
                    table_name="customers",
                    columns={
                        "customer_id": ColumnProfile(name="customer_id", data_type="BIGINT", is_primary_key=True),
                        "customer_name": ColumnProfile(name="customer_name", data_type="VARCHAR")
                    }
                )
            }
        )
        self.dm.register_domain(ecommerce_config)
        self.assertIsNotNone(ecommerce_config)

        res = self.generator.generate_domain_dbt(ecommerce_config, run_compile=False)

        # 1. Kiểm tra kết quả trả về
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["domain_id"], "ecommerce")
        self.assertGreaterEqual(len(res["staging_models"]), 2)
        self.assertGreaterEqual(len(res["marts_models"]), 1)
        self.assertGreater(res["metrics_count"], 0)

        # 2. Kiểm tra file vật lý được tạo trong infra/dbt
        stg_path = os.path.join(self.generator.staging_dir, "ecommerce", "stg_orders.sql")
        marts_path = os.path.join(self.generator.marts_dir, "ecommerce", "fct_orders_monthly_summary.sql")
        marts_yml = os.path.join(self.generator.marts_dir, "ecommerce", "marts.yml")

        self.assertTrue(os.path.exists(stg_path))
        self.assertTrue(os.path.exists(marts_path))
        self.assertTrue(os.path.exists(marts_yml))

        # 3. Kiểm tra sources.yml đã được sinh với schema ecommerce
        sources_path = os.path.join(self.generator.staging_dir, "ecommerce", "sources.yml")
        with open(sources_path, "r", encoding="utf-8") as f:
            sources_content = f.read()
        self.assertIn("schema: ecommerce", sources_content)

        # 4. Kiểm tra đồng bộ vào DomainManager
        updated_domain = self.dm.get_domain("ecommerce")
        self.assertIsNotNone(updated_domain)
        # Các metrics tự sinh từ dbt đã được nạp vào domain
        self.assertGreater(len(updated_domain.metrics), 0)


if __name__ == "__main__":
    unittest.main()
