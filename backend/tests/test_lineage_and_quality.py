"""
Unit tests for Data Lineage & Data Quality Engine.
"""

import pytest
from app.core.lineage_service import LineageService
from app.core.dq_checker import DataQualityChecker
from app.core.domain_manager import DomainManager


def test_lineage_service_build_graph():
    service = LineageService()
    graph = service.build_domain_lineage_graph("ecommerce")

    assert graph is not None
    assert graph["domain_id"] == "ecommerce"
    assert graph["total_nodes"] > 5
    assert graph["total_edges"] >= 5

    # Check layers are present
    layer_types = {n.get("layer") for n in graph["nodes"]}
    assert "source" in layer_types
    assert "staging" in layer_types
    assert "warehouse" in layer_types
    assert "metric" in layer_types
    assert "consumer" in layer_types


def test_lineage_service_impact_analysis():
    service = LineageService()
    impact = service.analyze_impact("ecommerce", "orders", "status")

    assert impact is not None
    assert impact["domain_id"] == "ecommerce"
    assert impact["target"]["table_name"] == "orders"
    assert impact["target"]["column_name"] == "status"
    assert impact["risk_assessment"]["risk_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert impact["risk_assessment"]["blast_radius_score"] > 0
    assert len(impact["recommendations"]) > 0


def test_data_quality_checker_run():
    checker = DataQualityChecker()
    report = checker.run_domain_quality_checks("ecommerce")

    assert report is not None
    assert report["domain_id"] == "ecommerce"
    assert report["overall_score"] > 80.0
    assert report["summary"]["total"] >= 3
    assert report["summary"]["passed"] > 0
    assert len(report["table_summaries"]) > 0
    assert len(report["history"]) == 7
