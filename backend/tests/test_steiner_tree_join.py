import os
import sys
import unittest
from typing import Any, List, Dict

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, RelationshipProfile, MetricProfile
from app.rag.profiling_graph import BilingualDataProfilingGraph


class TestSteinerTreeJoinInference(unittest.TestCase):
    """Kiểm thử thuật toán Minimum Steiner Tree suy luận đường dẫn JOIN đa bảng."""

    def setUp(self):
        # Thiết lập Schema E-commerce 4 bảng: customers, orders, order_items, products
        # Schema graph: customers (1) <--- (N) orders (1) <--- (N) order_items (N) ---> (1) products
        self.ecommerce_domain = DomainConfig(
            domain_id="ecommerce_test",
            display_name="Thương Mại Điện Tử Test",
            description="Domain test kiểm thử thuật toán Steiner Tree",
            tables={
                "customers": TableProfile(
                    table_name="customers",
                    vn_name="Khách hàng",
                    primary_key=["id"],
                    columns={
                        "id": ColumnProfile(name="id", vn_name="Mã khách hàng", data_type="BIGINT", description="Khóa chính"),
                        "customer_name": ColumnProfile(name="customer_name", vn_name="Tên khách hàng", data_type="VARCHAR(100)", description="Họ tên")
                    }
                ),
                "orders": TableProfile(
                    table_name="orders",
                    vn_name="Đơn hàng",
                    primary_key=["id"],
                    columns={
                        "id": ColumnProfile(name="id", vn_name="Mã đơn hàng", data_type="BIGINT", description="Khóa chính"),
                        "customer_id": ColumnProfile(name="customer_id", vn_name="Khách hàng", data_type="BIGINT", description="Khóa ngoại tới customers"),
                        "order_date": ColumnProfile(name="order_date", vn_name="Ngày đặt", data_type="DATETIME", description="Thời điểm đặt hàng"),
                        "total_amount": ColumnProfile(name="total_amount", vn_name="Tổng tiền", data_type="DOUBLE", description="Tổng tiền đơn")
                    }
                ),
                "order_items": TableProfile(
                    table_name="order_items",
                    vn_name="Chi tiết đơn hàng",
                    primary_key=["id"],
                    columns={
                        "id": ColumnProfile(name="id", vn_name="Mã dòng", data_type="BIGINT", description="Khóa chính"),
                        "order_id": ColumnProfile(name="order_id", vn_name="Mã đơn hàng", data_type="BIGINT", description="Khóa ngoại tới orders"),
                        "product_id": ColumnProfile(name="product_id", vn_name="Mã sản phẩm", data_type="BIGINT", description="Khóa ngoại tới products"),
                        "quantity": ColumnProfile(name="quantity", vn_name="Số lượng", data_type="INT", description="Số lượng mua"),
                        "unit_price": ColumnProfile(name="unit_price", vn_name="Đơn giá", data_type="DOUBLE", description="Giá mỗi sản phẩm")
                    }
                ),
                "products": TableProfile(
                    table_name="products",
                    vn_name="Sản phẩm",
                    primary_key=["id"],
                    columns={
                        "id": ColumnProfile(name="id", vn_name="Mã sản phẩm", data_type="BIGINT", description="Khóa chính"),
                        "product_name": ColumnProfile(name="product_name", vn_name="Tên sản phẩm", data_type="VARCHAR(200)", description="Tên hàng"),
                        "category_name": ColumnProfile(name="category_name", vn_name="Danh mục", data_type="VARCHAR(100)", description="Ngành hàng")
                    }
                )
            },
            relationships=[
                RelationshipProfile(
                    from_table="orders",
                    from_column="customer_id",
                    to_table="customers",
                    to_column="id",
                    cardinality="N:1",
                    join_type="LEFT",
                    weight=1.0
                ),
                RelationshipProfile(
                    from_table="order_items",
                    from_column="order_id",
                    to_table="orders",
                    to_column="id",
                    cardinality="N:1",
                    join_type="INNER",
                    weight=1.0
                ),
                RelationshipProfile(
                    from_table="order_items",
                    from_column="product_id",
                    to_table="products",
                    to_column="id",
                    cardinality="N:1",
                    join_type="INNER",
                    weight=1.0
                )
            ]
        )

        # Khởi tạo ProfilingGraph với mock embedding rỗng để không tốn tài nguyên tải model
        class MockEmbedding:
            def name(self) -> str:
                return "mock_embedding"

            def __call__(self, input: Any) -> Any:
                return [[0.0] * 128 for _ in input]

        self.profiler = BilingualDataProfilingGraph(
            domain_config=self.ecommerce_domain,
            embedding_function=MockEmbedding()
        )

    def test_single_table_no_join(self):
        # 1 bảng -> Không sinh JOIN
        ordered_tables, join_clauses, warnings = self.profiler.infer_join_paths({"orders"})
        self.assertEqual(ordered_tables, ["orders"])
        self.assertEqual(len(join_clauses), 0)

    def test_two_tables_direct_join(self):
        # 2 bảng có quan hệ trực tiếp (orders và customers)
        ordered_tables, join_clauses, warnings = self.profiler.infer_join_paths({"orders", "customers"})
        self.assertIn("orders", ordered_tables)
        self.assertIn("customers", ordered_tables)
        self.assertEqual(len(join_clauses), 1)

        # Mệnh đề JOIN chuẩn xác
        join_sql = join_clauses[0]
        self.assertTrue(
            "orders.customer_id = customers.id" in join_sql or "customers.id = orders.customer_id" in join_sql,
            f"Mệnh đề JOIN không đúng: {join_sql}"
        )

    def test_bridge_table_auto_discovery(self):
        # Yêu cầu cột từ 'orders' và 'products' (không yêu cầu 'order_items')
        # Thuật toán Steiner Tree PHẢI tự động phát hiện ra 'order_items' làm cầu nối!
        ordered_tables, join_clauses, warnings = self.profiler.infer_join_paths({"orders", "products"})
        
        self.assertIn("orders", ordered_tables)
        self.assertIn("products", ordered_tables)
        self.assertIn("order_items", ordered_tables, "Steiner Tree phải tự động chèn bảng cầu nối order_items")
        self.assertEqual(len(join_clauses), 2, "Cần đúng 2 bước JOIN để kết nối orders -> order_items -> products")

        full_join_sql = " ".join(join_clauses)
        self.assertIn("order_items.order_id = orders.id", full_join_sql)
        self.assertIn("order_items.product_id = products.id", full_join_sql)

    def test_four_tables_steiner_tree(self):
        # Cả 4 bảng tham gia truy vấn
        ordered_tables, join_clauses, warnings = self.profiler.infer_join_paths(
            {"customers", "orders", "order_items", "products"}
        )
        self.assertEqual(len(ordered_tables), 4)
        self.assertEqual(len(join_clauses), 3, "4 bảng kết nối hình cây cần đúng 3 cạnh JOIN")

    def test_link_schema_multi_table_prompt_context(self):
        # Nạp chỉ mục giả lập vào profiler
        self.profiler.index_all(force=True)

        # Truy vấn đa bảng: doanh thu và sản phẩm
        ctx = self.profiler.link_schema("tổng tiền theo danh mục sản phẩm")

        self.assertGreater(len(ctx.selected_tables), 0)
        self.assertTrue(len(ctx.prompt_context) > 50)
        self.assertIn("SCHEMA LIÊN KẾT", ctx.prompt_context)


if __name__ == "__main__":
    unittest.main()
