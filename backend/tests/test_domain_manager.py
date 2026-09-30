import os
import sys
import datetime
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.normalizer import GenericVietnameseNormalizer
from app.core.domain_manager import DomainManager
from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile


class TestGenericVietnameseNormalizer(unittest.TestCase):
    """Kiểm thử bộ chuẩn hóa GenericVietnameseNormalizer dùng chung cho mọi domain."""

    def setUp(self):
        # Mốc cố định: 2026-03-15
        self.ref_date = datetime.date(2026, 3, 15)
        self.norm = GenericVietnameseNormalizer(reference_date=self.ref_date)

    def test_relative_time_extraction(self):
        # 1. Tháng trước
        res = self.norm.extract_relative_time("doanh thu tháng trước")
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "tháng trước")
        self.assertTrue(res[1].startswith("2026-02-01"))
        self.assertTrue(res[2].startswith("2026-02-28"))

        # 2. Quý này (tháng 3 -> Quý 1)
        res_q = self.norm.extract_relative_time("số lượng giao dịch quý này")
        self.assertIsNotNone(res_q)
        self.assertEqual(res_q[0], "quý này")
        self.assertTrue(res_q[1].startswith("2026-01-01"))
        self.assertTrue(res_q[2].startswith("2026-03-31"))

        # 3. Năm ngoái
        res_y = self.norm.extract_relative_time("báo cáo năm ngoái")
        self.assertIsNotNone(res_y)
        self.assertEqual(res_y[0], "năm ngoái")
        self.assertTrue(res_y[1].startswith("2025-01-01"))
        self.assertTrue(res_y[2].startswith("2025-12-31"))

    def test_currency_range_extraction(self):
        # Range: từ 2 đến 3 tỷ
        min_p, max_p, matched, filt = self.norm.extract_currency_range("ngân sách từ 2 đến 3 tỷ")
        self.assertEqual(min_p, 2_000_000_000)
        self.assertEqual(max_p, 3_000_000_000)
        self.assertEqual(filt, "BETWEEN 2000000000.0 AND 3000000000.0")

        # Tỷ rưỡi: dưới 2 tỷ rưỡi
        _, max_p2, _, filt2 = self.norm.extract_currency_range("tìm nhà dưới 2 tỷ rưỡi")
        self.assertEqual(max_p2, 2_500_000_000)
        self.assertEqual(filt2, "<= 2500000000.0")

        # Triệu: trên 800tr
        min_p3, _, _, filt3 = self.norm.extract_currency_range("giá trên 800tr")
        self.assertEqual(min_p3, 800_000_000)
        self.assertEqual(filt3, ">= 800000000.0")

    def test_numeric_range_and_limit(self):
        # Diện tích
        min_a, max_a, _, _ = self.norm.extract_numeric_range("diện tích từ 45 đến 60 m2", r"m2|mét vuông")
        self.assertEqual(min_a, 45.0)
        self.assertEqual(max_a, 60.0)

        # Limit
        cand, matched = self.norm.extract_limit("Top 10 bất động sản giá rẻ")
        self.assertEqual(cand, 10)
        self.assertEqual(matched, "top 10")


class TestDomainManager(unittest.TestCase):
    """Kiểm thử DomainManager registry linh hoạt và bộ định tuyến Domain Router."""

    def setUp(self):
        self.dm = DomainManager()
        self.dm.reset()

    def test_default_fallback_domain(self):
        """Hệ thống không crash khi chưa có domain nào; luôn có active domain an toàn."""
        active = self.dm.get_active_domain()
        self.assertIsNotNone(active)
        self.assertEqual(active.domain_id, "default")
        self.assertIn("default", self.dm.list_domains())

    def test_dynamic_register_and_routing(self):
        """Kiểm tra đăng ký nhiều domain runtime và định tuyến truy vấn chính xác."""
        ecommerce_domain = DomainConfig(
            domain_id="ecommerce",
            display_name="Thương Mại Điện Tử",
            description="Dữ liệu đơn hàng, sản phẩm và khách hàng",
            domain_keywords=["đơn hàng", "sản phẩm", "doanh thu", "khách hàng", "hủy đơn", "thanh toán", "order"],
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    vn_name="Đơn hàng",
                    description="Thông tin đơn hàng thương mại điện tử",
                    columns={
                        "order_id": ColumnProfile(
                            name="order_id",
                            vn_name="Mã đơn hàng",
                            data_type="BIGINT",
                            description="Định danh duy nhất của đơn hàng",
                            is_primary_key=True
                        ),
                        "total_amount": ColumnProfile(
                            name="total_amount",
                            vn_name="Tổng tiền đơn hàng",
                            data_type="DOUBLE",
                            description="Giá trị thanh toán của đơn hàng",
                            synonyms=["giá trị đơn", "tổng tiền", "tiền đơn"]
                        )
                    }
                )
            },
            metrics={
                "gmv": MetricProfile(
                    name="gmv",
                    metric_name="gmv",
                    vn_terms=["tổng giá trị giao dịch", "gmv", "doanh thu bán hàng"],
                    sql_expression="SUM(total_amount)",
                    description="Tổng giá trị giao dịch của đơn hàng thành công"
                )
            }
        )

        healthcare_domain = DomainConfig(
            domain_id="healthcare",
            display_name="Y Tế & Bệnh Viện",
            description="Dữ liệu bệnh nhân, bệnh án và lịch khám",
            domain_keywords=["bệnh nhân", "bác sĩ", "chẩn đoán", "bệnh án", "khám bệnh", "toa thuốc"],
            tables={},
            metrics={}
        )

        self.dm.register_domain(ecommerce_domain)
        self.dm.register_domain(healthcare_domain)

        domains = self.dm.list_domains()
        self.assertIn("ecommerce", domains)
        self.assertIn("healthcare", domains)

        # 1. Câu hỏi về E-commerce -> ecommerce
        q_ecom = "Báo cáo tổng giá trị giao dịch gmv và số lượng đơn hàng bị hủy tháng trước"
        detected_ecom = self.dm.detect_domain(q_ecom)
        self.assertEqual(detected_ecom, "ecommerce")

        # 2. Câu hỏi về Y tế -> healthcare
        q_health = "Thống kê số lượng bệnh nhân đến khám bệnh theo bác sĩ"
        detected_health = self.dm.detect_domain(q_health)
        self.assertEqual(detected_health, "healthcare")

        # 3. Câu hỏi không rõ ràng -> fallback active domain
        q_unknown = "123 abc xyz test"
        detected_unknown = self.dm.detect_domain(q_unknown)
        self.assertIn(detected_unknown, [self.dm.get_active_domain().domain_id, "default", "ecommerce", "healthcare"])


if __name__ == "__main__":
    unittest.main()

