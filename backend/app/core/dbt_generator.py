"""
Autonomous dbt Auto-Adapter — Sinh dbt Pipeline Thật Từ DomainConfig.
Tạo toàn bộ cấu trúc dbt project chuẩn:
  - sources.yml       : khai báo nguồn dữ liệu gốc
  - staging/stg_*.sql : làm sạch và chuẩn hóa
  - staging/stg_*.yml : tests và metadata (vn_name, synonyms trong meta:)
  - marts/fct_*.sql   : tổng hợp theo thời gian
  - marts/metrics.yml : MetricFlow semantic metrics (ASCII name + meta.vn_terms)
Sau đó gọi `dbt compile` thật để sinh manifest.json.
"""

import os
import sys
import re
import subprocess
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, MetricProfile

logger = logging.getLogger("AutoDbtGenerator")


class AutoDbtGenerator:
    """
    Sinh dbt pipeline thật từ DomainConfig bất kỳ.
    Nguyên tắc tiếng Việt:
      - Tên model/metric: ASCII (tuân thủ MetricFlow identifier rules)
      - vn_name, synonyms, vn_terms: tiếng Việt → đặt trong meta: block
    """

    # Guardrail 1: Bảng kỹ thuật/rác bị bỏ qua
    BLACKLIST_TABLE_PATTERNS = [
        r"^log_", r"_log$", r"^audit_", r"_audit$", r"^temp_", r"^tmp_",
        r"^session_", r"_session$", r"^cache_", r"_cache$",
        r"^alembic_", r"^flyway_", r"^schema_migrations$", r"^sysdiagrams$",
        r"^MSreplication_", r"^sys_",
    ]

    # Guardrail 2: Ưu tiên timestamp theo vòng đời giao dịch
    TIMESTAMP_PRIORITY = [
        (r"(delivered|completed|success|finished)_at", 100),
        (r"(paid|settled|disbursed)_at", 90),
        (r"(published|posted|approved)_at", 80),
        (r"(shipped|dispatched)_at", 70),
        (r"(order|transaction|invoice)_date", 60),
        (r"(created|inserted|registered)_at", 50),
        (r"(date|time|timestamp|year|month)", 40),
    ]

    def __init__(self, dbt_dir: Optional[str] = None):
        if dbt_dir:
            self.dbt_dir = os.path.abspath(dbt_dir)
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "infra"))
            self.dbt_dir = os.path.join(base, "dbt")

        self.models_dir  = os.path.join(self.dbt_dir, "models")
        self.staging_dir = os.path.join(self.models_dir, "staging")
        self.marts_dir   = os.path.join(self.models_dir, "marts")
        self.target_dir  = os.path.join(self.dbt_dir, "target")

    # =========================================================================
    # 1. HELPERS
    # =========================================================================

    def is_ignorable_table(self, table_name: str) -> bool:
        tbl = table_name.lower().split(".")[-1]  # strip schema prefix
        return any(re.search(p, tbl) for p in self.BLACKLIST_TABLE_PATTERNS)

    def _safe_name(self, name: str) -> str:
        """Chuyển tên bất kỳ thành ASCII identifier hợp lệ cho dbt."""
        # Giữ ký tự alphanum + underscore, bỏ schema prefix
        base = name.split(".")[-1]
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", base).lower().strip("_")
        if safe and safe[0].isdigit():
            safe = "t_" + safe
        return safe or "unknown"

    def categorize_columns(self, table: TableProfile) -> Dict[str, Any]:
        pks, fks, time_cols, metric_cols, dim_cols = [], [], [], [], []

        for c_name, col in table.columns.items():
            nl = c_name.lower()
            dt = (col.data_type or "").lower()
            base_nl = nl.split(".")[-1]

            if col.is_primary_key or base_nl in ("id",) or base_nl == f"{self._safe_name(table.table_name)}_id":
                pks.append(c_name)
            elif col.foreign_key or (base_nl.endswith("_id") and base_nl != "id"):
                fks.append(c_name)

            is_time = any(t in dt for t in ["date", "time", "timestamp", "datetime"]) or \
                      any(k in base_nl for k in ["_at", "_date", "date_", "timestamp", "year", "month"])
            if is_time:
                score = 10
                for pat, s in self.TIMESTAMP_PRIORITY:
                    if re.search(pat, base_nl):
                        score = max(score, s)
                time_cols.append((c_name, score))

            is_num = any(n in dt for n in ["int", "decimal", "float", "double", "numeric", "real", "money", "bigint"])
            if is_num and c_name not in pks and c_name not in fks and not is_time:
                metric_cols.append(c_name)

            if c_name not in pks and c_name not in fks and not is_time and c_name not in metric_cols:
                dim_cols.append(c_name)

        time_cols.sort(key=lambda x: x[1], reverse=True)
        return {
            "primary_keys": pks,
            "foreign_keys": fks,
            "time_columns": [c[0] for c in time_cols],
            "metric_columns": metric_cols,
            "dimension_columns": dim_cols,
        }

    # =========================================================================
    # 2. SOURCES.YML — Khai báo nguồn raw tables
    # =========================================================================

    def _generate_sources_yml(self, domain_config: DomainConfig, schema: str) -> str:
        """Sinh sources.yml khai báo tất cả bảng nguồn của domain."""
        tables_list = []
        for t_name, tbl in domain_config.tables.items():
            if self.is_ignorable_table(t_name):
                continue
            raw_name = t_name.split(".")[-1]  # tên bảng thực trong DB
            entry = {
                "name": raw_name,
                "description": tbl.description or f"Bảng nguồn {raw_name}",
                "meta": {
                    "vn_name": tbl.vn_name or raw_name,
                }
            }
            tables_list.append(entry)

        sources_dict = {
            "version": 2,
            "sources": [{
                "name": domain_config.domain_id,
                "schema": schema,
                "description": f"Nguồn dữ liệu gốc cho domain {domain_config.display_name}",
                "tables": tables_list
            }]
        }
        return yaml.dump(sources_dict, allow_unicode=True, sort_keys=False)

    # =========================================================================
    # 3. STAGING MODEL
    # =========================================================================

    def generate_staging_model(
        self,
        table: TableProfile,
        domain_id: str,
        categories: Dict[str, Any],
        db_dialect: str = "default"
    ) -> Tuple[str, str]:
        """Sinh stg_*.sql và stg_*.yml cho một bảng."""
        raw_name = table.table_name.split(".")[-1]
        safe     = self._safe_name(raw_name)
        stg_name = f"stg_{safe}"
        pk       = categories["primary_keys"][0] if categories["primary_keys"] else None

        # ── SQL ──────────────────────────────────────────────────────────────
        col_selects = []
        for c_name, col in table.columns.items():
            dt = (col.data_type or "").upper()
            bare = c_name.split(".")[-1]
            if any(t in dt for t in ["VARCHAR", "NVARCHAR", "TEXT", "CHAR", "NCHAR"]):
                if db_dialect.lower() in ("sqlserver", "mssql"):
                    col_selects.append(f"        TRIM(CAST({bare} AS VARCHAR(255))) AS {bare}")
                else:
                    col_selects.append(f"        TRIM(CAST({bare} AS VARCHAR)) AS {bare}")
            elif any(t in dt for t in ["DATETIME", "DATE", "TIMESTAMP"]):
                col_selects.append(f"        CAST({bare} AS DATE) AS {bare}")
            elif any(t in dt for t in ["INT", "DECIMAL", "FLOAT", "MONEY", "NUMERIC", "BIGINT"]):
                col_selects.append(f"        COALESCE({bare}, 0) AS {bare}")
            else:
                col_selects.append(f"        {bare}")

        where_clause = f"\n    WHERE {pk.split('.')[-1]} IS NOT NULL" if pk else ""
        select_clause = ",\n".join(col_selects)

        sql = f"""{{{{ config(materialized='view') }}}}

WITH source AS (
    SELECT * FROM {{{{ source('{domain_id}', '{raw_name}') }}}}
),
cleaned AS (
    SELECT
{select_clause}
    FROM source{where_clause}
)
SELECT * FROM cleaned
"""

        # ── YAML ─────────────────────────────────────────────────────────────
        cols_yaml = []
        for c_name, col in table.columns.items():
            bare = c_name.split(".")[-1]
            c_entry: Dict[str, Any] = {
                "name": bare,
                "description": col.description or col.vn_name or bare,
                "meta": {
                    "vn_name": col.vn_name or bare,
                    "synonyms": col.synonyms or [],
                }
            }
            if pk and bare == pk.split(".")[-1]:
                c_entry["tests"] = ["unique", "not_null"]
            cols_yaml.append(c_entry)

        yml_dict = {
            "version": 2,
            "models": [{
                "name": stg_name,
                "description": table.description or f"Bảng staging từ {raw_name}",
                "meta": {
                    "vn_name": table.vn_name or raw_name,
                    "domain": domain_id,
                },
                "columns": cols_yaml
            }]
        }
        return sql, yaml.dump(yml_dict, allow_unicode=True, sort_keys=False)

    # =========================================================================
    # 4. MARTS MODEL + METRICS
    # =========================================================================

    def generate_marts_model(
        self,
        table: TableProfile,
        domain_id: str,
        categories: Dict[str, Any],
        db_dialect: str = "default",
    ) -> Optional[Tuple[str, str, List[Dict[str, Any]]]]:
        """Sinh fct_*.sql, fct_*.yml và danh sách MetricFlow metrics."""
        time_cols   = categories["time_columns"]
        metric_cols = categories["metric_columns"]
        dim_cols    = categories["dimension_columns"]

        if not time_cols or not metric_cols:
            return None

        raw_name  = table.table_name.split(".")[-1]
        safe      = self._safe_name(raw_name)
        stg_name  = f"stg_{safe}"
        fct_name  = f"fct_{safe}_summary"
        best_time = time_cols[0].split(".")[-1]
        sel_dims  = [d.split(".")[-1] for d in dim_cols[:3]]

        # ── SQL ──────────────────────────────────────────────────────────────
        dim_selects = "".join(f"    {d},\n" for d in sel_dims)
        metric_lines = []
        semantic_metrics: List[Dict[str, Any]] = []

        # Phát hiện cặp price × quantity
        has_price = any("price" in m.lower() or "amount" in m.lower() or "tien" in m.lower() for m in metric_cols)
        has_qty   = any("quantity" in m.lower() or "qty" in m.lower() or "count" in m.lower() for m in metric_cols)
        if has_price and has_qty:
            p_col = next(m for m in metric_cols if "price" in m.lower() or "amount" in m.lower() or "tien" in m.lower())
            q_col = next(m for m in metric_cols if "quantity" in m.lower() or "qty" in m.lower() or "count" in m.lower())
            pb = p_col.split(".")[-1]; qb = q_col.split(".")[-1]
            metric_lines.append(f"    ROUND(SUM({pb} * {qb}), 2) AS total_gross_revenue,")
            semantic_metrics.append({
                "name": f"total_gross_revenue_{safe}",
                "vn_label": f"Tổng Doanh Thu Gộp ({table.vn_name or raw_name})",
                "vn_terms": ["tổng doanh thu", "gmv", "doanh thu gộp"],
                "sql": f"SUM({pb} * {qb})",
                "model": fct_name,
            })

        for m_col in metric_cols[:4]:
            mb = m_col.split(".")[-1]
            metric_lines.append(f"    ROUND(SUM({mb}), 2) AS total_{mb},")
            metric_lines.append(f"    ROUND(AVG({mb}), 2) AS avg_{mb},")
            semantic_metrics.append({
                "name": f"total_{mb}_{safe}",
                "vn_label": f"Tổng {mb} ({table.vn_name or raw_name})",
                "vn_terms": [f"tổng {mb}", f"sum {mb}"],
                "sql": f"SUM({mb})",
                "model": fct_name,
            })
            semantic_metrics.append({
                "name": f"avg_{mb}_{safe}",
                "vn_label": f"Trung Bình {mb} ({table.vn_name or raw_name})",
                "vn_terms": [f"trung bình {mb}", f"average {mb}"],
                "sql": f"AVG({mb})",
                "model": fct_name,
            })

        metric_block = "\n".join(metric_lines).rstrip(",")

        if db_dialect.lower() in ("sqlserver", "mssql"):
            month_expr = f"DATEFROMPARTS(YEAR({best_time}), MONTH({best_time}), 1)"
        else:
            month_expr = f"DATE_TRUNC('month', {best_time})"

        group_cols = [month_expr] + sel_dims
        group_by = ", ".join(group_cols)

        sql = f"""{{{{ config(materialized='table') }}}}

SELECT
    {month_expr} AS report_month,
{dim_selects}    COUNT(*) AS total_records,
{metric_block}
FROM {{{{ ref('{stg_name}') }}}}
WHERE {best_time} IS NOT NULL
GROUP BY {group_by}
ORDER BY report_month DESC
"""

        # ── YAML ─────────────────────────────────────────────────────────────
        yml_cols = [
            {"name": "report_month", "description": "Tháng thống kê (YYYY-MM-01)"},
            {"name": "total_records", "description": "Tổng số bản ghi trong tháng"},
        ]
        for d in sel_dims:
            yml_cols.append({"name": d, "description": f"Chiều phân loại {d}"})
        for m in semantic_metrics:
            yml_cols.append({"name": m["name"].split("_" + safe)[0], "description": m["vn_label"]})

        yml_dict = {
            "version": 2,
            "models": [{
                "name": fct_name,
                "description": f"Bảng Data Mart tổng hợp theo tháng cho {table.vn_name or raw_name}",
                "meta": {"vn_name": f"Báo cáo {table.vn_name or raw_name}", "domain": domain_id},
                "columns": yml_cols,
            }]
        }
        return sql, yaml.dump(yml_dict, allow_unicode=True, sort_keys=False), semantic_metrics

    # =========================================================================
    # 5. METRICS.YML — MetricFlow Semantic Layer
    # =========================================================================

    def _generate_metrics_yml(
        self,
        all_metrics: List[Dict[str, Any]],
        domain_id: str,
    ) -> str:
        """
        Sinh metrics.yml chuẩn MetricFlow.
        Quy tắc tiếng Việt:
          - name:  ASCII identifier bắt buộc
          - label: tiếng Việt (hiển thị UI)
          - meta.vn_terms: tiếng Việt → AI Agent đọc để map câu hỏi
        """
        metrics_list = []
        for m in all_metrics:
            metrics_list.append({
                "name": m["name"],           # ASCII — MetricFlow bắt buộc
                "label": m["vn_label"],      # tiếng Việt — dbt Cloud UI
                "description": m["vn_label"],
                "type": "simple",
                "type_params": {
                    "measure": {
                        "name": m["name"],
                        "agg": "sum" if m["sql"].upper().startswith("SUM") else "average",
                        "expr": m["sql"],
                    }
                },
                "meta": {
                    "vn_terms": m["vn_terms"],   # tiếng Việt — AI Agent đọc
                    "domain": domain_id,
                }
            })

        yml_dict = {"version": 2, "metrics": metrics_list}
        return yaml.dump(yml_dict, allow_unicode=True, sort_keys=False)

    # =========================================================================
    # 6. ORCHESTRATION — Sinh toàn bộ pipeline
    # =========================================================================

    def generate_domain_dbt(
        self,
        domain_config: DomainConfig,
        db_schema: Optional[str] = None,
        db_dialect: str = "sqlserver",
        run_compile: bool = True,
    ) -> Dict[str, Any]:
        """
        Sinh toàn bộ dbt project cho một DomainConfig:
        1. sources.yml
        2. staging/stg_*.sql + stg_*.yml
        3. marts/fct_*.sql + fct_*.yml
        4. marts/metrics.yml (MetricFlow)
        5. Chạy `dbt compile` thật → sinh manifest.json
        """
        domain_id = domain_config.domain_id
        schema    = db_schema or domain_id

        dom_stg_dir   = os.path.join(self.staging_dir, domain_id)
        dom_marts_dir = os.path.join(self.marts_dir, domain_id)
        os.makedirs(dom_stg_dir, exist_ok=True)
        os.makedirs(dom_marts_dir, exist_ok=True)

        generated_staging = []
        generated_marts   = []
        all_metrics: List[Dict[str, Any]] = []

        # ── sources.yml ──────────────────────────────────────────────────────
        sources_content = self._generate_sources_yml(domain_config, schema)
        sources_path = os.path.join(dom_stg_dir, "sources.yml")
        with open(sources_path, "w", encoding="utf-8") as f:
            f.write(sources_content)
        logger.info(f"[dbt] Đã sinh sources.yml tại {sources_path}")

        # ── Duyệt từng bảng ─────────────────────────────────────────────────
        for t_name, table in domain_config.tables.items():
            if self.is_ignorable_table(t_name):
                logger.info(f"[dbt] Bỏ qua bảng kỹ thuật: {t_name}")
                continue

            categories = self.categorize_columns(table)
            safe = self._safe_name(t_name)

            # Staging
            stg_sql, stg_yml = self.generate_staging_model(table, domain_id, categories, db_dialect)
            sql_path = os.path.join(dom_stg_dir, f"stg_{safe}.sql")
            yml_path = os.path.join(dom_stg_dir, f"stg_{safe}.yml")
            with open(sql_path, "w", encoding="utf-8") as f: f.write(stg_sql)
            with open(yml_path, "w", encoding="utf-8") as f: f.write(stg_yml)
            generated_staging.append(f"stg_{safe}")

            # Marts
            mart_res = self.generate_marts_model(table, domain_id, categories, db_dialect=db_dialect)
            if mart_res:
                mart_sql, mart_yml, metrics = mart_res
                fct_name = f"fct_{safe}_summary"
                fct_sql_path = os.path.join(dom_marts_dir, f"{fct_name}.sql")
                fct_yml_path = os.path.join(dom_marts_dir, f"{fct_name}.yml")
                with open(fct_sql_path, "w", encoding="utf-8") as f: f.write(mart_sql)
                with open(fct_yml_path, "w", encoding="utf-8") as f: f.write(mart_yml)
                generated_marts.append(fct_name)
                all_metrics.extend(metrics)

        # ── metrics.yml (MetricFlow Semantic Layer) ──────────────────────────
        manifest_path = None
        if all_metrics:
            metrics_yml = self._generate_metrics_yml(all_metrics, domain_id)
            metrics_path = os.path.join(dom_marts_dir, "metrics.yml")
            with open(metrics_path, "w", encoding="utf-8") as f:
                f.write(metrics_yml)
            logger.info(f"[dbt] Đã sinh metrics.yml với {len(all_metrics)} chỉ số.")

            # Đồng bộ metrics tự sinh vào domain_config
            for m in all_metrics:
                m_id = m["name"]
                domain_config.metrics[m_id] = MetricProfile(
                    metric_id=m_id,
                    vn_terms=m.get("vn_terms", [m.get("vn_label", m_id)]),
                    sql_expression=m.get("sql", ""),
                    description=m.get("vn_label", "")
                )

        # ── Chạy dbt compile thật ────────────────────────────────────────────
        compile_result = None
        if run_compile:
            compile_result, manifest_path = self.run_dbt_compile()

        return {
            "status": "SUCCESS",
            "domain_id": domain_id,
            "staging_models": generated_staging,
            "marts_models": generated_marts,
            "metrics_count": len(all_metrics),
            "metrics": [m["name"] for m in all_metrics],
            "dbt_compile": compile_result,
            "manifest_path": manifest_path,
        }

    # =========================================================================
    # 7. CHẠY DBT COMPILE THẬT
    # =========================================================================

    def _resolve_dbt_cmd(self) -> List[str]:
        """Tìm đường dẫn dbt executable hoặc gọi qua python module."""
        import shutil
        dbt_exe = shutil.which("dbt")
        if dbt_exe:
            return [dbt_exe]
        venv_scripts = os.path.join(sys.prefix, "Scripts", "dbt.exe")
        if os.path.exists(venv_scripts):
            return [venv_scripts]
        workspace_dbt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".venv", "Scripts", "dbt.exe"))
        if os.path.exists(workspace_dbt):
            return [workspace_dbt]
        return [sys.executable, "-m", "dbt.cli.main"]

    def run_dbt_compile(self, extra_args: Optional[List[str]] = None) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Chạy `dbt compile` thật sự bằng subprocess.
        Trả về (kết quả, đường dẫn manifest.json).
        """
        profiles_dir = self.dbt_dir
        manifest_path = os.path.join(self.target_dir, "manifest.json")

        cmd = self._resolve_dbt_cmd() + [
            "compile",
            "--project-dir", self.dbt_dir,
            "--profiles-dir", profiles_dir,
            "--no-version-check",
        ]
        if extra_args:
            cmd.extend(extra_args)

        logger.info(f"[dbt] Chạy: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.dbt_dir,
                timeout=300,  # 5 phút timeout
            )
            success = proc.returncode == 0
            result = {
                "success": success,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-3000:] if proc.stdout else "",  # tail 3k chars
                "stderr": proc.stderr[-2000:] if proc.stderr else "",
                "manifest_generated": os.path.exists(manifest_path),
            }
            if success:
                logger.info("[dbt] compile thành công — manifest.json đã được cập nhật.")
            else:
                logger.error(f"[dbt] compile thất bại:\n{proc.stderr}")
            return result, manifest_path if success else None

        except FileNotFoundError:
            msg = "dbt CLI chưa được cài đặt. Chạy: pip install dbt-core"
            logger.error(f"[dbt] {msg}")
            return {"success": False, "error": msg, "manifest_generated": False}, None

        except subprocess.TimeoutExpired:
            msg = "dbt compile quá 5 phút — timeout."
            logger.error(f"[dbt] {msg}")
            return {"success": False, "error": msg, "manifest_generated": False}, None

        except Exception as e:
            logger.error(f"[dbt] Lỗi không xác định: {e}")
            return {"success": False, "error": str(e), "manifest_generated": False}, None

    def run_dbt_test(self, model_selector: Optional[str] = None) -> Dict[str, Any]:
        """Chạy `dbt test` để kiểm tra data quality tests."""
        profiles_dir = self.dbt_dir
        cmd = self._resolve_dbt_cmd() + [
            "test",
            "--project-dir", self.dbt_dir,
            "--profiles-dir", profiles_dir,
            "--no-version-check",
        ]
        if model_selector:
            cmd += ["--select", model_selector]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.dbt_dir, timeout=600)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-3000:],
                "stderr": proc.stderr[-2000:],
            }
        except FileNotFoundError:
            return {"success": False, "error": "dbt CLI chưa được cài đặt."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_dbt_run(self, model_selector: Optional[str] = None) -> Dict[str, Any]:
        """Chạy `dbt run` để materialize models vào database."""
        profiles_dir = self.dbt_dir
        cmd = self._resolve_dbt_cmd() + [
            "run",
            "--project-dir", self.dbt_dir,
            "--profiles-dir", profiles_dir,
            "--no-version-check",
        ]
        if model_selector:
            cmd += ["--select", model_selector]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.dbt_dir, timeout=600)
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-3000:],
                "stderr": proc.stderr[-2000:],
            }
        except FileNotFoundError:
            return {"success": False, "error": "dbt CLI chưa được cài đặt."}
        except Exception as e:
            return {"success": False, "error": str(e)}
