"""
Warehouse Client Factory Module.
Cung cấp DuckDBClient là Data Warehouse engine của hệ thống.
"""

import logging
from typing import Optional
from app.core.config import settings
from app.db.duckdb_client import DuckDBClient

logger = logging.getLogger("WarehouseClient")

_GLOBAL_WAREHOUSE_CLIENT = None


def get_warehouse_client(
    db_path: Optional[str] = None,
    **kwargs
) -> DuckDBClient:
    """
    Factory khởi tạo Warehouse Client (DuckDB).
    """
    global _GLOBAL_WAREHOUSE_CLIENT
    duck_path = db_path or getattr(settings, "DUCKDB_PATH", "./data/warehouse.duckdb")
    return DuckDBClient(db_path=duck_path)


# Alias
WarehouseClient = DuckDBClient

