import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.lineage_service import LineageService
from app.core.dq_checker import DataQualityChecker
from app.core.domain_manager import DomainManager


class TestLineageAndQuality(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile
        dm = DomainManager()
        ecom = DomainConfig(
            domain_id="ecommerce",
            display_name="E-Commerce",
            description="Dữ liệu thương mại điện tử",
            tables={
                "orders": TableProfile(
                    table_name="orders",
                    columns={
                        "order_id": ColumnProfile(name="order_id", data_type="BIGINT", is_primary_key=True),
                        "status": ColumnProfile(name="status", data_type="VARCHAR"),
                        "total_amount": ColumnProfile(name="total_amount", data_type="DOUBLE")
                    }
                )
            },
            metrics={
                "gmv": MetricProfile(
                    metric_id="gmv",
                    sql_expression="SUM(total_amount)",
                    depends_on_tables=["orders"],
                    depends_on_columns=["total_amount"]
                )
            }
        )
        dm.register_domain(ecom)

    def test_lineage_service_build_graph(self):
        service = LineageService()
        graph = service.build_domain_lineage_graph("ecommerce")

        self.assertIsNotNone(graph)
        self.assertEqual(graph["domain_id"], "ecommerce")
        self.assertGreater(graph["total_nodes"], 5)
        self.assertGreaterEqual(graph["total_edges"], 5)

        # Check layers are present
        layer_types = {n.get("layer") for n in graph["nodes"]}
        self.assertIn("source", layer_types)
        self.assertIn("staging", layer_types)
        self.assertIn("warehouse", layer_types)
        self.assertIn("metric", layer_types)
        self.assertIn("consumer", layer_types)

    def test_lineage_service_impact_analysis(self):
        service = LineageService()
        impact = service.analyze_impact("ecommerce", "orders", "status")

        self.assertIsNotNone(impact)
        self.assertEqual(impact["domain_id"], "ecommerce")
        self.assertEqual(impact["target"]["table_name"], "orders")
        self.assertEqual(impact["target"]["column_name"], "status")
        self.assertIn(impact["risk_assessment"]["risk_level"], ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.assertGreater(impact["risk_assessment"]["blast_radius_score"], 0)
        self.assertGreater(len(impact["recommendations"]), 0)

    def test_data_quality_checker_run(self):
        checker = DataQualityChecker()
        report = checker.run_domain_quality_checks("ecommerce")

        self.assertIsNotNone(report)
        self.assertEqual(report["domain_id"], "ecommerce")
        self.assertGreater(report["overall_score"], 80.0)
        self.assertGreaterEqual(report["summary"]["total"], 3)
        self.assertGreater(report["summary"]["passed"], 0)
        self.assertGreater(len(report["table_summaries"]), 0)
        self.assertEqual(len(report["history"]), 7)


if __name__ == "__main__":
    unittest.main()
