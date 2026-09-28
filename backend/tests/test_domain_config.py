import os
import sys
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile, RelationshipProfile


class TestDomainConfig(unittest.TestCase):
    """Kiểm thử nạp và xác thực cấu hình Domain từ YAML."""

    def test_load_real_estate_domain(self):
        domain_path = os.path.join(backend_dir, "domains", "real_estate")
        if not os.path.exists(domain_path):
            domain_path = os.path.join(backend_dir, "app", "domains", "real_estate")
        self.assertTrue(os.path.exists(domain_path), f"Thư mục không tồn tại: {domain_path}")

        domain = DomainConfig.load_from_folder(domain_path)
        
        # 1. Kiểm tra metadata domain
        self.assertEqual(domain.domain_id, "real_estate")
        self.assertEqual(domain.display_name, "Bất Động Sản Việt Nam")
        self.assertGreater(len(domain.domain_keywords), 5)
        self.assertIn("căn hộ", domain.domain_keywords)

        # 2. Kiểm tra bảng và cột
        self.assertIn("real_estate_listings", domain.tables)
        re_table = domain.tables["real_estate_listings"]
        self.assertEqual(re_table.table_name, "real_estate_listings")
        self.assertEqual(len(re_table.columns), 19, "Bảng real_estate_listings phải có đủ 19 cột")

        # Kiểm tra chi tiết một số cột then chốt
        col_price = re_table.columns.get("price")
        self.assertIsNotNone(col_price)
        self.assertEqual(col_price.data_type, "DOUBLE")
        self.assertEqual(col_price.vn_name, "Giá niêm yết (VNĐ)")
        self.assertIn("giá bán", col_price.synonyms)

        col_published = re_table.columns.get("published_at")
        self.assertIsNotNone(col_published)
        self.assertTrue(col_published.is_partition_or_dist)

        col_province = re_table.columns.get("province_name")
        self.assertIsNotNone(col_province)
        self.assertTrue(col_province.is_partition_or_dist)

        # 3. Kiểm tra Metrics
        self.assertIn("avg_price_per_sqm", domain.metrics)
        m_avg_sqm = domain.metrics["avg_price_per_sqm"]
        self.assertEqual(m_avg_sqm.sql_expression, "ROUND(AVG(price / NULLIF(area, 0)), 0)")
        self.assertIn("giá trung bình m2", m_avg_sqm.vn_terms)

        self.assertIn("listing_count", domain.metrics)
        self.assertEqual(domain.metrics["listing_count"].sql_expression, "COUNT(*)")

        # 4. Kiểm tra Segments
        self.assertIn("luxury", domain.segments)
        self.assertEqual(domain.segments["luxury"].condition, "price >= 10000000000")

        self.assertIn("affordable", domain.segments)
        self.assertEqual(domain.segments["affordable"].condition, "price < 3000000000")

        # 5. Kiểm tra Synonyms
        self.assertIn("2pn", domain.synonyms)
        self.assertEqual(domain.synonyms["2pn"], "2 phòng ngủ")


if __name__ == "__main__":
    unittest.main()
