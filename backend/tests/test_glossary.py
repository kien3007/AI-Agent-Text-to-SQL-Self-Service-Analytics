import os
import sys
import unittest

# Đảm bảo import app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.glossary import VietnameseBusinessGlossary

class TestVietnameseBusinessGlossary(unittest.TestCase):
    def setUp(self):
        self.glossary = VietnameseBusinessGlossary()

    def test_apartment_cau_giay_under_3_billion(self):
        query = "chung cư 2PN Cầu Giấy dưới 3 tỷ"
        res = self.glossary.normalize(query)
        intent = res.intent

        self.assertEqual(intent.property_type, "Căn hộ chung cư")
        self.assertEqual(intent.district, "Cầu Giấy")
        self.assertEqual(intent.province, "Hà Nội") # Tự suy luận từ Cầu Giấy
        self.assertEqual(intent.bedroom_count, 2)
        self.assertEqual(intent.max_price, 3_000_000_000)

    def test_land_thu_duc_cheap(self):
        query = "đất thổ cư Thủ Đức giá rẻ"
        res = self.glossary.normalize(query)
        intent = res.intent

        self.assertEqual(intent.property_type, "Đất")
        self.assertEqual(intent.district, "Thủ Đức")
        self.assertEqual(intent.province, "Hồ Chí Minh") # Tự suy luận từ Thủ Đức
        self.assertEqual(intent.order_by, "price ASC")

    def test_relative_time_resolution(self):
        query = "nhà hẻm Bình Thạnh tháng trước"
        res = self.glossary.normalize(query)
        intent = res.intent

        self.assertEqual(intent.property_type, "Nhà")
        self.assertEqual(intent.district, "Bình Thạnh")
        self.assertIsNotNone(intent.time_range)
        self.assertEqual(intent.time_range[0], "tháng trước")

    def test_quarter_resolution(self):
        query = "biệt thự liền kề ĐN trên 15 tỷ quý trước"
        res = self.glossary.normalize(query)
        intent = res.intent

        self.assertEqual(intent.property_type, "Biệt thự/Nhà liền kề")
        self.assertEqual(intent.province, "Đà Nẵng")
        self.assertEqual(intent.min_price, 15_000_000_000)
        self.assertIsNotNone(intent.time_range)
        self.assertEqual(intent.time_range[0], "quý trước")

    def test_price_range_and_area(self):
        query = "căn hộ từ 2 đến 3 tỷ diện tích từ 60 đến 80 m2"
        res = self.glossary.normalize(query)
        intent = res.intent

        self.assertEqual(intent.property_type, "Căn hộ chung cư")
        self.assertEqual(intent.min_price, 2_000_000_000)
        self.assertEqual(intent.max_price, 3_000_000_000)
        self.assertEqual(intent.min_area, 60.0)
        self.assertEqual(intent.max_area, 80.0)

if __name__ == "__main__":
    unittest.main()
