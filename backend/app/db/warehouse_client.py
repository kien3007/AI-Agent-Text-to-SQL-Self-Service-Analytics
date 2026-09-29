"""
Warehouse Client Factory Module.
Cung cấp một điểm truy cập thống nhất (Unified Entry Point) cho tầng lưu trữ Data Warehouse:
- Hỗ trợ 'duckdb' (mặc định, local in-process, không cần Docker, tốc độ cao)
- Hỗ trợ 'doris' (Apache Doris MPP cluster qua MySQL wire protocol)
"""

import os
import logging
from typing import Union, Optional
from app.core.config import settings
from app.db.duckdb_client import DuckDBClient
from app.db.doris_client import DorisClient

logger = logging.getLogger("WarehouseClient")

_GLOBAL_WAREHOUSE_CLIENT = None


def get_warehouse_client(
    backend: Optional[str] = None,
    db_path: Optional[str] = None,
    **doris_kwargs
) -> Union[DuckDBClient, DorisClient]:
    """
    Factory khởi tạo Warehouse Client theo cấu hình WAREHOUSE_BACKEND.
    Mặc định: 'duckdb'.
    """
    global _GLOBAL_WAREHOUSE_CLIENT
    
    selected_backend = (backend or getattr(settings, "WAREHOUSE_BACKEND", "duckdb") or "duckdb").lower()

    if selected_backend == "duckdb":
        duck_path = db_path or getattr(settings, "DUCKDB_PATH", "./data/warehouse.duckdb")
        return DuckDBClient(db_path=duck_path)
    elif selected_backend == "doris":
        return DorisClient(**doris_kwargs)
    else:
        logger.warning(f"Backend '{selected_backend}' không rõ. Fallback về DuckDB.")
        return DuckDBClient(db_path=db_path)


# Alias WarehouseClient cho DuckDBClient mặc định
WarehouseClient = DuckDBClient
