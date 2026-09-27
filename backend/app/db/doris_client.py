import re
import os
import sys
import logging
from typing import Dict, Any, List, Tuple, Optional
import pymysql
from pymysql.cursors import DictCursor

try:
    from dbutils.pooled_db import PooledDB
except ImportError:
    PooledDB = None

# Đảm bảo UTF-8 trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("DorisClient")

_GLOBAL_POOL = None

def _get_pool(host=None, port=None, user=None, password=None, database=None):
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        if PooledDB is None:
            raise RuntimeError("Cần cài đặt 'DBUtils': pip install DBUtils")
        
        h = host or os.getenv("DORIS_HOST", "localhost")
        p = port or int(os.getenv("DORIS_PORT", "9030"))
        u = user or os.getenv("DORIS_USER", "root")
        pw = password or os.getenv("DORIS_PASSWORD", "")
        db = database or os.getenv("DORIS_DATABASE", "real_estate_analytics")
        
        _GLOBAL_POOL = PooledDB(
            creator=pymysql,
            maxconnections=20,
            mincached=0,        # Lazy init: không tạo kết nối sẵn khi boot
            maxcached=10,
            blocking=True,
            ping=1,             # Ping trước khi trả về connection
            host=h,
            port=p,
            user=u,
            password=pw,
            database=db,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
            read_timeout=60,
            write_timeout=60
        )
    return _GLOBAL_POOL


class DorisClient:
    """
    Client kết nối Apache Doris tối ưu cho truy vấn phân tích (OLAP).
    Sử dụng Connection Pooling (DBUtils) để đảm bảo thread-safe cho concurrent requests.
    Cung cấp:
    - Thực thi SQL với timeout và giới hạn kết quả trả về an toàn.
    - EXPLAIN VERBOSE phân tích số byte quét và số tablet để guardrail chi phí.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        # Pool được khởi tạo lazily khi get_connection() được gọi lần đầu

    def get_connection(self):
        """Lấy một kết nối còn sống từ Global Connection Pool (lazy init)."""
        return _get_pool(self.host, self.port, self.user, self.password, self.database).connection()

    def execute_query(self, sql: str, max_rows: int = 1000) -> Tuple[List[str], List[Tuple]]:
        """
        Thực thi câu truy vấn SELECT an toàn.
        Trả về (tên_các_cột, danh_sách_dòng_kết_quả).
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchmany(max_rows)
                return columns, list(rows)
        finally:
            conn.close()

    def execute_query_dict(self, sql: str, max_rows: int = 1000) -> List[Dict[str, Any]]:
        """Thực thi câu truy vấn và trả về danh sách Dictionary."""
        conn = self.get_connection()
        try:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql)
                rows = cursor.fetchmany(max_rows)
                return list(rows)
        finally:
            conn.close()

    def explain_query(self, sql: str) -> Dict[str, Any]:
        """
        Thực thi EXPLAIN VERBOSE để ước tính chi phí, số dòng/byte quét và số tablet.
        Dùng cho Plan Validator Agent và HITL Guardrails.
        """
        explain_sql = f"EXPLAIN VERBOSE {sql.strip()}"
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(explain_sql)
                    rows = cursor.fetchall()
            finally:
                conn.close()
                
            explain_text = "\n".join(r[0] for r in rows if r and r[0])
            
            # Phân tích cardinallity, scan bytes và tablets
            cardinality = 0
            card_match = re.search(r"cardinality[=:]\s*([0-9,]+)", explain_text, re.IGNORECASE)
            if card_match:
                cardinality = int(card_match.group(1).replace(",", ""))

            tablets = 0
            tablet_matches = re.findall(r"tablets=(\d+)/(\d+)", explain_text)
            if tablet_matches:
                tablets = sum(int(m[0]) for m in tablet_matches)

            is_partition_pruned = "partitions=" in explain_text

            avg_row_size = 0
            size_match = re.search(r"avgRowSize[=:]\s*([0-9.]+)", explain_text, re.IGNORECASE)
            if size_match:
                avg_row_size = float(size_match.group(1))
            bytes_scanned = cardinality * avg_row_size

            return {
                "success": True,
                "cardinality": cardinality,
                "tablets_scanned": tablets,
                "bytes_scanned": bytes_scanned,
                "is_partition_pruned": is_partition_pruned,
                "raw_explain": explain_text[:2000] # Giới hạn lưu trữ
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "cardinality": 0,
                "tablets_scanned": 0,
                "is_partition_pruned": False,
                "raw_explain": ""
            }

    def get_distinct_categories(self) -> Dict[str, List[str]]:
        """
        Trích xuất toàn bộ danh mục phân loại thực tế từ 3.4M bản ghi trong Doris:
        - Loại hình BĐS (property_type_name)
        - Tỉnh / Thành phố (province_name)
        - Quận / Huyện (district_name)
        - Hướng nhà (house_direction)
        - Top các dự án phổ biến (project_name)
        """
        conn = self.get_connection()
        result = {}

        try:
            with conn.cursor() as cursor:
                # 1. Property types
                cursor.execute("SELECT DISTINCT property_type_name FROM real_estate_listings WHERE property_type_name != ''")
                result["property_types"] = [r[0] for r in cursor.fetchall() if r[0]]

                # 2. Provinces
                cursor.execute("SELECT DISTINCT province_name FROM real_estate_listings WHERE province_name != '' ORDER BY province_name")
                result["provinces"] = [r[0] for r in cursor.fetchall() if r[0]]

                # 3. Districts
                cursor.execute("SELECT DISTINCT district_name, province_name FROM real_estate_listings WHERE district_name != ''")
                district_rows = cursor.fetchall()
                result["districts"] = [r[0] for r in district_rows if r[0]]
                result["district_to_province"] = {r[0]: r[1] for r in district_rows if r[0] and r[1]}

                # 4. Directions (lọc lấy các hướng chuẩn)
                cursor.execute("SELECT DISTINCT house_direction FROM real_estate_listings WHERE house_direction IS NOT NULL AND house_direction != ''")
                raw_directions = [r[0] for r in cursor.fetchall() if r[0]]
                standard_dirs = set()
                for d in raw_directions:
                    cleaned_d = d.replace(" - ", " ").replace("-", " ").strip()
                    if cleaned_d in ["Đông", "Tây", "Nam", "Bắc", "Đông Nam", "Tây Nam", "Đông Bắc", "Tây Bắc"]:
                        standard_dirs.add(cleaned_d)
                result["directions"] = sorted(list(standard_dirs))

                # 5. Top Projects (có từ 20 tin đăng trở lên)
                cursor.execute("""
                    SELECT project_name, count(*) as cnt 
                    FROM real_estate_listings 
                    WHERE project_name IS NOT NULL AND project_name != '' 
                    GROUP BY project_name 
                    HAVING cnt >= 20 
                    ORDER BY cnt DESC 
                    LIMIT 200
                """)
                result["top_projects"] = [r[0] for r in cursor.fetchall() if r[0]]

            return result
        except Exception as e:
            logger.error(f"Error extracting categories: {e}")
            return result
        finally:
            conn.close()

    def close(self):
        # Global pool is handled separately, no need to manually close individual instances
        pass
