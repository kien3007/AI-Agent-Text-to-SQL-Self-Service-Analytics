import os
import sys
import unittest
from typing import Any

# Đảm bảo import app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile, RelationshipProfile
from app.rag.profiling_graph import BilingualDataProfilingGraph


class MockEmbedding:
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Any) -> Any:
        return [[0.0] * 128 for _ in input]


class TestBilingualDataProfilingGraph(unittest.TestCase):
    """Kiểm thử Semantic Schema Linking & Profiling Graph linh hoạt cho CSDL bất kỳ."""

    @classmethod
    def setUpClass(cls):
        # Thiết lập dynamic domain E-commerce/Retail để kiểm thử schema linking
        cls.dynamic_domain = DomainConfig(
            domain_id="retail_store",
            display_name="Cửa Hàng Bán Lẻ",
            description="Dữ liệu đơn hàng, doanh thu và sản phẩm",
            domain_keywords=["đơn hàng", "sản phẩm", "doanh thu", "khách hàng", "giá"],
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    description="Bảng thông tin đơn hàng",
                    columns={
                        "order_id": ColumnProfile(
                            name="order_id",
                            data_type="BIGINT",
                            is_primary_key=True,
                            vn_name="Mã đơn hàng"
                        ),
                        "customer_id": ColumnProfile(
                            name="customer_id",
                            data_type="BIGINT",
                            vn_name="Mã khách hàng"
                        ),
                        "total_amount": ColumnProfile(
                            name="total_amount",
                            data_type="DOUBLE",
                            vn_name="Tổng tiền hóa đơn",
                            synonyms=["doanh thu", "giá trị đơn", "tổng tiền", "tiền"]
                        ),
                        "order_status": ColumnProfile(
                            name="order_status",
                            data_type="VARCHAR",
                            vn_name="Trạng thái đơn",
                            synonyms=["trạng thái", "hoàn tất", "tình trạng", "status"],
                            sample_values=["COMPLETED", "CANCELLED", "PENDING"]
                        ),
                        "created_at": ColumnProfile(
                            name="created_at",
                            data_type="TIMESTAMP",
                            vn_name="Ngày đặt hàng",
                            is_partition_or_dist=True
                        )
                    },
                    primary_key=["order_id"]
                ),
                "customers": TableProfile(
                    table_name="customers",
                    description="Bảng thông tin khách hàng",
                    columns={
                        "customer_id": ColumnProfile(name="customer_id", data_type="BIGINT", is_primary_key=True),
                        "city": ColumnProfile(name="city", data_type="VARCHAR", vn_name="Thành phố", sample_values=["Hà Nội", "Hồ Chí Minh", "Đà Nẵng"])
                    },
                    primary_key=["customer_id"]
                )
            },
            relationships=[
                RelationshipProfile(
                    from_table="orders",
                    from_column="customer_id",
                    to_table="customers",
                    to_column="customer_id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="orders.customer_id = customers.customer_id"
                )
            ],
            metrics={
                "total_sales": MetricProfile(
                    name="total_sales",
                    metric_name="total_sales",
                    display_name="Tổng Doanh Số",
                    table_name="orders",
                    sql_expression="SUM(total_amount)",
                    vn_terms=["tổng doanh số", "tổng doanh thu", "doanh thu bán hàng"]
                )
            }
        )

        cls.profiler = BilingualDataProfilingGraph(
            domain_config=cls.dynamic_domain,
            embedding_function=MockEmbedding()
        )

    def test_link_schema_columns(self):
        """Kiểm tra trích xuất đúng cột liên quan từ câu hỏi phân tích."""
        query = "Tổng tiền các đơn hàng hoàn tất tại Hà Nội"
        ctx = self.profiler.link_schema(query)

        col_names = [c.name for c in ctx.relevant_columns]
        self.assertIn("total_amount", col_names)
        self.assertIn("order_status", col_names)

    def test_link_schema_metrics(self):
        """Kiểm tra phát hiện đúng metric định nghĩa sẵn."""
        query = "Xem tổng doanh thu bán hàng tháng trước"
        ctx = self.profiler.link_schema(query)

        metric_names = [m.name for m in ctx.suggested_metrics]
        self.assertIn("total_sales", metric_names)

    def test_multi_table_join_inference(self):
        """Kiểm tra tự động suy luận join giữa bảng orders và customers."""
        tables, joins, warnings = self.profiler.infer_join_paths({"orders", "customers"})
        self.assertIn("orders", tables)
        self.assertIn("customers", tables)
        self.assertEqual(len(joins), 1)
        self.assertIn("orders.customer_id = customers.customer_id", joins[0])


if __name__ == "__main__":
    unittest.main()
