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

from typing import Any, List

class MockEmbedding:
    def name(self) -> str:
        return "mock_embedding"

    def __call__(self, input: Any) -> Any:
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
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "staging", "ecommerce", "stg_orders.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "staging", "ecommerce", "stg_orders.yml")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "staging", "ecommerce", "stg_customers.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "ecommerce", "fct_orders_monthly_summary.sql")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "ecommerce", "fct_orders_monthly_summary.yml")))
        self.assertTrue(os.path.exists(os.path.join(dbt_dir, "models", "marts", "ecommerce", "marts.yml")))

    def test_dbt_models_and_metrics_extraction(self):
        """Kiểm tra trích xuất TableProfile và MetricProfile từ dbt models."""
        tables, metrics = self.loader.load_models_and_metrics()

        # Xác thực các bảng
        self.assertIn("stg_orders", tables)
        self.assertIn("stg_customers", tables)
        self.assertIn("fct_orders_monthly_summary", tables)

        # Kiểm tra cột của bảng Marts tổng hợp
        summary_tbl = tables["fct_orders_monthly_summary"]
        self.assertIn("report_month", summary_tbl.columns)
        self.assertIn("total_records", summary_tbl.columns)
        self.assertIn("status", summary_tbl.columns)

        # Xác thực Semantic Metrics
        self.assertIn("total_total_amount_orders", metrics)
        self.assertIn("avg_total_amount_orders", metrics)

        metric_total = metrics["total_total_amount_orders"]
        self.assertTrue(any("tổng" in term.lower() for term in metric_total.vn_terms))

    def test_compile_and_parse_manifest_json(self):
        """Kiểm tra đọc metadata dbt (manifest.json hoặc YAML fallback)."""
        info = self.loader.get_manifest_info()
        self.assertIsNotNone(info)
        self.assertIn("exists", info)

        tables, metrics = self.loader.load_models_and_metrics()
        self.assertGreaterEqual(len(tables), 3)
        self.assertGreaterEqual(len(metrics), 2)

    def test_sync_dbt_to_domain_manager(self):
        """Kiểm tra đồng bộ metadata dbt trực tiếp vào DomainManager."""
        dm = DomainManager()
        synced_cfg = self.loader.sync_to_domain_manager(dm, domain_id="ecommerce")

        # Kiểm tra bảng Marts đã xuất hiện trong domain_config
        self.assertIn("fct_orders_monthly_summary", synced_cfg.tables)
        self.assertIn("stg_orders", synced_cfg.tables)

        # Kiểm tra Semantic Metrics đã được nạp
        self.assertIn("total_total_amount_orders", synced_cfg.metrics)
        self.assertIn("avg_total_amount_orders", synced_cfg.metrics)


if __name__ == "__main__":
    unittest.main()
