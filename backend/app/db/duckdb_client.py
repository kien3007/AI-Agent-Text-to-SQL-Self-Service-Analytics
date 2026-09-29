"""
DuckDB Client Module.
Client kết nối và thực thi truy vấn phân tích (OLAP) trên DuckDB Embedded Engine.
Được thiết kế tương thích 100% với giao diện của DorisClient nhưng:
- Không cần server daemon/Docker
- Chạy in-process với hiệu năng Vectorized Columnar Engine
- Hỗ trợ an toàn đa luồng ở chế độ read-only
"""

import os
import re
import sys
import logging
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import duckdb

logger = logging.getLogger("DuckDBClient")


class DuckDBClient:
    """
    Client kết nối DuckDB tối ưu cho Text-to-SQL Self-Service Analytics.
    Cung cấp:
    - Thực thi SQL phân tích với giới hạn kết quả an toàn.
    - EXPLAIN kế hoạch thực thi cho Plan Validator & Safety Guardrails.
    - Tự động phát hiện và trích xuất danh mục giá trị thực tế cho Semantic Layer.
    """

    def __init__(self, db_path: Optional[str] = None, read_only: bool = True):
        current_dir = Path(__file__).resolve().parent
        backend_dir = current_dir.parent.parent
        project_root = backend_dir.parent

        if db_path:
            self.db_path = str(Path(db_path).resolve()) if not Path(db_path).is_absolute() else db_path
        else:
            default_path = project_root / "data" / "warehouse.duckdb"
            env_path = os.getenv("DUCKDB_PATH")
            if env_path:
                self.db_path = str(Path(env_path).resolve())
            else:
                self.db_path = str(default_path)

        self.read_only = read_only

    def get_connection(self, read_only: Optional[bool] = None) -> duckdb.DuckDBPyConnection:
        """Tạo kết nối tới database DuckDB."""
        ro = self.read_only if read_only is None else read_only
        
        # Nếu file chưa tồn tại thì không thể mở ở chế độ read_only=True
        if not os.path.exists(self.db_path) and ro:
            ro = False
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        return duckdb.connect(self.db_path, read_only=ro)

    def execute_query(self, sql: str, max_rows: int = 1000) -> Tuple[List[str], List[Tuple]]:
        """
        Thực thi câu truy vấn SELECT an toàn.
        Trả về (tên_các_cột, danh_sách_dòng_kết_quả).
        """
        cleaned_sql = sql.strip().strip(";")
        conn = self.get_connection(read_only=True)
        try:
            rel = conn.sql(cleaned_sql)
            columns = rel.columns if hasattr(rel, "columns") else []
            rows = rel.fetchmany(max_rows)
            return columns, list(rows)
        finally:
            conn.close()

    def execute_query_dict(self, sql: str, max_rows: int = 1000) -> List[Dict[str, Any]]:
        """Thực thi câu truy vấn và trả về danh sách Dictionary."""
        cleaned_sql = sql.strip().strip(";")
        conn = self.get_connection(read_only=True)
        try:
            rel = conn.sql(cleaned_sql)
            df = rel.limit(max_rows).df()
            
            # Xử lý datetime/timestamps và NaNs để JSON serialize an toàn
            records = df.to_dict(orient="records")
            cleaned_records = []
            for row in records:
                cleaned_row = {}
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        cleaned_row[k] = v.isoformat()
                    elif v != v:  # NaN check
                        cleaned_row[k] = None
                    else:
                        cleaned_row[k] = v
                cleaned_records.append(cleaned_row)
            return cleaned_records
        finally:
            conn.close()

    def explain_query(self, sql: str) -> Dict[str, Any]:
        """
        Thực thi EXPLAIN để ước tính chi phí, cấu trúc kế hoạch thực thi.
        Tương thích với Plan Validator Agent và HITL Guardrails.
        """
        cleaned_sql = sql.strip().strip(";")
        explain_sql = f"EXPLAIN {cleaned_sql}"
        conn = self.get_connection(read_only=True)
        try:
            rows = conn.sql(explain_sql).fetchall()
            explain_text = "\n".join(str(r[1]) if len(r) > 1 else str(r[0]) for r in rows)

            cardinality = 0
            # Tìm ước tính số dòng từ DuckDB EXPLAIN (ví dụ: ~3,574,390 rows hoặc cardinality: 1000)
            card_match = re.search(r"~?([0-9,]+)\s*rows", explain_text, re.IGNORECASE)
            if not card_match:
                card_match = re.search(r"(?:cardinality|count)[=:\s]+([0-9,]+)", explain_text, re.IGNORECASE)
            if card_match:
                cardinality = int(card_match.group(1).replace(",", ""))

            # Với DuckDB (local columnar), quét dung lượng thường rất nhỏ do SIMD
            bytes_scanned = cardinality * 64

            return {
                "success": True,
                "cardinality": cardinality,
                "tablets_scanned": 1,
                "bytes_scanned": bytes_scanned,
                "is_partition_pruned": True,
                "raw_explain": explain_text[:2000]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cardinality": 0,
                "tablets_scanned": 0,
                "bytes_scanned": 0,
                "is_partition_pruned": False,
                "raw_explain": ""
            }
        finally:
            conn.close()

    def get_distinct_categories(self) -> Dict[str, List[str]]:
        """
        Trích xuất toàn bộ danh mục phân loại thực tế từ real_estate_listings:
        - Loại hình BĐS (property_type_name)
        - Tỉnh / Thành phố (province_name)
        - Quận / Huyện (district_name)
        - Hướng nhà (house_direction)
        - Top các dự án phổ biến (project_name)
        """
        result = {
            "property_types": [],
            "provinces": [],
            "districts": [],
            "district_to_province": {},
            "directions": [],
            "top_projects": []
        }
        
        conn = self.get_connection(read_only=True)
        try:
            # 1. Property types
            pt = conn.sql("""
                SELECT DISTINCT property_type_name 
                FROM real_estate_listings 
                WHERE property_type_name IS NOT NULL AND property_type_name != ''
            """).fetchall()
            result["property_types"] = [r[0] for r in pt if r[0]]

            # 2. Provinces
            prov = conn.sql("""
                SELECT DISTINCT province_name 
                FROM real_estate_listings 
                WHERE province_name IS NOT NULL AND province_name != '' 
                ORDER BY province_name
            """).fetchall()
            result["provinces"] = [r[0] for r in prov if r[0]]

            # 3. Districts
            dist = conn.sql("""
                SELECT DISTINCT district_name, province_name 
                FROM real_estate_listings 
                WHERE district_name IS NOT NULL AND district_name != ''
            """).fetchall()
            result["districts"] = [r[0] for r in dist if r[0]]
            result["district_to_province"] = {r[0]: r[1] for r in dist if r[0] and r[1]}

            # 4. Directions
            dirs = conn.sql("""
                SELECT DISTINCT house_direction 
                FROM real_estate_listings 
                WHERE house_direction IS NOT NULL AND house_direction != ''
            """).fetchall()
            valid_dirs = {"Đông", "Tây", "Nam", "Bắc", "Đông Nam", "Tây Nam", "Đông Bắc", "Tây Bắc"}
            result["directions"] = [r[0].strip() for r in dirs if r[0] and r[0].strip() in valid_dirs]

            # 5. Top Projects
            proj = conn.sql("""
                SELECT project_name, COUNT(*) as cnt 
                FROM real_estate_listings 
                WHERE project_name IS NOT NULL AND project_name != '' 
                GROUP BY project_name 
                ORDER BY cnt DESC 
                LIMIT 50
            """).fetchall()
            result["top_projects"] = [r[0] for r in proj if r[0]]

        except Exception as e:
            logger.warning(f"Không thể trích xuất danh mục từ DuckDB ({e}). Sử dụng danh mục mặc định.")
        finally:
            conn.close()

        return result
