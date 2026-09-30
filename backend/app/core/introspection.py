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
from pathlib import Path
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
            # 1. Lấy danh sách bảng và view từ DuckDB có lọc theo database_name/schema_name nếu có
            table_sql = """
                SELECT DISTINCT table_name FROM duckdb_tables 
                WHERE NOT internal AND (
                    LOWER(database_name) = LOWER(?) OR 
                    LOWER(schema_name) = LOWER(?)
                )
                UNION 
                SELECT DISTINCT view_name FROM duckdb_views 
                WHERE NOT internal AND (
                    LOWER(database_name) = LOWER(?) OR 
                    LOWER(schema_name) = LOWER(?)
                )
            """
            try:
                cur.execute(table_sql, (database_name, database_name, database_name, database_name))
                table_rows = cur.fetchall()
            except Exception:
                table_rows = []

            # Nếu không khớp tên database/schema cụ thể, fallback lấy tất cả bảng người dùng
            if not table_rows:
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
            if tables_dict:
                placeholders = ",".join("?" for _ in tables_dict)
                col_sql = f"""
                    SELECT table_name, column_name, data_type 
                    FROM duckdb_columns 
                    WHERE NOT internal AND table_name IN ({placeholders})
                    ORDER BY table_name, column_index
                """
                try:
                    cur.execute(col_sql, list(tables_dict.keys()))
                    col_rows = cur.fetchall()
                except Exception:
                    cur.execute("SELECT table_name, column_name, data_type FROM duckdb_columns WHERE NOT internal ORDER BY table_name")
                    col_rows = cur.fetchall()
            else:
                col_rows = []

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
            baseline_metrics = self.generate_baseline_metrics(tables_dict)

            return DomainConfig(
                domain_id=domain_key,
                display_name=domain_title,
                description=f"Domain {domain_title} được tự động trích xuất từ DuckDB",
                tables=tables_dict,
                relationships=inferred_rels,
                metrics=baseline_metrics
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
        baseline_metrics = self.generate_baseline_metrics(tables_dict)

        return DomainConfig(
            domain_id=domain_key,
            display_name=domain_title,
            description=f"Cấu hình tự động khám phá từ CSDL {database_name}",
            domain_keywords=domain_keywords,
            tables=tables_dict,
            relationships=relationships,
            metrics=baseline_metrics
        )

    def introspect_sqlalchemy(
        self,
        engine_or_url: Any,
        database_name: Optional[str] = None,
        domain_id: Optional[str] = None,
        display_name: Optional[str] = None,
        schema: Optional[str] = None
    ) -> DomainConfig:
        """
        Tự động khám phá schema qua SQLAlchemy Inspector cho PostgreSQL, MySQL, SQLite, MSSQL, vv.
        Hỗ trợ schema tùy chọn cho MSSQL/PostgreSQL (VD: schema='fmcg_sales', 'vietnam_ecommerce').
        """
        from sqlalchemy import create_engine, inspect
        if isinstance(engine_or_url, str):
            engine = create_engine(engine_or_url)
        elif hasattr(engine_or_url, "engine"):
            engine = engine_or_url.engine
        else:
            engine = engine_or_url

        inspector = inspect(engine)
        db_name = database_name or getattr(engine.url, "database", None) or "database"
        actual_domain_key = domain_id or (f"{schema}" if schema else db_name)
        domain_key = str(actual_domain_key).lower().replace("-", "_").replace(".", "_")
        domain_title = display_name or (f"{schema.replace('_', ' ').title()}" if schema else str(db_name).replace("_", " ").title())

        tables_dict: Dict[str, TableProfile] = {}
        relationships: List[RelationshipProfile] = []

        all_tables = inspector.get_table_names(schema=schema)
        try:
            views = inspector.get_view_names(schema=schema)
            all_tables.extend([v for v in views if v not in all_tables])
        except Exception:
            pass

        # Nếu không chỉ định schema và bảng ở default schema rỗng (như MSSQL multi-schema),
        # tự động tìm qua các business schemas
        if not all_tables and schema is None and any(d in engine.dialect.name.lower() for d in ("mssql", "sqlserver", "postgresql")):
            try:
                available_schemas = inspector.get_schema_names()
                system_schemas = {
                    "sys", "information_schema", "guest", "db_owner", "db_securityadmin",
                    "db_ddladmin", "db_backupoperator", "db_datareader", "db_datawriter",
                    "db_denydatareader", "db_denydatawriter", "cdc", "db_accessadmin", "pg_catalog"
                }
                business_schemas = [s for s in available_schemas if s.lower() not in system_schemas]
                if business_schemas:
                    for b_sch in business_schemas:
                        for bt in inspector.get_table_names(schema=b_sch):
                            all_tables.append(f"{b_sch}.{bt}")
            except Exception:
                pass

        for t_entry in all_tables:
            if "." in t_entry and schema is None:
                cur_schema, t_name = t_entry.split(".", 1)
            else:
                cur_schema = schema
                t_name = t_entry

            # Giữ nguyên schema prefix nếu không phải schema mặc định để truy vấn SQL trên MSSQL/PostgreSQL hợp lệ
            if cur_schema and cur_schema.lower() not in ("dbo", "public", "main", ""):
                full_table_key = f"{cur_schema}.{t_name}" if "." not in t_entry else t_entry
            else:
                full_table_key = t_entry

            columns_dict: Dict[str, ColumnProfile] = {}
            try:
                pk_constraint = inspector.get_pk_constraint(t_name, schema=cur_schema)
                pks = set(pk_constraint.get("constrained_columns", []) if pk_constraint else [])
            except Exception:
                pks = set()

            try:
                cols = inspector.get_columns(t_name, schema=cur_schema)
            except Exception:
                cols = []

            for col in cols:
                c_name = col["name"]
                c_type = str(col["type"])
                c_comment = col.get("comment") or ""
                is_pk = c_name in pks

                synonyms = [c_name.replace("_", " ")]
                if c_comment:
                    synonyms.append(c_comment)

                columns_dict[c_name] = ColumnProfile(
                    name=c_name,
                    vn_name=c_comment if c_comment else c_name.replace("_", " ").title(),
                    en_name=c_name.replace("_", " ").title(),
                    data_type=c_type.upper(),
                    description=c_comment or f"Cột {c_name} trong bảng {full_table_key}",
                    is_primary_key=is_pk,
                    is_partition_or_dist=False,
                    sample_values=[],
                    synonyms=list(set(synonyms))
                )

            tables_dict[full_table_key] = TableProfile(
                table_name=full_table_key,
                vn_name=t_name.replace("_", " ").title(),
                description=f"Bảng/View {full_table_key}",
                columns=columns_dict,
                primary_key=list(pks)
            )

            try:
                fks = inspector.get_foreign_keys(t_name, schema=cur_schema)
                for fk in fks:
                    ref_tbl = fk.get("referred_table")
                    constrained_cols = fk.get("constrained_columns", [])
                    ref_cols = fk.get("referred_columns", [])
                    if ref_tbl and constrained_cols and ref_cols:
                        from_table_full = full_table_key
                        ref_table_full = f"{cur_schema}.{ref_tbl}" if cur_schema and cur_schema.lower() not in ("dbo", "public", "main", "") and "." not in ref_tbl else ref_tbl
                        relationships.append(RelationshipProfile(
                            from_table=from_table_full,
                            from_column=constrained_cols[0],
                            to_table=ref_table_full,
                            to_column=ref_cols[0],
                            cardinality="N:1",
                            join_type="INNER",
                            weight=1.0,
                            description=f"FK: {from_table_full}.{constrained_cols[0]} -> {ref_table_full}.{ref_cols[0]}"
                        ))
            except Exception:
                pass

        if not relationships:
            relationships = self.infer_relationships_by_naming(tables_dict)

        domain_keywords = [domain_key] + [t.split(".")[-1].replace("_", " ") for t in tables_dict.keys()]
        baseline_metrics = self.generate_baseline_metrics(tables_dict)

        return DomainConfig(
            domain_id=domain_key,
            display_name=domain_title,
            description=f"Cấu hình tự động khám phá từ CSDL {db_name}{' (' + schema + ')' if schema else ''}",
            domain_keywords=domain_keywords,
            tables=tables_dict,
            relationships=relationships,
            metrics=baseline_metrics
        )

    def introspect_all_schemas(self, engine_or_url: Any) -> List[DomainConfig]:
        """
        Quét và sinh DomainConfig riêng biệt cho từng Business Schema trong CSDL đa schema (MSSQL/PostgreSQL).
        """
        from sqlalchemy import create_engine, inspect
        if isinstance(engine_or_url, str):
            engine = create_engine(engine_or_url)
        elif hasattr(engine_or_url, "engine"):
            engine = engine_or_url.engine
        else:
            engine = engine_or_url

        inspector = inspect(engine)
        system_schemas = {
            "sys", "information_schema", "guest", "db_owner", "db_securityadmin",
            "db_ddladmin", "db_backupoperator", "db_datareader", "db_datawriter",
            "db_denydatareader", "db_denydatawriter", "cdc", "db_accessadmin", "pg_catalog"
        }
        all_schemas = [s for s in inspector.get_schema_names() if s.lower() not in system_schemas]
        
        configs = []
        for s in all_schemas:
            tables = inspector.get_table_names(schema=s)
            if tables:
                cfg = self.introspect_sqlalchemy(
                    engine_or_url=engine,
                    schema=s,
                    domain_id=s,
                    display_name=s.replace("_", " ").title()
                )
                configs.append(cfg)
        return configs

    def introspect_any(
        self,
        target: Any,
        database_name: Optional[str] = None,
        domain_id: Optional[str] = None,
        display_name: Optional[str] = None,
        schema: Optional[str] = None
    ) -> DomainConfig:
        """
        Cổng khám phá CSDL vạn năng: Tự động phân loại target và gọi phương thức phù hợp.
        Target có thể là: JDBC URL, SQLAlchemy URL/Engine/Client, DuckDBClient, hoặc Connection object.
        """
        if isinstance(target, str):
            from app.db.warehouse_client import parse_jdbc_url
            target_parsed = parse_jdbc_url(target)
            lower_target = target_parsed.lower().strip()
            if any(lower_target.startswith(p) for p in ("postgresql://", "postgres://", "mysql://", "sqlite:///", "clickhouse://", "mssql://", "mssql+", "oracle://", "snowflake://")):
                return self.introspect_sqlalchemy(target_parsed, database_name, domain_id, display_name, schema=schema)
            if lower_target.endswith((".sqlite", ".sqlite3", ".db")):
                return self.introspect_sqlalchemy(f"sqlite:///{target}", database_name, domain_id, display_name, schema=schema)
            # Default to DuckDB
            import duckdb
            conn = duckdb.connect(target)
            self.connection = conn
            db_n = database_name or Path(target).stem
            return self.introspect_information_schema(db_n, domain_id, display_name)

        if hasattr(target, "engine"):
            return self.introspect_sqlalchemy(target.engine, database_name, domain_id, display_name)

        if hasattr(target, "get_connection"):
            conn = target.get_connection()
            self.connection = conn
            db_n = database_name or getattr(target, "db_path", "duckdb")
            if isinstance(db_n, str):
                db_n = Path(db_n).stem
            return self.introspect_information_schema(str(db_n), domain_id, display_name)

        return self.introspect_information_schema(database_name or "database", domain_id, display_name)

    def generate_baseline_metrics(self, tables_dict: Dict[str, TableProfile]) -> Dict[str, MetricProfile]:
        """
        Tự động tạo các metric cơ bản (COUNT, SUM, AVG) cho các bảng và cột số được khám phá.
        Đảm bảo domain mới luôn có Semantic Layer hoạt động ngay lập tức mà không bị rỗng.
        """
        metrics: Dict[str, MetricProfile] = {}
        target_num_types = ("INT", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "REAL", "INTEGER", "NUMBER")
        metric_keywords = ("price", "amount", "total", "revenue", "cost", "fee", "salary", "sales", "quantity", "score", "area", "balance", "budget", "gia", "tien", "luong", "doanh_thu")

        for t_name, t_prof in tables_dict.items():
            t_vn = t_prof.vn_name or t_name.replace("_", " ").title()

            # 1. Metric đếm số lượng bản ghi (Record Count)
            count_id = f"total_{t_name}"
            metrics[count_id] = MetricProfile(
                metric_id=count_id,
                vn_terms=[f"tổng số {t_vn}", f"số lượng {t_vn}", f"số {t_vn}", f"thống kê {t_vn}"],
                en_terms=[f"total {t_name}", f"{t_name} count", f"number of {t_name}"],
                sql_expression="COUNT(*)",
                description=f"Tổng số lượng bản ghi trong bảng {t_name}",
                depends_on_tables=[t_name],
                depends_on_columns=[]
            )

            # 2. Quét các cột số để tạo SUM và AVG
            numeric_cols = []
            for c_name, c_prof in t_prof.columns.items():
                d_type = (c_prof.data_type or "").upper()
                c_lower = c_name.lower()
                is_id = c_lower.endswith(("_id", "_guid", "uuid", "_code", "id")) or c_prof.is_primary_key
                if any(nt in d_type for nt in target_num_types) and not is_id:
                    numeric_cols.append((c_name, c_prof))

            for c_name, c_prof in numeric_cols:
                c_lower = c_name.lower()
                c_vn = c_prof.vn_name or c_name.replace("_", " ").title()
                is_priority = any(kw in c_lower for kw in metric_keywords)

                if is_priority or len(numeric_cols) <= 4:
                    # Tổng (SUM)
                    sum_id = f"total_{c_name}"
                    metrics[sum_id] = MetricProfile(
                        metric_id=sum_id,
                        vn_terms=[f"tổng {c_vn}", f"tổng số {c_vn}", f"doanh thu {c_vn}" if "rev" in c_lower else f"tổng cộng {c_vn}"],
                        en_terms=[f"total {c_name}", f"sum of {c_name}"],
                        sql_expression=f"ROUND(SUM({c_name}), 2)",
                        description=f"Tổng giá trị lũy kế của cột {c_name} trong bảng {t_name}",
                        depends_on_tables=[t_name],
                        depends_on_columns=[c_name]
                    )

                    # Trung bình (AVG)
                    avg_id = f"avg_{c_name}"
                    metrics[avg_id] = MetricProfile(
                        metric_id=avg_id,
                        vn_terms=[f"{c_vn} trung bình", f"trung bình {c_vn}", f"bình quân {c_vn}"],
                        en_terms=[f"average {c_name}", f"avg {c_name}", f"mean {c_name}"],
                        sql_expression=f"ROUND(AVG({c_name}), 2)",
                        description=f"Giá trị bình quân của cột {c_name} trong bảng {t_name}",
                        depends_on_tables=[t_name],
                        depends_on_columns=[c_name]
                    )

        return metrics

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
