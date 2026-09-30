"""
SQLAlchemy Generic Database Client.
Hỗ trợ kết nối và truy vấn đa cơ sở dữ liệu qua SQLAlchemy:
- PostgreSQL (postgresql://...)
- MySQL (mysql://...)
- SQLite (sqlite:///...)
- ClickHouse, Snowflake, SQL Server và bất kỳ dialect nào có SQLAlchemy driver.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
from app.db.base_client import BaseDatabaseClient

logger = logging.getLogger("SQLAlchemyClient")


class SQLAlchemyClient(BaseDatabaseClient):
    """Client CSDL linh hoạt hỗ trợ mọi hệ quản trị CSDL qua SQLAlchemy Engine."""

    def __init__(self, connection_url: str, default_schema: Optional[str] = None, **kwargs):
        self.connection_url = connection_url
        self.default_schema = default_schema
        self.engine = create_engine(connection_url, pool_pre_ping=True, **kwargs)
        self.dialect_name = self.engine.dialect.name.lower()

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """Lấy toàn bộ tên bảng và view trong database (hỗ trợ schema trong MSSQL/PostgreSQL)."""
        try:
            inspector = inspect(self.engine)
            target_schema = schema or self.default_schema
            tables = inspector.get_table_names(schema=target_schema)
            try:
                views = inspector.get_view_names(schema=target_schema)
                tables.extend([v for v in views if v not in tables])
            except Exception:
                pass

            # Nếu là MSSQL hoặc PostgreSQL mà chưa có bảng ở schema mặc định, tự động quét qua các business schemas
            if not tables and not target_schema and any(d in self.dialect_name for d in ("mssql", "sqlserver", "postgresql")):
                try:
                    all_schemas = inspector.get_schema_names()
                    system_schemas = {
                        "sys", "information_schema", "guest", "db_owner", "db_securityadmin",
                        "db_ddladmin", "db_backupoperator", "db_datareader", "db_datawriter",
                        "db_denydatareader", "db_denydatawriter", "cdc", "db_accessadmin", "pg_catalog"
                    }
                    business_schemas = [s for s in all_schemas if s.lower() not in system_schemas]
                    for s in business_schemas:
                        s_tables = inspector.get_table_names(schema=s)
                        tables.extend([f"{s}.{t}" for t in s_tables])
                except Exception:
                    pass

            return tables
        except Exception as e:
            logger.error(f"Lỗi lấy danh sách bảng qua SQLAlchemy: {e}")
            return []

    def execute_query(self, sql: str, max_rows: int = 1000) -> Tuple[List[str], List[Tuple]]:
        """Thực thi câu truy vấn SQL an toàn (chỉ đọc) và trả về (columns, rows)."""
        cleaned_sql = sql.strip().rstrip(";")
        with self.engine.connect() as conn:
            result = conn.execute(text(cleaned_sql))
            cols = list(result.keys())
            rows = result.fetchmany(max_rows)
            return cols, [tuple(r) for r in rows]

    def execute_query_dict(self, sql: str, max_rows: int = 1000) -> List[Dict[str, Any]]:
        """Thực thi truy vấn và trả về danh sách dictionary."""
        cleaned_sql = sql.strip().rstrip(";")
        with self.engine.connect() as conn:
            result = conn.execute(text(cleaned_sql))
            rows = result.mappings().fetchmany(max_rows)
            return [dict(r) for r in rows]

    def explain_query(self, sql: str) -> str:
        """Thực thi EXPLAIN kế hoạch truy vấn tương ứng dialect."""
        cleaned_sql = sql.strip().rstrip(";")
        if "mssql" in self.dialect_name:
            return "EXPLAIN plan is validated via SQLAlchemy connection."
        explain_cmd = f"EXPLAIN {cleaned_sql}"
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text(explain_cmd)).fetchall()
                lines = []
                for r in res:
                    lines.append(str(r[0]) if len(r) == 1 else " | ".join(str(v) for v in r))
                return "\n".join(lines)
        except Exception as e:
            return f"EXPLAIN not supported or failed: {e}"

    def get_distinct_categories(
        self,
        table_name: Optional[str] = None,
        categorical_columns: Optional[List[str]] = None,
        max_distinct: int = 50
    ) -> Dict[str, List[Any]]:
        """Trích xuất các giá trị phân loại thực tế cho các cột chuỗi (tương thích cả MSSQL TOP và PostgreSQL/MySQL LIMIT)."""
        distinct_vals: Dict[str, List[Any]] = {}
        tables = [table_name] if table_name else self.get_tables()
        if not tables:
            return distinct_vals

        inspector = inspect(self.engine)
        for t in tables[:5]:
            try:
                schema_part, actual_tbl = (t.split(".", 1) if "." in t else (self.default_schema, t))
                cols = inspector.get_columns(actual_tbl, schema=schema_part)
                target_cols = categorical_columns or [
                    c["name"] for c in cols 
                    if any(t_name in str(c["type"]).lower() for t_name in ("varchar", "text", "string", "char"))
                    and not c["name"].lower().endswith(("_id", "_guid", "uuid"))
                ]
                with self.engine.connect() as conn:
                    for col in target_cols[:5]:
                        if "mssql" in self.dialect_name:
                            q = text(f"SELECT DISTINCT TOP ({max_distinct}) [{col}] FROM [{schema_part}].[{actual_tbl}] WHERE [{col}] IS NOT NULL" if schema_part else f"SELECT DISTINCT TOP ({max_distinct}) [{col}] FROM [{actual_tbl}] WHERE [{col}] IS NOT NULL")
                        else:
                            q = text(f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL LIMIT {max_distinct}")
                        rows = conn.execute(q).fetchall()
                        vals = [r[0] for r in rows if r[0] is not None]
                        if vals:
                            distinct_vals[f"{t}.{col}"] = vals
            except Exception as e:
                logger.warning(f"Lỗi lấy categories cho bảng {t}: {e}")
        return distinct_vals

    def close(self):
        """Đóng connection pool."""
        self.engine.dispose()
