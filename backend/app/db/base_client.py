"""
Base Database Client Protocol & Abstract Class.
Định nghĩa giao diện thống nhất cho mọi database engine (DuckDB, SQLite, PostgreSQL, MySQL, ClickHouse...).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional


class BaseDatabaseClient(ABC):
    """Giao diện trừu tượng chuẩn hóa cho các client CSDL trong hệ thống Text-to-SQL."""

    @abstractmethod
    def execute_query(self, sql: str, max_rows: int = 1000) -> Tuple[List[str], List[Tuple]]:
        """
        Thực thi câu truy vấn SQL an toàn (chỉ đọc).
        Trả về: (danh_sách_tên_cột, danh_sách_dòng_kết_quả_dạng_tuple).
        """
        pass

    @abstractmethod
    def execute_query_dict(self, sql: str, max_rows: int = 1000) -> List[Dict[str, Any]]:
        """
        Thực thi truy vấn và trả về danh sách dict: [{col: val, ...}].
        """
        pass

    @abstractmethod
    def explain_query(self, sql: str) -> str:
        """
        Thực thi EXPLAIN để lấy kế hoạch truy vấn cho Plan Validator & Safety Guardrails.
        """
        pass

    @abstractmethod
    def get_tables(self) -> List[str]:
        """
        Lấy danh sách các bảng/views người dùng trong CSDL.
        """
        pass

    @abstractmethod
    def get_distinct_categories(
        self,
        table_name: Optional[str] = None,
        categorical_columns: Optional[List[str]] = None,
        max_distinct: int = 50
    ) -> Dict[str, List[Any]]:
        """
        Quét các giá trị phân loại thực tế phục vụ Semantic Layer & Entity Linking.
        """
        pass
