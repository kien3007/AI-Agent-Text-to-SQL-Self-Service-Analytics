import os
import sys
import shutil
import tempfile
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile, RelationshipProfile
from app.core.introspection import DatabaseIntrospector


class TestDomainConfig(unittest.TestCase):
    """Kiểm thử cấu hình Domain linh hoạt: khởi tạo, serialize/deserialize, export/reload YAML."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dynamic_domain_creation_and_yaml_roundtrip(self):
        """Kiểm tra tạo DomainConfig động cho CSDL bất kỳ và nạp/ghi YAML vòng lặp (roundtrip)."""
        domain = DomainConfig(
            domain_id="finance_db",
            display_name="Hệ Thống Tài Chính & Giao Dịch",
            description="Domain tài chính quản lý hóa đơn và thanh toán",
            domain_keywords=["tài chính", "hóa đơn", "giao dịch", "thanh toán", "doanh thu"],
            tables={
                "invoices": TableProfile(
                    table_name="invoices",
                    description="Bảng quản lý hóa đơn bán hàng",
                    columns={
                        "invoice_id": ColumnProfile(
                            name="invoice_id",
                            data_type="BIGINT",
                            is_primary_key=True,
                            vn_name="Mã hóa đơn"
                        ),
                        "total_amount": ColumnProfile(
                            name="total_amount",
                            data_type="DOUBLE",
                            vn_name="Tổng số tiền",
                            synonyms=["doanh số", "số tiền", "tổng tiền"]
                        ),
                        "created_at": ColumnProfile(
                            name="created_at",
                            data_type="TIMESTAMP",
                            vn_name="Thời gian tạo hóa đơn"
                        )
                    },
                    primary_key=["invoice_id"]
                ),
                "payments": TableProfile(
                    table_name="payments",
                    description="Bảng ghi nhận giao dịch thanh toán",
                    columns={
                        "payment_id": ColumnProfile(name="payment_id", data_type="BIGINT", is_primary_key=True),
                        "invoice_id": ColumnProfile(name="invoice_id", data_type="BIGINT"),
                        "status": ColumnProfile(name="status", data_type="VARCHAR", vn_name="Trạng thái", sample_values=["SUCCESS", "FAILED"])
                    },
                    primary_key=["payment_id"]
                )
            },
            relationships=[
                RelationshipProfile(
                    from_table="payments",
                    from_column="invoice_id",
                    to_table="invoices",
                    to_column="invoice_id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="payments.invoice_id = invoices.invoice_id"
                )
            ],
            metrics={
                "total_revenue": MetricProfile(
                    name="total_revenue",
                    metric_name="total_revenue",
                    display_name="Tổng Doanh Thu",
                    table_name="invoices",
                    sql_expression="SUM(total_amount)",
                    vn_terms=["tổng doanh thu", "doanh số"]
                )
            }
        )

        # 1. Kiểm tra thuộc tính in-memory
        self.assertEqual(domain.domain_id, "finance_db")
        self.assertEqual(len(domain.tables), 2)
        self.assertIn("total_revenue", domain.metrics)
        self.assertEqual(domain.metrics["total_revenue"].sql_expression, "SUM(total_amount)")
        self.assertEqual(len(domain.relationships), 1)

        # 2. Export ra YAML folder bằng DatabaseIntrospector
        introspector = DatabaseIntrospector()
        domain_folder = os.path.join(self.temp_dir, "finance_db")
        introspector.export_to_yaml_folder(domain, domain_folder)

        self.assertTrue(os.path.exists(os.path.join(domain_folder, "domain.yaml")))
        self.assertTrue(os.path.exists(os.path.join(domain_folder, "schema.yaml")))
        self.assertTrue(os.path.exists(os.path.join(domain_folder, "metrics.yaml")))

        # 3. Reload từ YAML folder
        reloaded = DomainConfig.load_from_folder(domain_folder)
        self.assertEqual(reloaded.domain_id, "finance_db")
        self.assertEqual(reloaded.display_name, "Hệ Thống Tài Chính & Giao Dịch")
        self.assertIn("invoices", reloaded.tables)
        self.assertIn("payments", reloaded.tables)
        self.assertEqual(reloaded.tables["invoices"].columns["total_amount"].vn_name, "Tổng số tiền")
        self.assertIn("total_revenue", reloaded.metrics)
        self.assertEqual(len(reloaded.relationships), 1)
        self.assertEqual(reloaded.relationships[0].from_table, "payments")


if __name__ == "__main__":
    unittest.main()
