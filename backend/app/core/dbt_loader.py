"""
dbt Manifest Loader & Semantic Layer Integration.
Tự động phân tích cú pháp dbt project (manifest.json hoặc models YAML)
để nạp các bảng Marts và Semantic Metrics trực tiếp vào AI Agent (Zero-code Sync).
"""

import os
import sys
import json
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import TableProfile, ColumnProfile, MetricProfile, DomainConfig
from app.core.domain_manager import DomainManager

logger = logging.getLogger("DbtManifestLoader")


class DbtManifestLoader:
    """
    Bộ nạp metadata từ dbt project vào AI Agent.
    Hỗ trợ 2 chế độ:
    1. Đọc file biên dịch target/manifest.json chính thức của dbt.
    2. Đọc trực tiếp các file schema.yml / marts.yml trong thư mục models (khi chưa chạy dbt compile).
    """

    def __init__(self, dbt_project_dir: Optional[str] = None):
        base_dir = os.getcwd()
        self.dbt_dir = dbt_project_dir or os.path.join(base_dir, "infra", "dbt")
        self.manifest_path = os.path.join(self.dbt_dir, "target", "manifest.json")
        self.models_dir = os.path.join(self.dbt_dir, "models")

    def load_models_and_metrics(self) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """
        Trích xuất danh sách TableProfile và MetricProfile từ dbt project.
        """
        # 1. Nếu có manifest.json được dbt compile sẵn
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                return self._parse_manifest_json(manifest)
            except Exception as e:
                logger.warning(f"Không thể đọc manifest.json ({e}), chuyển sang đọc YAML trực tiếp.")

        # 2. Fallback đọc trực tiếp từ thư mục models/*.yml
        return self._parse_from_models_yaml()

    def _parse_manifest_json(self, manifest: Dict[str, Any]) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """Phân tích file target/manifest.json chuẩn của dbt."""
        tables: Dict[str, TableProfile] = {}
        metrics: Dict[str, MetricProfile] = {}

        # Trích xuất models (nodes)
        nodes = manifest.get("nodes", {})
        for node_id, node in nodes.items():
            if node.get("resource_type") == "model":
                tbl_name = node.get("name")
                desc = node.get("description", "")
                cols_dict: Dict[str, ColumnProfile] = {}

                for c_name, c_info in node.get("columns", {}).items():
                    data_type = c_info.get("data_type", "VARCHAR(255)")
                    c_desc = c_info.get("description", "")
                    cols_dict[c_name] = ColumnProfile(
                        name=c_name,
                        vn_name=c_desc.split(".")[0] if c_desc else c_name,
                        data_type=data_type,
                        description=c_desc
                    )

                tables[tbl_name] = TableProfile(
                    table_name=tbl_name,
                    vn_name=desc.split(".")[0] if desc else tbl_name,
                    description=desc,
                    columns=cols_dict
                )

        # Trích xuất metrics
        metrics_dict = manifest.get("metrics", {})
        for m_id, m_node in metrics_dict.items():
            name = m_node.get("name")
            desc = m_node.get("description", "")
            sql_expr = m_node.get("sql") or m_node.get("type", "sum")
            label = m_node.get("label", name)
            meta = m_node.get("meta", {})
            vn_terms = meta.get("vn_terms", [label, name])

            metrics[name] = MetricProfile(
                metric_id=name,
                vn_terms=vn_terms,
                sql_expression=str(sql_expr),
                description=desc
            )

        return tables, metrics

    def _parse_from_models_yaml(self) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """Duyệt các file .yml trong thư mục infra/dbt/models để trích xuất metadata."""
        tables: Dict[str, TableProfile] = {}
        metrics: Dict[str, MetricProfile] = {}

        if not os.path.exists(self.models_dir):
            return tables, metrics

        for root, _, files in os.walk(self.models_dir):
            for file in files:
                if file.endswith(".yml") or file.endswith(".yaml"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}

                        # Đọc models
                        for m in data.get("models", []):
                            m_name = m.get("name")
                            m_desc = m.get("description", "")
                            cols_dict = {}

                            for c in m.get("columns", []):
                                c_name = c.get("name")
                                c_desc = c.get("description", "")
                                cols_dict[c_name] = ColumnProfile(
                                    name=c_name,
                                    vn_name=c_desc.split(".")[0] if c_desc else c_name,
                                    data_type="VARCHAR(255)",
                                    description=c_desc
                                )

                            tables[m_name] = TableProfile(
                                table_name=m_name,
                                vn_name=m_desc.split(".")[0] if m_desc else m_name,
                                description=m_desc,
                                columns=cols_dict
                            )

                        # Đọc metrics
                        for met in data.get("metrics", []):
                            met_name = met.get("name")
                            met_desc = met.get("description", "")
                            met_label = met.get("label", met_name)
                            met_sql = met.get("sql", met.get("type", "sum"))
                            vn_terms = met.get("vn_terms", [met_label.lower(), met_name])

                            metrics[met_name] = MetricProfile(
                                metric_id=met_name,
                                vn_terms=vn_terms,
                                sql_expression=str(met_sql),
                                description=met_desc
                            )
                    except Exception as e:
                        logger.warning(f"Lỗi đọc file YAML {file_path}: {e}")

        return tables, metrics

    def sync_to_domain_manager(
        self,
        domain_manager: Optional[DomainManager] = None,
        domain_id: str = "real_estate"
    ) -> DomainConfig:
        """
        Đồng bộ hóa metadata từ dbt trực tiếp vào DomainConfig của DomainManager.
        """
        dm = domain_manager or DomainManager()
        cfg = dm.get_domain(domain_id)
        if not cfg:
            raise ValueError(f"Không tìm thấy domain_id {domain_id}")

        dbt_tables, dbt_metrics = self.load_models_and_metrics()

        # Bổ sung các bảng dbt Marts vào schema
        for t_name, t_profile in dbt_tables.items():
            cfg.tables[t_name] = t_profile

        # Bổ sung các Semantic Metrics vào danh mục
        for m_name, m_profile in dbt_metrics.items():
            cfg.metrics[m_name] = m_profile

        logger.info(f"Đã đồng bộ {len(dbt_tables)} bảng và {len(dbt_metrics)} metrics từ dbt vào domain '{domain_id}'.")
        return cfg

    def compile_manifest_mock(self) -> str:
        """
        Sinh file target/manifest.json mô phỏng từ các file YAML/SQL
        phục vụ môi trường development / CI khi chưa cài máy chủ dbt-doris CLI.
        """
        target_dir = os.path.join(self.dbt_dir, "target")
        os.makedirs(target_dir, exist_ok=True)

        dbt_tables, dbt_metrics = self._parse_from_models_yaml()

        nodes = {}
        for t_name, t_prof in dbt_tables.items():
            cols = {}
            for c_name, c_prof in t_prof.columns.items():
                cols[c_name] = {
                    "name": c_name,
                    "description": c_prof.description,
                    "data_type": c_prof.data_type
                }
            nodes[f"model.real_estate_analytics.{t_name}"] = {
                "resource_type": "model",
                "name": t_name,
                "description": t_prof.description,
                "columns": cols
            }

        metrics_json = {}
        for m_name, m_prof in dbt_metrics.items():
            metrics_json[f"metric.real_estate_analytics.{m_name}"] = {
                "name": m_name,
                "description": m_prof.description,
                "sql": m_prof.sql_expression,
                "meta": {"vn_terms": m_prof.vn_terms}
            }

        manifest = {
            "metadata": {
                "dbt_version": "1.8.0",
                "project_name": "real_estate_analytics"
            },
            "nodes": nodes,
            "metrics": metrics_json
        }

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return self.manifest_path
