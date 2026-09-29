"""
Database Introspector (Bộ Tự Động Khám Phá Schema CSDL - Automated Schema Crawler).
Chịu trách nhiệm:
1. Quét CSDL qua information_schema (DuckDB, MySQL, SQLite) để lấy danh sách bảng, cột, kiểu dữ liệu, comment.
2. Tự động phát hiện khóa chính (PK) và khóa ngoại (FK) từ ràng buộc CSDL hoặc quy ước đặt tên (*_id -> table.id).
3. Xuất kết quả tự động thành đối tượng DomainConfig hoặc lưu thành bộ cấu hình YAML (domain.yaml, schema.yaml, metrics.yaml).
"""

import os
import sys
import re
from typing import Dict, Any, List, Optional, Tuple, Set

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, RelationshipProfile, MetricProfile


class DatabaseIntrospector:
    """
    Tự động khám phá cấu trúc CSDL và sinh cấu hình DomainConfig chuẩn hóa.
    """

    def __init__(self, connection: Optional[Any] = None):
        self.connection = connection

    def introspect_information_schema(
        self,
        database_name: str,
        domain_id: Optional[str] = None,
        display_name: Optional[str] = None,
        cursor: Optional[Any] = None
    ) -> DomainConfig:
        """
        Quét schema CSDL từ information_schema.tables, columns và key_column_usage.
        """
        cur = cursor or (self.connection.cursor() if self.connection else None)
        if not cur:
            raise ValueError("Cần cung cấp database connection hoặc cursor để thực hiện introspection.")

        domain_key = domain_id or database_name.lower().replace("-", "_")
        domain_title = display_name or database_name.replace("_", " ").title()

        is_duckdb = "duckdb" in type(self.connection).__module__.lower() if self.connection else False

        if is_duckdb:
            # 1. Lấy danh sách bảng và view từ DuckDB
            cur.execute("SELECT table_name FROM duckdb_tables WHERE NOT internal UNION SELECT view_name FROM duckdb_views WHERE NOT internal")
            table_rows = cur.fetchall()
            tables_dict: Dict[str, TableProfile] = {}
            for row in table_rows:
                t_name = row[0]
                tables_dict[t_name] = TableProfile(
                    table_name=t_name,
                    vn_name=t_name.replace("_", " ").title(),
                    description=f"Bảng/View {t_name}",
                    columns={}
                )

            # 2. Lấy danh sách cột từ DuckDB
            cur.execute("SELECT table_name, column_name, data_type FROM duckdb_columns WHERE NOT internal ORDER BY table_name")
            col_rows = cur.fetchall()
            for row in col_rows:
                t_name, c_name, d_type = row[0], row[1], row[2]
                if t_name in tables_dict:
                    is_pk = (c_name.lower() in ("id", f"{t_name}_id", f"{t_name[:-1] if t_name.endswith('s') else t_name}_id"))
                    if is_pk:
                        tables_dict[t_name].primary_key.append(c_name)
                    synonyms = [c_name.replace("_", " ")]
                    col_profile = ColumnProfile(
                        name=c_name,
                        vn_name=c_name.replace("_", " ").title(),
                        data_type=d_type.upper(),
                        description=f"Cột {c_name} trong bảng {t_name}",
                        is_primary_key=is_pk,
                        synonyms=list(set(synonyms))
                    )
                    tables_dict[t_name].columns[c_name] = col_profile

            # 3. Tự động suy luận quan hệ từ quy ước đặt tên
            inferred_rels = self.infer_relationships_by_naming(tables_dict)
            return DomainConfig(
                domain_id=domain_key,
                display_name=domain_title,
                description=f"Domain {domain_title} được tự động trích xuất từ DuckDB",
                tables=tables_dict,
                relationships=inferred_rels,
                metrics={}
            )

        # 1. Lấy danh sách bảng và mô tả bảng (DuckDB / MySQL)
        cur.execute(
            """
            SELECT table_name, table_comment
            FROM information_schema.tables
            WHERE table_schema = %s
            """,
            (database_name,)
        )
        table_rows = cur.fetchall()
        tables_dict: Dict[str, TableProfile] = {}

        for row in table_rows:
            t_name = row[0] if isinstance(row, (list, tuple)) else row["table_name"]
            t_comment = (row[1] if isinstance(row, (list, tuple)) else row.get("table_comment")) or ""
            tables_dict[t_name] = TableProfile(
                table_name=t_name,
                vn_name=t_comment if t_comment else t_name,
                description=t_comment,
                columns={}
            )

        # 2. Lấy danh sách cột
        cur.execute(
            """
            SELECT table_name, column_name, data_type, column_comment, column_key
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (database_name,)
        )
        col_rows = cur.fetchall()

        for row in col_rows:
            if isinstance(row, (list, tuple)):
                t_name, c_name, d_type, c_comment, c_key = row[0], row[1], row[2], row[3] or "", row[4] or ""
            else:
                t_name = row["table_name"]
                c_name = row["column_name"]
                d_type = row["data_type"]
                c_comment = row.get("column_comment", "")
                c_key = row.get("column_key", "")

            if t_name in tables_dict:
                is_pk = (c_key == "PRI")
                if is_pk:
                    tables_dict[t_name].primary_key.append(c_name)

                # Sinh từ đồng nghĩa mặc định từ tên cột
                synonyms = [c_name.replace("_", " ")]
                if c_comment:
                    synonyms.append(c_comment)

                col_profile = ColumnProfile(
                    name=c_name,
                    vn_name=c_comment if c_comment else c_name.replace("_", " ").title(),
                    data_type=d_type.upper(),
                    description=c_comment or f"Cột {c_name} trong bảng {t_name}",
                    is_primary_key=is_pk,
                    synonyms=list(set(synonyms))
                )
                tables_dict[t_name].columns[c_name] = col_profile

        # 3. Lấy ràng buộc khóa ngoại chính thức (nếu có trong CSDL)
        relationships: List[RelationshipProfile] = []
        try:
            cur.execute(
                """
                SELECT table_name, column_name, referenced_table_name, referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = %s AND referenced_table_name IS NOT NULL
                """,
                (database_name,)
            )
            fk_rows = cur.fetchall()
            for r in fk_rows:
                if isinstance(r, (list, tuple)):
                    from_t, from_c, to_t, to_c = r[0], r[1], r[2], r[3]
                else:
                    from_t = r["table_name"]
                    from_c = r["column_name"]
                    to_t = r["referenced_table_name"]
                    to_c = r["referenced_column_name"]

                relationships.append(RelationshipProfile(
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    cardinality="N:1",
                    join_type="INNER",
                    weight=1.0
                ))
        except Exception:
            pass

        # 4. Tự động suy luận khóa ngoại logic nếu chưa có trong DB (Heuristic FK Inference)
        # Ví dụ: bảng orders có cột customer_id -> trỏ tới customers.id
        if not relationships:
            relationships = self.infer_relationships_by_naming(tables_dict)

        domain_keywords = [domain_key] + [t.replace("_", " ") for t in tables_dict.keys()]

        return DomainConfig(
            domain_id=domain_key,
            display_name=domain_title,
            description=f"Cấu hình tự động khám phá từ CSDL {database_name}",
            domain_keywords=domain_keywords,
            tables=tables_dict,
            relationships=relationships
        )

    def infer_relationships_by_naming(
        self,
        tables_dict: Dict[str, TableProfile]
    ) -> List[RelationshipProfile]:
        """
        Tự động suy luận quan hệ khóa ngoại dựa trên quy ước đặt tên:
        - Bảng orders có customer_id -> trỏ tới customers.id
        - Bảng order_items có product_id -> trỏ tới products.id
        """
        relationships: List[RelationshipProfile] = []
        all_table_names = set(tables_dict.keys())

        for from_t, t_profile in tables_dict.items():
            for c_name, c_profile in t_profile.columns.items():
                if c_name.endswith("_id") and not c_profile.is_primary_key:
                    target_candidate = c_name[:-3] # customer_id -> customer
                    # Thử dạng số nhiều (customer -> customers)
                    candidates = [target_candidate, f"{target_candidate}s", f"{target_candidate}es"]
                    for cand in candidates:
                        if cand in all_table_names and cand != from_t:
                            # Kiểm tra xem bảng đích có cột id hoặc target_candidate_id không
                            cand_cols = tables_dict[cand].columns
                            target_col = "id" if "id" in cand_cols else c_name
                            if target_col in cand_cols:
                                relationships.append(RelationshipProfile(
                                    from_table=from_t,
                                    from_column=c_name,
                                    to_table=cand,
                                    to_column=target_col,
                                    cardinality="N:1",
                                    join_type="INNER",
                                    weight=1.0,
                                    description=f"Suy luận tự động: {from_t}.{c_name} -> {cand}.{target_col}"
                                ))
                                break

        return relationships

    def export_to_yaml_folder(self, domain_config: DomainConfig, output_folder: str):
        """Xuất đối tượng DomainConfig ra bộ file cấu hình YAML chuẩn."""
        import yaml
        os.makedirs(output_folder, exist_ok=True)

        # 1. domain.yaml
        domain_dict = {
            "domain_id": domain_config.domain_id,
            "display_name": domain_config.display_name,
            "description": domain_config.description,
            "domain_keywords": domain_config.domain_keywords,
            "synonyms": domain_config.synonyms
        }
        with open(os.path.join(output_folder, "domain.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(domain_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # 2. schema.yaml
        tables_raw = {}
        for t_name, t_prof in domain_config.tables.items():
            cols_raw = {}
            for c_name, c_prof in t_prof.columns.items():
                cols_raw[c_name] = {
                    "name": c_prof.name,
                    "vn_name": c_prof.vn_name,
                    "en_name": c_prof.en_name,
                    "data_type": c_prof.data_type,
                    "description": c_prof.description,
                    "synonyms": c_prof.synonyms,
                    "is_partition_or_dist": c_prof.is_partition_or_dist
                }
            tables_raw[t_name] = {
                "table_name": t_prof.table_name,
                "vn_name": t_prof.vn_name,
                "description": t_prof.description,
                "primary_key": t_prof.primary_key,
                "partition_key": t_prof.partition_key,
                "columns": cols_raw
            }

        rels_raw = []
        for r in domain_config.relationships:
            rels_raw.append({
                "from_table": r.from_table,
                "from_column": r.from_column,
                "to_table": r.to_table,
                "to_column": r.to_column,
                "cardinality": r.cardinality,
                "join_type": r.join_type,
                "weight": r.weight
            })

        schema_dict = {"tables": tables_raw, "relationships": rels_raw}
        with open(os.path.join(output_folder, "schema.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(schema_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # 3. metrics.yaml
        metrics_raw = {}
        for m_id, m_prof in domain_config.metrics.items():
            metrics_raw[m_id] = {
                "metric_id": m_prof.metric_id,
                "vn_terms": m_prof.vn_terms,
                "en_terms": m_prof.en_terms,
                "sql_expression": m_prof.sql_expression,
                "description": m_prof.description,
                "depends_on_tables": m_prof.depends_on_tables,
                "depends_on_columns": m_prof.depends_on_columns
            }

        metrics_dict = {"metrics": metrics_raw, "segments": {}}
        with open(os.path.join(output_folder, "metrics.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(metrics_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
