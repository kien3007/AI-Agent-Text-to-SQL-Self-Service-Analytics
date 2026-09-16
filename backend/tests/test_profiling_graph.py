import os
import sys
import unittest

# Đảm bảo import app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.rag.profiling_graph import BilingualDataProfilingGraph

class TestBilingualDataProfilingGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chroma_dir = os.path.join(root_dir, "data", "chroma_db")
        cls.profiler = BilingualDataProfilingGraph(chroma_dir=chroma_dir)

    def test_link_schema_cau_giay(self):
        query = "chung cư 2PN Cầu Giấy dưới 3 tỷ"
        ctx = self.profiler.link_schema(query)

        col_names = [c.name for c in ctx.relevant_columns]
        self.assertIn("property_type_name", col_names)
        self.assertIn("district_name", col_names)
        self.assertIn("province_name", col_names) # Suy luận từ Cầu Giấy
        self.assertIn("bedroom_count", col_names)
        self.assertIn("price", col_names)
        self.assertIn("published_at", col_names) # Luôn có partition key

        # Kiểm tra WHERE filters
        filters_str = " ".join(ctx.suggested_filters)
        self.assertIn("property_type_name = 'Căn hộ chung cư'", filters_str)
        self.assertIn("district_name = 'Cầu Giấy'", filters_str)
        self.assertIn("province_name = 'Hà Nội'", filters_str)
        self.assertIn("bedroom_count = 2", filters_str)
        self.assertIn("price <= 3000000000", filters_str)

    def test_link_schema_thu_duc(self):
        query = "đất thổ cư Thủ Đức giá rẻ"
        ctx = self.profiler.link_schema(query)

        col_names = [c.name for c in ctx.relevant_columns]
        self.assertIn("property_type_name", col_names)
        self.assertIn("district_name", col_names)
        self.assertIn("province_name", col_names) # Suy luận từ Thủ Đức

        filters_str = " ".join(ctx.suggested_filters)
        self.assertIn("property_type_name = 'Đất'", filters_str)
        self.assertIn("district_name = 'Thủ Đức'", filters_str)
        self.assertIn("province_name = 'Hồ Chí Minh'", filters_str)
        self.assertEqual(ctx.order_by_clause, "price ASC")

    def test_link_schema_avg_price_sqm(self):
        query = "giá trung bình m2 tại Đà Nẵng tháng trước"
        ctx = self.profiler.link_schema(query)

        col_names = [c.name for c in ctx.relevant_columns]
        self.assertIn("province_name", col_names)
        self.assertIn("price", col_names)
        self.assertIn("area", col_names)
        self.assertIn("published_at", col_names)

        # Kiểm tra có metric avg_price_per_sqm
        metric_names = [m.name for m in ctx.suggested_metrics]
        self.assertIn("avg_price_per_sqm", metric_names)

        # Kiểm tra gợi ý phân vùng
        self.assertTrue(len(ctx.prompt_context) > 100)
        self.assertIn("PARTITION BY RANGE(published_at)", ctx.partition_pruning_hint)

if __name__ == "__main__":
    unittest.main()
