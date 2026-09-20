"""
Autonomous dbt Auto-Adapter (Cỗ Máy dbt Tự Thích Ứng & Chống Mù Quáng Nghiệp Vụ).
Tự động phân tích DomainConfig từ bất kỳ CSDL nào được nạp vào,
áp dụng 4 Tầng Guardrails thông minh để sinh ra toàn bộ dbt pipeline:
- Staging models (làm sạch dữ liệu, ép kiểu, lọc null)
- Data Marts models (tổng hợp thời gian, gom nhóm dimensions, tính metric)
- Semantic Metrics (khai báo chỉ số nghiệp vụ chuẩn)
- Tự động cấu hình profiles.yml và đồng bộ manifest vào AI Agent.
"""

import os
import re
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile
from app.core.dbt_loader import DbtManifestLoader

logger = logging.getLogger("AutoDbtGenerator")


class AutoDbtGenerator:
    """
    Bộ sinh tự động pipeline dbt với các nguyên tắc chống mù quáng ngữ cảnh (Anti-Blindness Guardrails).
    """

    # Guardrail 1: Blacklist các bảng kỹ thuật, bảng tạm, bảng log
    BLACKLIST_TABLE_PATTERNS = [
        r"^log_", r"_log$", r"^audit_", r"_audit$", r"^temp_", r"^tmp_",
        r"^session_", r"_session$", r"^cache_", r"_cache$",
        r"^alembic_", r"^flyway_", r"^schema_migrations$"
    ]

    # Guardrail 2: Thứ tự ưu tiên mốc thời gian (Lifecycle Timestamp Priority)
    # Ưu tiên các mốc hoàn tất giao dịch trước mốc khởi tạo đơn thuần
    TIMESTAMP_PRIORITY_PATTERNS = [
        (r"(delivered|completed|success|finished)_at", 100),
        (r"(paid|settled|disbursed)_at", 90),
        (r"(published|posted)_at", 80),
        (r"(shipped|dispatched)_at", 70),
        (r"(order|transaction|invoice)_date", 60),
        (r"(created|inserted|registered)_at", 50),
        (r"(date|time|timestamp)", 40)
    ]

    # Guardrail 4: Từ khóa nhận diện Dimensions cốt lõi (Low-Medium Cardinality)
    CORE_DIMENSION_PATTERNS = [
        r"(category|type|status|tier|segment|district|province|city|state|channel|payment_method|department)"
    ]

    def __init__(self, dbt_dir: Optional[str] = None):
        """Khởi tạo với đường dẫn tới thư mục dbt project."""
        if dbt_dir:
            self.dbt_dir = os.path.abspath(dbt_dir)
        else:
            base_infra = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "infra"))
            self.dbt_dir = os.path.join(base_infra, "dbt")

        self.models_dir = os.path.join(self.dbt_dir, "models")
        self.staging_dir = os.path.join(self.models_dir, "staging")
        self.marts_dir = os.path.join(self.models_dir, "marts")

    # =========================================================================
    # 1. BỘ PHÂN LOẠI & HEURISTICS NGỮ NGHĨA (SEMANTIC INFERENCE)
    # =========================================================================

    def is_ignorable_table(self, table_name: str) -> bool:
        """Guardrail 1: Kiểm tra xem bảng có phải là bảng rác/bảng kỹ thuật không."""
        tbl_lower = table_name.lower()
        for pat in self.BLACKLIST_TABLE_PATTERNS:
            if re.search(pat, tbl_lower):
                return True
        return False

    def categorize_columns(self, table: TableProfile) -> Dict[str, Any]:
        """
        Phân loại toàn bộ các cột trong bảng thành:
        - Primary Keys / Foreign Keys
        - Time Columns (có xếp hạng ưu tiên)
        - Metric Columns (các cột số đo lường)
        - Dimension Columns (các cột phân loại)
        """
        primary_keys = []
        foreign_keys = []
        time_columns = []
        metric_columns = []
        dimension_columns = []

        for c_name, col in table.columns.items():
            name_lower = c_name.lower()
            dtype_lower = (col.data_type or "").lower()

            # 1. Khóa
            if col.is_primary_key or name_lower == "id" or name_lower == f"{table.table_name}_id":
                primary_keys.append(c_name)
            elif col.foreign_key or (name_lower.endswith("_id") and name_lower != "id"):
                foreign_keys.append(c_name)

            # 2. Thời gian
            is_time = any(t in dtype_lower for t in ["date", "time", "timestamp", "year"]) or any(
                k in name_lower for k in ["_at", "_date", "date_", "time", "timestamp", "year", "month"]
            )
            if is_time:
                # Tính điểm ưu tiên (Guardrail 2)
                score = 10
                for pat, p_score in self.TIMESTAMP_PRIORITY_PATTERNS:
                    if re.search(pat, name_lower):
                        score = max(score, p_score)
                time_columns.append((c_name, score))

            # 3. Định lượng (Metrics)
            is_numeric = any(n in dtype_lower for n in ["int", "decimal", "float", "double", "numeric", "real"])
            if is_numeric and c_name not in primary_keys and c_name not in foreign_keys:
                metric_keywords = ["price", "amount", "total", "revenue", "cost", "quantity", "fee", "area", "value", "balance", "rate"]
                if any(k in name_lower for k in metric_keywords) or not name_lower.endswith("_id"):
                    metric_columns.append(c_name)

            # 4. Phân loại (Dimensions)
            if c_name not in primary_keys and c_name not in foreign_keys and not is_time and c_name not in metric_columns:
                dimension_columns.append(c_name)

        # Sắp xếp cột thời gian theo thứ tự ưu tiên giảm dần
        time_columns.sort(key=lambda x: x[1], reverse=True)
        sorted_time_cols = [c[0] for c in time_columns]

        # Guardrail 4: Sắp xếp dimensions ưu tiên các cột cốt lõi
        def dim_priority(dim_name: str) -> int:
            dim_l = dim_name.lower()
            for pat in self.CORE_DIMENSION_PATTERNS:
                if re.search(pat, dim_l):
                    return 100
            return 10

        dimension_columns.sort(key=dim_priority, reverse=True)

        return {
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "time_columns": sorted_time_cols,
            "metric_columns": metric_columns,
            "dimension_columns": dimension_columns
        }

    # =========================================================================
    # 2. SINH MÃ DBT MODELS (STAGING & MARTS)
    # =========================================================================

    def generate_staging_model(
        self,
        table: TableProfile,
        domain_id: str,
        categories: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Sinh mã SQL và YAML cho Staging model:
        - models/staging/{domain_id}/stg_{table.table_name}.sql
        - models/staging/{domain_id}/stg_{table.table_name}.yml
        """
        t_name = table.table_name
        stg_name = f"stg_{t_name}"
        pk = categories["primary_keys"][0] if categories["primary_keys"] else None

        # 1. SQL Staging
        sql_lines = [
            "{{ config(materialized='view') }}",
            "",
            "WITH source_data AS (",
            f"    SELECT * FROM {t_name}",
            "),",
            "cleaned AS (",
            "    SELECT"
        ]

        col_selects = []
        for c_name, col in table.columns.items():
            dtype = (col.data_type or "").upper()
            if "VARCHAR" in dtype or "TEXT" in dtype or "CHAR" in dtype:
                col_selects.append(f"        TRIM({c_name}) AS {c_name}")
            elif "DATE" in dtype or "TIME" in dtype:
                col_selects.append(f"        CAST({c_name} AS DATE) AS {c_name}")
            elif "INT" in dtype or "DECIMAL" in dtype or "FLOAT" in dtype:
                col_selects.append(f"        COALESCE({c_name}, 0) AS {c_name}")
            else:
                col_selects.append(f"        {c_name}")

        sql_lines.append(",\n".join(col_selects))
        sql_lines.append("    FROM source_data")
        if pk:
            sql_lines.append(f"    WHERE {pk} IS NOT NULL")
        sql_lines.append(")")
        sql_lines.append("SELECT * FROM cleaned")
        sql_content = "\n".join(sql_lines) + "\n"

        # 2. YAML Staging Tests
        yml_dict = {
            "version": 2,
            "models": [
                {
                    "name": stg_name,
                    "description": f"Bảng staging làm sạch dữ liệu từ bảng nguồn {t_name}.",
                    "columns": []
                }
            ]
        }
        cols_yaml = []
        for c_name in table.columns:
            c_entry = {
                "name": c_name,
                "description": f"Cột {c_name} đã được chuẩn hóa."
            }
            if pk and c_name == pk:
                c_entry["tests"] = ["unique", "not_null"]
            cols_yaml.append(c_entry)
        yml_dict["models"][0]["columns"] = cols_yaml

        yml_content = yaml.dump(yml_dict, allow_unicode=True, sort_keys=False)
        return sql_content, yml_content

    def generate_marts_model(
        self,
        table: TableProfile,
        domain_id: str,
        categories: Dict[str, Any]
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """
        Sinh mã SQL và YAML cho Data Mart:
        Chỉ sinh khi bảng có: Ít nhất 1 Cột thời gian VÀ Ít nhất 1 Cột Metric.
        Áp dụng Guardrail 4: Giới hạn Top 2-3 dimensions cốt lõi.
        """
        time_cols = categories["time_columns"]
        metric_cols = categories["metric_columns"]
        dim_cols = categories["dimension_columns"]

        if not time_cols or not metric_cols:
            return None

        # Guardrail 2: Lấy cột thời gian có độ ưu tiên cao nhất
        best_time_col = time_cols[0]
        # Guardrail 4: Giới hạn tối đa 3 dimensions quan trọng nhất
        selected_dims = dim_cols[:3]

        t_name = table.table_name
        stg_name = f"stg_{t_name}"
        fct_name = f"fct_{t_name}_monthly_summary"

        # 1. SQL Marts
        sql_lines = [
            "{{ config(materialized='table') }}",
            "",
            "SELECT",
            f"    DATE_FORMAT({best_time_col}, '%Y-%m') AS report_month,"
        ]
        for dim in selected_dims:
            sql_lines.append(f"    {dim},")

        sql_lines.append("    COUNT(*) AS total_records,")

        # Guardrail 3: Công thức kết hợp metrics
        metric_selects = []
        semantic_metrics = []

        # Tự động phát hiện cặp price + quantity nếu có
        has_price = any("price" in m.lower() for m in metric_cols)
        has_qty = any("quantity" in m.lower() or "qty" in m.lower() for m in metric_cols)
        if has_price and has_qty:
            p_col = next(m for m in metric_cols if "price" in m.lower())
            q_col = next(m for m in metric_cols if "quantity" in m.lower() or "qty" in m.lower())
            metric_selects.append(f"    ROUND(SUM({p_col} * {q_col}), 2) AS total_gross_revenue")
            semantic_metrics.append({
                "name": f"total_gross_revenue_{t_name}",
                "label": f"Tổng Doanh Thu Gộp ({table.vn_name or t_name})",
                "sql": f"SUM({p_col} * {q_col})"
            })

        for m_col in metric_cols[:4]:
            metric_selects.append(f"    ROUND(SUM({m_col}), 2) AS total_{m_col}")
            metric_selects.append(f"    ROUND(AVG({m_col}), 2) AS avg_{m_col}")

            semantic_metrics.append({
                "name": f"total_{m_col}_{t_name}",
                "label": f"Tổng {m_col} ({table.vn_name or t_name})",
                "sql": f"SUM({m_col})"
            })
            semantic_metrics.append({
                "name": f"avg_{m_col}_{t_name}",
                "label": f"Trung Bình {m_col} ({table.vn_name or t_name})",
                "sql": f"AVG({m_col})"
            })

        sql_lines.append(",\n".join(metric_selects))
        sql_lines.append(f"FROM {{{{ ref('{stg_name}') }}}}")
        sql_lines.append("GROUP BY")

        group_by_indices = [str(i) for i in range(1, len(selected_dims) + 2)]
        sql_lines.append("    " + ", ".join(group_by_indices))
        sql_lines.append("ORDER BY report_month DESC")

        sql_content = "\n".join(sql_lines) + "\n"

        # 2. YAML Marts
        marts_yaml_dict = {
            "version": 2,
            "models": [
                {
                    "name": fct_name,
                    "description": f"Bảng Data Mart tổng hợp theo tháng cho {table.vn_name or t_name}.",
                    "columns": [
                        {"name": "report_month", "description": "Tháng thống kê (YYYY-MM)"},
                        {"name": "total_records", "description": "Tổng số lượng bản ghi"}
                    ]
                }
            ]
        }
        for dim in selected_dims:
            marts_yaml_dict["models"][0]["columns"].append({
                "name": dim,
                "description": f"Chiều phân loại {dim}"
            })

        yml_content = yaml.dump(marts_yaml_dict, allow_unicode=True, sort_keys=False)

        metrics_meta = {
            "fct_name": fct_name,
            "metrics": semantic_metrics
        }
        return sql_content, yml_content, metrics_meta

    # =========================================================================
    # 3. ĐIỀU PHỐI TỔNG THỂ (ORCHESTRATION PIPELINE)
    # =========================================================================

    def generate_domain_dbt(
        self,
        domain_config: DomainConfig,
        auto_compile: bool = True
    ) -> Dict[str, Any]:
        """
        Tự động sinh toàn bộ dự án dbt cho một DomainConfig:
        1. Tạo thư mục models/staging/{domain_id} và models/marts/{domain_id}.
        2. Sinh stg_*.sql và stg_*.yml cho các bảng hợp lệ (loại bỏ bảng rác).
        3. Sinh fct_*_summary.sql và marts.yml cho các bảng Data Mart.
        4. Cập nhật profiles.yml sang schema mới.
        5. Compile dbt và đồng bộ manifest vào DomainManager.
        """
        domain_id = domain_config.domain_id
        dom_stg_dir = os.path.join(self.staging_dir, domain_id)
        dom_marts_dir = os.path.join(self.marts_dir, domain_id)

        os.makedirs(dom_stg_dir, exist_ok=True)
        os.makedirs(dom_marts_dir, exist_ok=True)

        generated_staging = []
        generated_marts = []
        all_semantic_metrics = []

        # 1. Duyệt từng bảng trong Domain
        for t_name, table in domain_config.tables.items():
            # Guardrail 1: Bỏ qua bảng rác/bảng kỹ thuật
            if self.is_ignorable_table(t_name):
                logger.info(f"Bỏ qua bảng rác/kỹ thuật: {t_name}")
                continue

            categories = self.categorize_columns(table)

            # Sinh Staging model
            stg_sql, stg_yml = self.generate_staging_model(table, domain_id, categories)
            stg_sql_path = os.path.join(dom_stg_dir, f"stg_{t_name}.sql")
            stg_yml_path = os.path.join(dom_stg_dir, f"stg_{t_name}.yml")

            with open(stg_sql_path, "w", encoding="utf-8") as f:
                f.write(stg_sql)
            with open(stg_yml_path, "w", encoding="utf-8") as f:
                f.write(stg_yml)

            generated_staging.append(f"stg_{t_name}")

            # Sinh Data Marts model nếu có đủ điều kiện
            mart_res = self.generate_marts_model(table, domain_id, categories)
            if mart_res:
                mart_sql, mart_yml, m_meta = mart_res
                fct_name = m_meta["fct_name"]
                mart_sql_path = os.path.join(dom_marts_dir, f"{fct_name}.sql")
                mart_yml_path = os.path.join(dom_marts_dir, f"{fct_name}.yml")

                with open(mart_sql_path, "w", encoding="utf-8") as f:
                    f.write(mart_sql)
                with open(mart_yml_path, "w", encoding="utf-8") as f:
                    f.write(mart_yml)

                generated_marts.append(fct_name)
                all_semantic_metrics.extend(m_meta["metrics"])

        # 2. Sinh file semantic metrics marts.yml cho domain
        if all_semantic_metrics:
            metrics_file_dict = {
                "version": 2,
                "metrics": []
            }
            for sm in all_semantic_metrics:
                metrics_file_dict["metrics"].append({
                    "name": sm["name"],
                    "label": sm["label"],
                    "model": f"ref('{sm['name'].split('_')[-1]}')",
                    "description": f"Chỉ số {sm['label']} được tự động tạo bởi AutoDbtGenerator.",
                    "calculation_method": "derived",
                    "expression": sm["sql"],
                    "timestamp": "report_month",
                    "time_grains": ["month"],
                    "meta": {
                        "vn_terms": [sm["label"], sm["name"]]
                    }
                })

            marts_yml_path = os.path.join(dom_marts_dir, "marts.yml")
            with open(marts_yml_path, "w", encoding="utf-8") as f:
                yaml.dump(metrics_file_dict, f, allow_unicode=True, sort_keys=False)

        # 3. Cập nhật profiles.yml
        self.update_profiles_schema(domain_config.domain_id)

        # 4. Tự động đồng bộ vào DomainManager qua DbtManifestLoader
        loader = DbtManifestLoader(dbt_project_dir=self.dbt_dir)
        tables_loaded, metrics_loaded = loader.load_models_and_metrics()
        loader.sync_to_domain_manager(domain_id=domain_id)

        return {
            "domain_id": domain_id,
            "staging_models": generated_staging,
            "marts_models": generated_marts,
            "metrics_count": len(all_semantic_metrics),
            "status": "SUCCESS"
        }

    def update_profiles_schema(self, new_schema: str):
        """Cập nhật tên schema/database trong file profiles.yml."""
        prof_path = os.path.join(self.dbt_dir, "profiles.yml")
        if not os.path.exists(prof_path):
            return

        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Thay thế dòng schema: ...
            updated = re.sub(
                r"schema:\s*.*",
                f"schema: {new_schema}",
                content
            )

            with open(prof_path, "w", encoding="utf-8") as f:
                f.write(updated)
        except Exception as e:
            logger.warning(f"Không thể cập nhật profiles.yml: {e}")
