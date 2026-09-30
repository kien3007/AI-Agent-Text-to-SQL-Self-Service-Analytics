"""
Data Ingestion Service Module.
Chịu trách nhiệm trích xuất dữ liệu từ các CSDL nguồn (SQL Server, PostgreSQL, MySQL, SQLite...)
và nạp vào kho dữ liệu phân tích DuckDB cục bộ (warehouse.duckdb).
Hỗ trợ cả Full-Refresh và Incremental Sync (dựa trên watermark timestamp / ID).
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import duckdb
from sqlalchemy import create_engine, inspect, text

current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.warehouse_client import parse_jdbc_url, get_warehouse_client
from app.db.duckdb_client import DuckDBClient

logger = logging.getLogger("DataIngestionService")


class DataIngestionService:
    """Dịch vụ trích xuất và nạp dữ liệu từ CSDL nguồn vào kho DuckDB."""

    def __init__(self, target_duckdb_path: Optional[str] = None):
        if target_duckdb_path:
            self.duckdb_path = str(Path(target_duckdb_path).resolve())
        else:
            default_path = backend_dir.parent / "data" / "warehouse.duckdb"
            env_path = os.getenv("DUCKDB_PATH")
            self.duckdb_path = str(Path(env_path).resolve()) if env_path else str(default_path)

        os.makedirs(os.path.dirname(self.duckdb_path), exist_ok=True)
        self._ensure_metadata_table()

    def _ensure_metadata_table(self):
        """Khởi tạo bảng ghi log lịch sử đồng bộ _ingestion_sync_log trong DuckDB."""
        try:
            conn = duckdb.connect(self.duckdb_path, read_only=False)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _ingestion_sync_log (
                    sync_id VARCHAR(64) PRIMARY KEY,
                    source_key VARCHAR(100),
                    domain_id VARCHAR(100),
                    table_name VARCHAR(100),
                    sync_mode VARCHAR(20),
                    rows_ingested BIGINT,
                    duration_sec DOUBLE,
                    status VARCHAR(20),
                    error_message VARCHAR,
                    executed_at TIMESTAMP
                );
            """)
            conn.close()
        except Exception as e:
            logger.warning(f"Không thể khởi tạo _ingestion_sync_log: {e}")

    def sync_table(
        self,
        source_connection_url: str,
        table_name: str,
        source_schema: Optional[str] = None,
        target_table_name: Optional[str] = None,
        sync_mode: str = "full_refresh",
        watermark_column: Optional[str] = None,
        chunk_size: int = 50000,
        domain_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đồng bộ 1 bảng từ CSDL nguồn vào DuckDB.
        - sync_mode: 'full_refresh' (xóa tạo lại) hoặc 'incremental' (chỉ lấy dòng mới)
        - chunk_size: Kích thước batch để tránh tràn RAM
        """
        start_time = time.time()
        target_table = target_table_name or table_name
        clean_url = parse_jdbc_url(source_connection_url)
        engine = create_engine(clean_url, pool_pre_ping=True)

        logger.info(f"Bắt đầu nạp bảng '{table_name}' -> DuckDB table '{target_table}' ({sync_mode})...")

        rows_synced = 0
        status = "SUCCESS"
        err_msg = None

        try:
            duck_conn = duckdb.connect(self.duckdb_path, read_only=False)

            # 1. Xác định điều kiện lọc nếu là incremental
            last_watermark = None
            if sync_mode == "incremental" and watermark_column:
                # Kiểm tra bảng đích đã có chưa để lấy giá trị max
                tbl_exists = duck_conn.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
                    [target_table]
                ).fetchone()[0] > 0

                if tbl_exists:
                    res = duck_conn.execute(f"SELECT MAX({watermark_column}) FROM {target_table}").fetchone()
                    last_watermark = res[0] if res else None

            # 2. Xây dựng câu SELECT từ CSDL nguồn
            schema_prefix = f"[{source_schema}]." if source_schema and "mssql" in clean_url else (f'"{source_schema}".' if source_schema else "")
            quoted_table = f"[{table_name}]" if "mssql" in clean_url else f'"{table_name}"'
            query_str = f"SELECT * FROM {schema_prefix}{quoted_table}"

            if last_watermark is not None and watermark_column:
                query_str += f" WHERE {watermark_column} > :watermark"
                params = {"watermark": last_watermark}
            else:
                params = {}

            # 3. Đọc dữ liệu từ nguồn theo batch (stream) và ghi vào DuckDB
            with engine.connect() as s_conn:
                result_proxy = s_conn.execution_options(stream_results=True).execute(text(query_str), params)
                columns = list(result_proxy.keys())

                first_chunk = True
                while True:
                    rows = result_proxy.fetchmany(chunk_size)
                    if not rows:
                        break

                    # Chuyển đổi thành PyArrow table / DataFrame để nạp siêu tốc vào DuckDB
                    import pandas as pd
                    df = pd.DataFrame(rows, columns=columns)

                    if first_chunk:
                        if sync_mode == "full_refresh" or last_watermark is None:
                            # Ghi đè toàn bộ bảng
                            duck_conn.execute(f"DROP TABLE IF EXISTS {target_table}")
                            duck_conn.register("temp_ingest_chunk", df)
                            duck_conn.execute(f"CREATE TABLE {target_table} AS SELECT * FROM temp_ingest_chunk")
                            duck_conn.unregister("temp_ingest_chunk")
                        else:
                            duck_conn.register("temp_ingest_chunk", df)
                            duck_conn.execute(f"INSERT INTO {target_table} SELECT * FROM temp_ingest_chunk")
                            duck_conn.unregister("temp_ingest_chunk")
                        first_chunk = False
                    else:
                        duck_conn.register("temp_ingest_chunk", df)
                        duck_conn.execute(f"INSERT INTO {target_table} SELECT * FROM temp_ingest_chunk")
                        duck_conn.unregister("temp_ingest_chunk")

                    rows_synced += len(rows)

            duck_conn.close()

        except Exception as e:
            status = "FAILED"
            err_msg = str(e)
            logger.error(f"Lỗi khi nạp bảng '{table_name}': {e}", exc_info=True)
        finally:
            engine.dispose()

        elapsed = time.time() - start_time
        logger.info(f"Hoàn thành bảng '{target_table}': {rows_synced} dòng trong {elapsed:.2f}s (Status: {status})")

        # 4. Ghi log lịch sử đồng bộ
        import uuid
        sync_id = f"sync_{target_table}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        self._record_log(
            sync_id=sync_id,
            source_key=source_schema or "default",
            domain_id=domain_id or "default",
            table_name=target_table,
            sync_mode=sync_mode,
            rows_ingested=rows_synced,
            duration_sec=elapsed,
            status=status,
            error_message=err_msg
        )

        return {
            "sync_id": sync_id,
            "table_name": target_table,
            "rows_ingested": rows_synced,
            "duration_sec": round(elapsed, 3),
            "status": status,
            "error_message": err_msg
        }

    def sync_database(
        self,
        source_connection_url: str,
        source_schema: Optional[str] = None,
        selected_tables: Optional[List[str]] = None,
        sync_mode: str = "full_refresh",
        domain_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đồng bộ toàn bộ các bảng trong CSDL nguồn (hoặc danh sách được chọn) vào DuckDB.
        """
        start_time = time.time()
        clean_url = parse_jdbc_url(source_connection_url)
        engine = create_engine(clean_url, pool_pre_ping=True)
        inspector = inspect(engine)

        if selected_tables:
            tables_to_sync = selected_tables
        else:
            tables_to_sync = inspector.get_table_names(schema=source_schema)

        results = []
        total_rows = 0
        failed_tables = []

        logger.info(f"Bắt đầu đồng bộ hàng loạt {len(tables_to_sync)} bảng vào DuckDB ({self.duckdb_path})...")

        for tbl in tables_to_sync:
            # Tự động tìm watermark column (updated_at, created_at, modified_at, id)
            watermark_col = None
            if sync_mode == "incremental":
                try:
                    cols = [c["name"].lower() for c in inspector.get_columns(tbl, schema=source_schema)]
                    for cand in ["updated_at", "modified_at", "created_at", "order_date", "id"]:
                        if cand in cols:
                            watermark_col = cand
                            break
                except Exception:
                    pass

            res = self.sync_table(
                source_connection_url=source_connection_url,
                table_name=tbl,
                source_schema=source_schema,
                sync_mode=sync_mode,
                watermark_column=watermark_col,
                domain_id=domain_id
            )
            results.append(res)
            total_rows += res["rows_ingested"]
            if res["status"] != "SUCCESS":
                failed_tables.append(tbl)

        total_elapsed = time.time() - start_time
        engine.dispose()
        summary = {
            "status": "SUCCESS" if not failed_tables else ("PARTIAL" if total_rows > 0 else "FAILED"),
            "domain_id": domain_id or "default",
            "tables_synced_count": len(tables_to_sync) - len(failed_tables),
            "total_tables": len(tables_to_sync),
            "total_rows_ingested": total_rows,
            "failed_tables": failed_tables,
            "duration_sec": round(total_elapsed, 3),
            "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "table_details": results
        }
        return summary

    def _record_log(
        self,
        sync_id: str,
        source_key: str,
        domain_id: str,
        table_name: str,
        sync_mode: str,
        rows_ingested: int,
        duration_sec: float,
        status: str,
        error_message: Optional[str]
    ):
        """Lưu bản ghi lịch sử vào DuckDB."""
        try:
            conn = duckdb.connect(self.duckdb_path, read_only=False)
            conn.execute("""
                INSERT INTO _ingestion_sync_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [sync_id, source_key, domain_id, table_name, sync_mode, rows_ingested, duration_sec, status, error_message or ""])
            conn.close()
        except Exception as e:
            logger.warning(f"Lỗi lưu log ingestion: {e}")

    def get_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các lần đồng bộ gần nhất."""
        try:
            conn = duckdb.connect(self.duckdb_path, read_only=True)
            rel = conn.execute("""
                SELECT sync_id, source_key, domain_id, table_name, sync_mode, 
                       rows_ingested, duration_sec, status, error_message, executed_at
                FROM _ingestion_sync_log
                ORDER BY executed_at DESC
                LIMIT ?
            """, [limit]).fetchall()
            cols = ["sync_id", "source_key", "domain_id", "table_name", "sync_mode", 
                    "rows_ingested", "duration_sec", "status", "error_message", "executed_at"]
            conn.close()
            return [dict(zip(cols, row)) for row in rel]
        except Exception as e:
            logger.warning(f"Lỗi đọc lịch sử sync: {e}")
            return []
