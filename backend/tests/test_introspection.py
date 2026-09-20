import os
import sys
import shutil
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.introspection import DatabaseIntrospector
from app.schemas.domain import TableProfile, ColumnProfile, DomainConfig


class TestDatabaseIntrospection(unittest.TestCase):
    """Kiểm thử DatabaseIntrospector tự động khám phá và xuất cấu hình YAML."""

    def setUp(self):
        self.introspector = DatabaseIntrospector()
        self.test_output_dir = os.path.join(backend_dir, "app", "domains", "temp_introspect_test")

    def tearDown(self):
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir, ignore_errors=True)

    def test_infer_relationships_by_naming(self):
        # Giả lập 2 bảng: users và orders
        tables_dict = {
            "users": TableProfile(
                table_name="users",
                vn_name="Người dùng",
                primary_key=["id"],
                columns={
                    "id": ColumnProfile(name="id", vn_name="Mã người dùng", data_type="BIGINT", description="PK", is_primary_key=True),
                    "username": ColumnProfile(name="username", vn_name="Tên đăng nhập", data_type="VARCHAR(50)", description="Username")
                }
            ),
            "orders": TableProfile(
                table_name="orders",
                vn_name="Đơn hàng",
                primary_key=["id"],
                columns={
                    "id": ColumnProfile(name="id", vn_name="Mã đơn", data_type="BIGINT", description="PK", is_primary_key=True),
                    "user_id": ColumnProfile(name="user_id", vn_name="Người mua", data_type="BIGINT", description="FK"),
                    "amount": ColumnProfile(name="amount", vn_name="Số tiền", data_type="DOUBLE", description="Tiền")
                }
            )
        }

        rels = self.introspector.infer_relationships_by_naming(tables_dict)
        self.assertEqual(len(rels), 1, "Phải suy luận được đúng 1 quan hệ từ orders.user_id -> users.id")

        rel = rels[0]
        self.assertEqual(rel.from_table, "orders")
        self.assertEqual(rel.from_column, "user_id")
        self.assertEqual(rel.to_table, "users")
        self.assertEqual(rel.to_column, "id")
        self.assertEqual(rel.cardinality, "N:1")

    def test_export_and_reload_domain(self):
        # Tạo mock domain
        domain = DomainConfig(
            domain_id="temp_introspect_test",
            display_name="Domain Tự Động Quét",
            description="Domain test tự động sinh từ introspection",
            domain_keywords=["test", "auto"],
            tables={
                "products": TableProfile(
                    table_name="products",
                    vn_name="Sản phẩm",
                    columns={
                        "id": ColumnProfile(name="id", vn_name="Mã SP", data_type="BIGINT", description="PK", is_primary_key=True),
                        "price": ColumnProfile(name="price", vn_name="Giá", data_type="DOUBLE", description="Giá bán")
                    }
                )
            }
        )

        # Xuất ra thư mục YAML
        self.introspector.export_to_yaml_folder(domain, self.test_output_dir)

        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "domain.yaml")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "schema.yaml")))
        self.assertTrue(os.path.exists(os.path.join(self.test_output_dir, "metrics.yaml")))

        # Nạp lại bằng DomainConfig.load_from_folder
        reloaded = DomainConfig.load_from_folder(self.test_output_dir)
        self.assertEqual(reloaded.domain_id, "temp_introspect_test")
        self.assertIn("products", reloaded.tables)
        self.assertEqual(len(reloaded.tables["products"].columns), 2)


if __name__ == "__main__":
    unittest.main()
