"""
Unit and Integration Tests for dbt Pipeline, Data Marts, and Semantic Layer Integration.
"""

import os
import sys
import unittest

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

class MockEmbedding(EmbeddingFunction):
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Documents) -> Embeddings:
        return [[0.0] * 1024 for _ in input]


from app.core.dbt_loader import DbtManifestLoader
from app.core.domain_manager import DomainManager
from app.rag.profiling_graph import BilingualDataProfilingGraph


class TestDbtIntegration(unittest.TestCase):
    """Kiểm thử tích hợp dự án dbt và Semantic Layer vào AI Agent."""

    def setUp(self):
        self.loader = DbtManifestLoader()
        self.mock_emb = MockEmbedding()

    def test_dbt_project_files_exist(self):
        """Kiểm tra sự tồn tại của các file cấu hình và models cốt lõi của dbt."""
        dbt_dir = self.loader.dbt_dir
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "dbt_project.yml")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "profiles.yml")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "staging", "stg_real_estate.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "staging", "stg_real_estate.yml")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "fct_real_estate_analytics.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "fct_district_monthly_summary.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "marts.yml")))

    def test_dbt_models_and_metrics_extraction(self):
        """Kiểm tra trích xuất TableProfile và MetricProfile từ dbt models."""
        tables, metrics = self.loader.load_models_and_metrics()

        # Xác thực các bảng
        self.assertIn("stg_real_estate", tables)
        self.assertIn("fct_real_estate_analytics", tables)
        self.assertIn("fct_district_monthly_summary", tables)

        # Kiểm tra cột của bảng Marts chi tiết
        fct_tbl = tables["fct_real_estate_analytics"]
        self.assertIn("price_segment", fct_tbl.columns)
        self.assertIn("area_segment", fct_tbl.columns)
        self.assertIn("price_per_sqm", fct_tbl.columns)

        # Kiểm tra cột của bảng Marts tổng hợp
        summary_tbl = tables["fct_district_monthly_summary"]
        self.assertIn("total_listings", summary_tbl.columns)
        self.assertIn("avg_price_per_sqm", summary_tbl.columns)

        # Xác thực Semantic Metrics
        self.assertIn("avg_price_per_sqm", metrics)
        self.assertIn("total_listings", metrics)
        self.assertIn("avg_property_price", metrics)
        self.assertIn("avg_property_area", metrics)

        metric_price = metrics["avg_price_per_sqm"]
        self.assertIn("đơn giá trung bình", metric_price.vn_terms)

    def test_compile_and_parse_manifest_json(self):
        """Kiểm tra sinh và đọc file target/manifest.json chuẩn của dbt."""
        manifest_path = self.loader.compile_manifest_mock()
        self.assertTrue(os.path.exists(manifest_path))

        tables, metrics = self.loader.load_models_and_metrics()
        self.assertGreaterEqual(len(tables), 3)
        self.assertGreaterEqual(len(metrics), 4)

    def test_sync_dbt_to_domain_manager(self):
        """Kiểm tra đồng bộ metadata dbt trực tiếp vào DomainManager."""
        dm = DomainManager()
        synced_cfg = self.loader.sync_to_domain_manager(dm, domain_id="real_estate")

        # Kiểm tra bảng Marts đã xuất hiện trong domain_config
        self.assertIn("fct_district_monthly_summary", synced_cfg.tables)
        self.assertIn("fct_real_estate_analytics", synced_cfg.tables)

        # Kiểm tra Semantic Metrics đã được nạp
        self.assertIn("avg_price_per_sqm", synced_cfg.metrics)
        self.assertIn("total_listings", synced_cfg.metrics)


if __name__ == "__main__":
    unittest.main()
