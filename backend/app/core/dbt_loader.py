"""
dbt Manifest Loader — Đọc manifest.json thật do `dbt compile` sinh ra.
Trích xuất TableProfile và MetricProfile từ:
  - nodes (models): tên bảng, cột, data type, description, meta.vn_name
  - metrics: ASCII name, label, meta.vn_terms (tiếng Việt cho AI Agent)
  - sources: bảng nguồn raw
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
    Nạp metadata từ dbt manifest.json thật (do `dbt compile` sinh ra) vào AI Agent.
    Fallback: đọc trực tiếp từ các file .yml trong models/ nếu chưa có manifest.
    """

    def __init__(self, dbt_project_dir: Optional[str] = None):
        from pathlib import Path
        base_dir = str(Path(backend_dir).parent)
        self.dbt_dir      = dbt_project_dir or os.path.join(base_dir, "infra", "dbt")
        self.manifest_path = os.path.join(self.dbt_dir, "target", "manifest.json")
        self.models_dir    = os.path.join(self.dbt_dir, "models")

    # =========================================================================
    # 1. ENTRY POINT
    # =========================================================================

    def load_models_and_metrics(self) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """Trích xuất TableProfile và MetricProfile từ dbt project."""
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                tables, metrics = self._parse_manifest_json(manifest)
                if tables or metrics:
                    logger.info(f"[dbt_loader] Đọc manifest.json: {len(tables)} models, {len(metrics)} metrics.")
                    return tables, metrics
            except Exception as e:
                logger.warning(f"[dbt_loader] Không thể đọc manifest.json ({e}), fallback sang YAML.")

        logger.info("[dbt_loader] Fallback: đọc trực tiếp từ models/*.yml")
        return self._parse_from_models_yaml()

    # =========================================================================
    # 2. ĐỌC MANIFEST.JSON THẬT
    # =========================================================================

    def _parse_manifest_json(
        self, manifest: Dict[str, Any]
    ) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """Phân tích manifest.json chuẩn của dbt (v7–v12)."""
        tables:  Dict[str, TableProfile]  = {}
        metrics: Dict[str, MetricProfile] = {}

        # ── 2a. Nodes (models) ────────────────────────────────────────────────
        for node_id, node in manifest.get("nodes", {}).items():
            if node.get("resource_type") != "model":
                continue

            t_name = node.get("name", "")
            desc   = node.get("description", "")
            meta   = node.get("meta", {})
            vn_name = meta.get("vn_name") or desc.split(".")[0] or t_name

            cols_dict: Dict[str, ColumnProfile] = {}
            for c_name, c_info in node.get("columns", {}).items():
                c_meta = c_info.get("meta", {})
                c_desc = c_info.get("description", "")
                cols_dict[c_name] = ColumnProfile(
                    name=c_name,
                    vn_name=c_meta.get("vn_name") or c_desc.split(".")[0] or c_name,
                    data_type=c_info.get("data_type", "VARCHAR(255)"),
                    description=c_desc,
                    synonyms=c_meta.get("synonyms", []),
                )

            tables[t_name] = TableProfile(
                table_name=t_name,
                vn_name=vn_name,
                description=desc,
                columns=cols_dict,
            )

        # ── 2b. Sources (raw tables cũng đưa vào context) ────────────────────
        for src_id, src_node in manifest.get("sources", {}).items():
            if src_node.get("resource_type") != "source":
                continue
            src_name = src_node.get("name", "")
            src_meta = src_node.get("meta", {})
            src_desc = src_node.get("description", "")
            if src_name and src_name not in tables:
                cols_dict = {}
                for c_name, c_info in src_node.get("columns", {}).items():
                    c_meta = c_info.get("meta", {})
                    cols_dict[c_name] = ColumnProfile(
                        name=c_name,
                        vn_name=c_meta.get("vn_name") or c_name,
                        data_type=c_info.get("data_type", "VARCHAR(255)"),
                        description=c_info.get("description", ""),
                        synonyms=c_meta.get("synonyms", []),
                    )
                tables[src_name] = TableProfile(
                    table_name=src_name,
                    vn_name=src_meta.get("vn_name") or src_desc or src_name,
                    description=src_desc,
                    columns=cols_dict,
                )

        # ── 2c. Metrics (MetricFlow) ──────────────────────────────────────────
        # manifest v7+: manifest["metrics"]
        # manifest v10+: manifest["semantic_models"] + manifest["metrics"]
        for m_id, m_node in manifest.get("metrics", {}).items():
            name     = m_node.get("name", "")
            label    = m_node.get("label", name)
            desc     = m_node.get("description", "")
            meta     = m_node.get("meta", {})
            vn_terms = meta.get("vn_terms") or [label.lower(), name]

            # Tìm sql expression từ nhiều format khác nhau
            sql_expr = (
                m_node.get("sql")
                or m_node.get("expression")
                or m_node.get("type", "count")
            )

            if name:
                metrics[name] = MetricProfile(
                    metric_id=name,
                    vn_terms=vn_terms,
                    sql_expression=str(sql_expr),
                    description=desc or label,
                )

        return tables, metrics

    # =========================================================================
    # 3. FALLBACK: ĐỌC TRỰC TIẾP TỪ .YML
    # =========================================================================

    def _parse_from_models_yaml(self) -> Tuple[Dict[str, TableProfile], Dict[str, MetricProfile]]:
        """Duyệt models/*.yml và metrics.yml để trích xuất metadata khi chưa compile."""
        tables:  Dict[str, TableProfile]  = {}
        metrics: Dict[str, MetricProfile] = {}

        if not os.path.exists(self.models_dir):
            return tables, metrics

        for root, _, files in os.walk(self.models_dir):
            for file in sorted(files):
                if not (file.endswith(".yml") or file.endswith(".yaml")):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                    # ── Models ────────────────────────────────────────────
                    for m in data.get("models", []):
                        m_name = m.get("name", "")
                        m_desc = m.get("description", "")
                        m_meta = m.get("meta", {})
                        vn_name = m_meta.get("vn_name") or m_desc.split(".")[0] or m_name

                        cols_dict: Dict[str, ColumnProfile] = {}
                        for c in m.get("columns", []):
                            c_name = c.get("name", "")
                            c_desc = c.get("description", "")
                            c_meta = c.get("meta", {})
                            cols_dict[c_name] = ColumnProfile(
                                name=c_name,
                                vn_name=c_meta.get("vn_name") or c_desc.split(".")[0] or c_name,
                                data_type=c.get("data_type", "VARCHAR(255)"),
                                description=c_desc,
                                synonyms=c_meta.get("synonyms", []),
                            )

                        if m_name:
                            tables[m_name] = TableProfile(
                                table_name=m_name,
                                vn_name=vn_name,
                                description=m_desc,
                                columns=cols_dict,
                            )

                    # ── Sources ────────────────────────────────────────────
                    for src in data.get("sources", []):
                        for t in src.get("tables", []):
                            t_name = t.get("name", "")
                            t_meta = t.get("meta", {})
                            t_desc = t.get("description", "")
                            if t_name and t_name not in tables:
                                tables[t_name] = TableProfile(
                                    table_name=t_name,
                                    vn_name=t_meta.get("vn_name") or t_desc or t_name,
                                    description=t_desc,
                                    columns={},
                                )

                    # ── Metrics ────────────────────────────────────────────
                    for met in data.get("metrics", []):
                        met_name  = met.get("name", "")
                        met_desc  = met.get("description", "")
                        met_label = met.get("label", met_name)
                        met_meta  = met.get("meta", {})
                        vn_terms  = met_meta.get("vn_terms") or [met_label.lower(), met_name]

                        # Tương thích cả dbt metrics v1 và MetricFlow v2
                        sql_expr = (
                            met.get("sql")
                            or met.get("expression")
                            or met.get("type", "count")
                        )

                        if met_name:
                            metrics[met_name] = MetricProfile(
                                metric_id=met_name,
                                vn_terms=vn_terms,
                                sql_expression=str(sql_expr),
                                description=met_desc or met_label,
                            )

                except Exception as e:
                    logger.warning(f"[dbt_loader] Lỗi đọc {file_path}: {e}")

        logger.info(f"[dbt_loader] YAML fallback: {len(tables)} models, {len(metrics)} metrics.")
        return tables, metrics

    # =========================================================================
    # 4. SYNC VÀO DOMAIN MANAGER
    # =========================================================================

    def sync_to_domain_manager(
        self,
        domain_manager: Optional[DomainManager] = None,
        domain_id: Optional[str] = None,
    ) -> DomainConfig:
        """Đồng bộ metadata từ dbt vào DomainConfig của DomainManager."""
        dm  = domain_manager or DomainManager()
        cfg = dm.get_domain(domain_id) if domain_id else dm.get_active_domain_config()
        if not cfg:
            cfg = dm.get_active_domain_config()

        dbt_tables, dbt_metrics = self.load_models_and_metrics()

        # Bổ sung/override bảng từ dbt (dbt models là source of truth cho marts)
        for t_name, t_profile in dbt_tables.items():
            cfg.tables[t_name] = t_profile

        # Merge metrics — bảo toàn depends_on nếu đã có
        for m_name, m_profile in dbt_metrics.items():
            if m_name in cfg.metrics:
                existing = cfg.metrics[m_name]
                if not m_profile.depends_on_columns and existing.depends_on_columns:
                    m_profile.depends_on_columns = existing.depends_on_columns
                if not m_profile.depends_on_tables and existing.depends_on_tables:
                    m_profile.depends_on_tables = existing.depends_on_tables
                if existing.vn_terms:
                    m_profile.vn_terms = list(dict.fromkeys(m_profile.vn_terms + existing.vn_terms))
            cfg.metrics[m_name] = m_profile

        logger.info(f"[dbt_loader] Đồng bộ {len(dbt_tables)} bảng, {len(dbt_metrics)} metrics vào domain '{domain_id}'.")
        return cfg

    # =========================================================================
    # 5. UTILITY
    # =========================================================================

    def get_manifest_info(self) -> Dict[str, Any]:
        """Trả về thông tin về manifest.json hiện tại."""
        if not os.path.exists(self.manifest_path):
            return {"exists": False, "path": self.manifest_path}
        try:
            stat = os.stat(self.manifest_path)
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            meta = manifest.get("metadata", {})
            return {
                "exists": True,
                "path": self.manifest_path,
                "size_bytes": stat.st_size,
                "dbt_version": meta.get("dbt_version", "unknown"),
                "project_name": meta.get("project_name", "unknown"),
                "generated_at": meta.get("generated_at", "unknown"),
                "models_count": sum(1 for n in manifest.get("nodes", {}).values() if n.get("resource_type") == "model"),
                "metrics_count": len(manifest.get("metrics", {})),
                "sources_count": len(manifest.get("sources", {})),
            }
        except Exception as e:
            return {"exists": True, "path": self.manifest_path, "error": str(e)}
