"""
Warehouse Client Factory & Multi-Database Router Module.
Cung cấp Client kết nối và định tuyến đa cơ sở dữ liệu (Multi-Database Router):
- Hỗ trợ DuckDB (embedded analytics warehouse)
- Hỗ trợ PostgreSQL, MySQL, SQLite, ClickHouse qua SQLAlchemy
- Tự động phát hiện và định tuyến linh hoạt theo URL kết nối, đường dẫn file, hoặc domain_id.
"""

import os
import logging
from typing import Optional, Dict, Any, Union, List
from pathlib import Path
from app.core.config import settings
from app.db.base_client import BaseDatabaseClient
from app.db.duckdb_client import DuckDBClient
from app.db.sqlalchemy_client import SQLAlchemyClient

logger = logging.getLogger("WarehouseClient")


def parse_jdbc_url(jdbc_url: str) -> str:
    """Chuyển đổi JDBC connection URL (SQL Server, MySQL, Postgres) sang SQLAlchemy URL."""
    clean = jdbc_url.strip()
    clean_l = clean.lower()
    from urllib.parse import quote_plus

    if clean_l.startswith("jdbc:sqlserver://"):
        main_part = clean[len("jdbc:sqlserver://"):]
        parts = main_part.split(";")
        host_port = parts[0]
        params = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip().lower()] = v.strip()
        
        user = params.get("user") or params.get("username", "")
        password = params.get("password", "")
        db_name = params.get("databasename") or params.get("database", "")
        
        auth = f"{quote_plus(user)}:{quote_plus(password)}@" if user else ""
        return f"mssql+pymssql://{auth}{host_port}/{db_name}"

    elif clean_l.startswith("jdbc:postgresql://"):
        return "postgresql://" + clean[len("jdbc:postgresql://"):]
    elif clean_l.startswith("jdbc:mysql://"):
        return "mysql+pymysql://" + clean[len("jdbc:mysql://"):]

    return clean


class MultiDBWarehouseRouter:
    """
    Bộ định tuyến đa cơ sở dữ liệu (Multi-Database Router).
    Quản lý danh sách kết nối tới các database/schema khác nhau:
    - Định tuyến theo connection URL (postgresql://, mysql://, sqlite://, mssql://, jdbc:...)
    - Định tuyến theo tên database hoặc domain_id
    - Tự động phát hiện database files (.duckdb, .sqlite, .db)
    - Cache và tái sử dụng connection an toàn
    """

    def __init__(self):
        self._clients: Dict[str, BaseDatabaseClient] = {}
        self._default_path = getattr(settings, "DUCKDB_PATH", "./data/warehouse.duckdb")

    def create_client_from_source(self, source: Union[str, BaseDatabaseClient]) -> BaseDatabaseClient:
        """Tự động suy luận loại client từ chuỗi URL, đường dẫn hoặc object."""
        if isinstance(source, BaseDatabaseClient):
            return source

        src_str = parse_jdbc_url(str(source).strip())
        lower_src = src_str.lower()

        # SQLAlchemy URL patterns
        if any(lower_src.startswith(prefix) for prefix in (
            "postgresql://", "postgres://", "mysql://", "sqlite:///",
            "clickhouse://", "mssql://", "mssql+", "oracle://", "snowflake://"
        )):
            return SQLAlchemyClient(connection_url=src_str)

        # SQLite file
        if lower_src.endswith((".sqlite", ".sqlite3", ".db")):
            abs_path = str(Path(src_str).resolve()).replace("\\", "/")
            return SQLAlchemyClient(connection_url=f"sqlite:///{abs_path}")

        # DuckDB file or memory
        return DuckDBClient(db_path=src_str)

    def register_database(
        self,
        db_key: str,
        client_or_url: Union[str, BaseDatabaseClient]
    ) -> BaseDatabaseClient:
        """Đăng ký một database kết nối vào router."""
        client = self.create_client_from_source(client_or_url)
        self._clients[db_key.lower().strip()] = client
        logger.info(f"Đã đăng ký database '{db_key}' (Type: {type(client).__name__})")
        return client

    def unregister_database(self, db_key: str) -> bool:
        """Hủy đăng ký một database."""
        key = db_key.lower().strip()
        if key in self._clients:
            client = self._clients.pop(key)
            if hasattr(client, "close"):
                client.close()
            return True
        return False

    def list_databases(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các database đã đăng ký kèm thông tin bảng."""
        result = []
        for key, client in self._clients.items():
            if key.startswith("_"):
                continue
            tables = client.get_tables()
            result.append({
                "database_key": key,
                "client_type": type(client).__name__,
                "tables_count": len(tables),
                "tables": tables
            })
        return result

    def get_client(
        self,
        db_name: Optional[str] = None,
        domain_id: Optional[str] = None,
        db_path: Optional[str] = None,
        connection_url: Optional[str] = None,
        **kwargs: Any
    ) -> BaseDatabaseClient:
        """
        Lấy client kết nối tương ứng với database hoặc domain.
        Thứ tự ưu tiên:
        1. connection_url cụ thể
        2. db_path cụ thể
        3. Tên database (db_name hoặc kwargs.get('database'))
        4. domain_id
        5. Default warehouse database
        """
        if connection_url:
            norm_url = connection_url.strip()
            if norm_url not in self._clients:
                self._clients[norm_url] = self.create_client_from_source(norm_url)
            return self._clients[norm_url]

        if db_path:
            norm_path = str(Path(db_path).resolve())
            if norm_path not in self._clients:
                self._clients[norm_path] = self.create_client_from_source(norm_path)
            return self._clients[norm_path]

        target_name = db_name or kwargs.get("database") or domain_id

        if target_name:
            key = str(target_name).lower().strip()
            if key in self._clients:
                return self._clients[key]

            # Kiểm tra biến môi trường đặc thù: DB_URL_{KEY} hoặc DUCKDB_PATH_{KEY}
            env_url = os.getenv(f"DB_URL_{key.upper()}")
            if env_url:
                client = self.create_client_from_source(env_url)
                self._clients[key] = client
                return client

            env_path = os.getenv(f"DUCKDB_PATH_{key.upper()}")
            if env_path:
                client = DuckDBClient(db_path=env_path)
                self._clients[key] = client
                return client

            # Kiểm tra xem có file data/{key}.duckdb hoặc data/{key}.db tồn tại không
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            for ext in [".duckdb", ".db", ".sqlite"]:
                cand = project_root / "data" / f"{key}{ext}"
                if cand.exists():
                    client = self.create_client_from_source(str(cand))
                    self._clients[key] = client
                    return client

        # Mặc định fallback về warehouse client chung
        default_key = "_default"
        if default_key not in self._clients:
            self._clients[default_key] = DuckDBClient(db_path=self._default_path)
        return self._clients[default_key]


_ROUTER = MultiDBWarehouseRouter()


def get_warehouse_client(
    db_path: Optional[str] = None,
    db_name: Optional[str] = None,
    domain_id: Optional[str] = None,
    connection_url: Optional[str] = None,
    **kwargs
) -> BaseDatabaseClient:
    """Factory khởi tạo hoặc định tuyến Warehouse Client."""
    return _ROUTER.get_client(
        db_name=db_name,
        domain_id=domain_id,
        db_path=db_path,
        connection_url=connection_url,
        **kwargs
    )


# Alias tương thích ngược
WarehouseClient = DuckDBClient
