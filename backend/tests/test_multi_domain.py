import os
import sys
import unittest
from typing import Any, List, Dict

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.domain_manager import DomainManager
from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile, RelationshipProfile
from app.rag.profiling_graph import BilingualDataProfilingGraph


class MockEmbedding:
    """Mock embedding function trả về vector cố định để test nhanh không phụ thuộc network."""
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Any) -> Any:
        return [[0.0] * 128 for _ in input]


class TestMultiDomainIntegration(unittest.TestCase):
    """
    Bộ kiểm thử tích hợp Đa Domain Toàn diện (E-commerce, Healthcare, Finance).
    Kiểm tra đăng ký dynamic domains, định tuyến câu hỏi và suy luận phép JOIN Steiner Tree.
    """

    @classmethod
    def setUpClass(cls):
        cls.dm = DomainManager()
        cls.dm.reset()

        # Tạo dynamic domain Ecommerce
        cls.ecom_domain = DomainConfig(
            domain_id="ecommerce",
            display_name="Thương Mại Điện Tử",
            description="Dữ liệu đơn hàng, sản phẩm và khách hàng",
            domain_keywords=["đơn hàng", "sản phẩm", "doanh thu", "khách hàng", "hủy đơn", "thanh toán", "order", "gmv"],
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "total_amount": ColumnProfile(name="total_amount", data_type="DOUBLE")
                    },
                    primary_key=["id"]
                ),
                "order_items": TableProfile(
                    table_name="order_items",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "order_id": ColumnProfile(name="order_id", data_type="BIGINT"),
                        "product_id": ColumnProfile(name="product_id", data_type="BIGINT")
                    },
                    primary_key=["id"]
                ),
                "products": TableProfile(
                    table_name="products",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "name": ColumnProfile(name="name", data_type="VARCHAR")
                    },
                    primary_key=["id"]
                )
            },
            relationships=[
                RelationshipProfile(
                    from_table="order_items",
                    from_column="order_id",
                    to_table="orders",
                    to_column="id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="order_items.order_id = orders.id"
                ),
                RelationshipProfile(
                    from_table="order_items",
                    from_column="product_id",
                    to_table="products",
                    to_column="id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="order_items.product_id = products.id"
                )
            ],
            metrics={
                "gmv": MetricProfile(
                    name="gmv",
                    metric_name="gmv",
                    sql_expression="SUM(total_amount)",
                    vn_terms=["gmv", "doanh thu"]
                )
            }
        )

        # Tạo dynamic domain Healthcare
        cls.health_domain = DomainConfig(
            domain_id="healthcare",
            display_name="Y Tế & Bệnh Viện",
            description="Dữ liệu bệnh nhân, chẩn đoán và hồ sơ bệnh án",
            domain_keywords=["bệnh nhân", "bác sĩ", "chẩn đoán", "bệnh án", "khám bệnh", "nằm viện", "toa thuốc"],
            tables={
                "patients": TableProfile(
                    table_name="patients",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "name": ColumnProfile(name="name", data_type="VARCHAR")
                    },
                    primary_key=["id"]
                ),
                "encounters": TableProfile(
                    table_name="encounters",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "patient_id": ColumnProfile(name="patient_id", data_type="BIGINT")
                    },
                    primary_key=["id"]
                ),
                "diagnoses": TableProfile(
                    table_name="diagnoses",
                    columns={
                        "id": ColumnProfile(name="id", data_type="BIGINT", is_primary_key=True),
                        "encounter_id": ColumnProfile(name="encounter_id", data_type="BIGINT"),
                        "disease_name": ColumnProfile(name="disease_name", data_type="VARCHAR")
                    },
                    primary_key=["id"]
                )
            },
            relationships=[
                RelationshipProfile(
                    from_table="encounters",
                    from_column="patient_id",
                    to_table="patients",
                    to_column="id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="encounters.patient_id = patients.id"
                ),
                RelationshipProfile(
                    from_table="diagnoses",
                    from_column="encounter_id",
                    to_table="encounters",
                    to_column="id",
                    relationship_type="MANY_TO_ONE",
                    join_condition="diagnoses.encounter_id = encounters.id"
                )
            ],
            metrics={
                "avg_stay": MetricProfile(
                    name="avg_stay",
                    metric_name="avg_stay",
                    sql_expression="AVG(stay_days)",
                    vn_terms=["thời gian nằm viện"]
                )
            }
        )

        cls.dm.register_domain(cls.ecom_domain)
        cls.dm.register_domain(cls.health_domain)

    def test_domain_manager_dynamic_registry(self):
        """Kiểm tra DomainManager quản trị thành công các dynamic domain."""
        domains = self.dm.list_domains()
        self.assertIn("ecommerce", domains, "Phải nạp thành công domain 'ecommerce'")
        self.assertIn("healthcare", domains, "Phải nạp thành công domain 'healthcare'")

        ecom = self.dm.get_domain("ecommerce")
        self.assertEqual(len(ecom.tables), 3)
        self.assertEqual(len(ecom.relationships), 2)
        self.assertIn("gmv", ecom.metrics)

    def test_domain_router_intent_classification(self):
        """Kiểm tra Domain Router tự động phân loại đúng câu hỏi người dùng vào domain mục tiêu."""
        test_cases = [
            # 1. Thương Mại Điện Tử
            ("Có bao nhiêu đơn hàng bị hủy trong tháng trước và tổng doanh thu gmv là bao nhiêu?", "ecommerce"),
            ("Doanh thu bán hàng và số lượng sản phẩm theo ngành hàng tháng này", "ecommerce"),
            ("Top 10 khách hàng có giá trị giỏ hàng thanh toán cao nhất", "ecommerce"),

            # 2. Y Tế & Bệnh Viện
            ("Báo cáo thời gian nằm viện trung bình của bệnh nhân điều trị nội trú", "healthcare"),
            ("Top 5 chẩn đoán bệnh phổ biến nhất tại khoa tim mạch tháng này", "healthcare"),
            ("Số lượng bệnh nhân tiếp nhận khám và kết quả xét nghiệm", "healthcare"),
        ]

        for query, expected_domain in test_cases:
            detected = self.dm.detect_domain(query)
            self.assertEqual(
                detected,
                expected_domain,
                f"Router phân loại sai câu hỏi: '{query}'. Kỳ vọng: {expected_domain}, Thực tế: {detected}"
            )

    def test_ecommerce_steiner_tree_join_inference(self):
        """Kiểm tra Steiner Tree suy luận đúng chuỗi JOIN 3 bảng trong domain E-commerce."""
        profiler = BilingualDataProfilingGraph(
            domain_config=self.ecom_domain,
            embedding_function=MockEmbedding()
        )

        # Yêu cầu dữ liệu từ bảng orders (doanh thu) và products (danh mục)
        # Steiner Tree phải tự động tìm ra bảng order_items làm cầu nối
        tables, join_clauses, warnings = profiler.infer_join_paths({"orders", "products"})

        self.assertIn("orders", tables)
        self.assertIn("products", tables)
        self.assertIn("order_items", tables, "Phải tự động chèn bảng cầu nối order_items")
        self.assertEqual(len(join_clauses), 2)

        full_join = " ".join(join_clauses)
        self.assertIn("order_items.order_id = orders.id", full_join)
        self.assertIn("order_items.product_id = products.id", full_join)

    def test_healthcare_steiner_tree_join_inference(self):
        """Kiểm tra Steiner Tree suy luận đúng chuỗi JOIN 3 bảng trong domain Healthcare."""
        profiler = BilingualDataProfilingGraph(
            domain_config=self.health_domain,
            embedding_function=MockEmbedding()
        )

        # Yêu cầu dữ liệu từ bảng patients (giới tính nữ) và diagnoses (tên bệnh)
        # Steiner Tree phải tự động tìm ra bảng encounters làm cầu nối
        tables, join_clauses, warnings = profiler.infer_join_paths({"patients", "diagnoses"})

        self.assertIn("patients", tables)
        self.assertIn("diagnoses", tables)
        self.assertIn("encounters", tables, "Phải tự động chèn bảng cầu nối encounters")
        self.assertEqual(len(join_clauses), 2)

        full_join = " ".join(join_clauses)
        self.assertIn("encounters.patient_id = patients.id", full_join)
        self.assertIn("diagnoses.encounter_id = encounters.id", full_join)


if __name__ == "__main__":
    unittest.main()
