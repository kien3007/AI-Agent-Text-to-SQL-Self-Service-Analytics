import os
import sys
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.domain_manager import DomainManager
from app.rag.profiling_graph import BilingualDataProfilingGraph
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings


class MockEmbedding(EmbeddingFunction):
    """Mock embedding function trả về vector cố định để test nhanh không phụ thuộc network."""
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.0] * 128 for _ in input]


class TestMultiDomainIntegration(unittest.TestCase):
    """
    Bộ kiểm thử tích hợp Đa Domain Toàn diện (Real Estate, E-commerce, Healthcare).
    Kiểm tra tự động phát hiện domain, định tuyến câu hỏi và suy luận phép JOIN Steiner Tree.
    """

    @classmethod
    def setUpClass(cls):
        cls.dm = DomainManager()
        # Đảm bảo nạp lại toàn bộ các domain trong thư mục domains/
        cls.dm.reload_domains()

    def test_domain_manager_auto_discovery(self):
        """Kiểm tra DomainManager tự động phát hiện và nạp cả 3 domain YAML."""
        domains = self.dm.list_domains()
        self.assertIn("real_estate", domains, "Phải nạp thành công domain 'real_estate'")
        self.assertIn("ecommerce", domains, "Phải nạp thành công domain 'ecommerce'")
        self.assertIn("healthcare", domains, "Phải nạp thành công domain 'healthcare'")

        # Kiểm tra chi tiết domain ecommerce
        ecom = self.dm.get_domain("ecommerce")
        self.assertEqual(len(ecom.tables), 5, "Domain ecommerce phải có đủ 5 bảng")
        self.assertEqual(len(ecom.relationships), 4, "Domain ecommerce phải có 4 quan hệ khóa ngoại")
        self.assertIn("gmv", ecom.metrics)

        # Kiểm tra chi tiết domain healthcare
        health = self.dm.get_domain("healthcare")
        self.assertEqual(len(health.tables), 5, "Domain healthcare phải có đủ 5 bảng")
        self.assertEqual(len(health.relationships), 4, "Domain healthcare phải có 4 quan hệ khóa ngoại")
        self.assertIn("avg_length_of_stay", health.metrics)

    def test_domain_router_intent_classification(self):
        """Kiểm tra Domain Router tự động phân loại đúng câu hỏi người dùng vào domain mục tiêu."""
        test_cases = [
            # 1. Bất Động Sản
            ("Tìm mua chung cư 2PN Cầu Giấy dưới 3 tỷ", "real_estate"),
            ("Giá đất thổ cư Thủ Đức sổ đỏ phân khúc bình dân", "real_estate"),
            ("Nhà hẻm xe hơi Bình Thạnh hướng đông nam", "real_estate"),

            # 2. Thương Mại Điện Tử
            ("Có bao nhiêu đơn hàng bị hủy trong tháng trước và tổng doanh thu gmv là bao nhiêu?", "ecommerce"),
            ("Doanh thu bán hàng và số lượng sản phẩm theo ngành hàng tháng này", "ecommerce"),
            ("Top 10 khách hàng có giá trị giỏ hàng thanh toán cao nhất", "ecommerce"),

            # 3. Y Tế & Bệnh Viện
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
        ecom_domain = self.dm.get_domain("ecommerce")
        profiler = BilingualDataProfilingGraph(
            domain_config=ecom_domain,
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
        health_domain = self.dm.get_domain("healthcare")
        profiler = BilingualDataProfilingGraph(
            domain_config=health_domain,
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
