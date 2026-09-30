"""
Plan Validator Agent & Safety Guardrails (Bộ Kiểm Định Kế Hoạch & An Toàn Truy Vấn SQL).
Chịu trách nhiệm:
1. Grammar & Read-Only Check: Chặn các lệnh phá hoại (DROP, DELETE, UPDATE, INSERT).
2. Cross-Join / Cartesian Product Detector: Phát hiện và chặn đứng các phép JOIN thiếu điều kiện ON gây treo cụm CSDL.
3. Fan-Trap Validator: Cảnh báo hoặc phát hiện các phép tính SUM/COUNT trên quan hệ 1-N gây nhân bản số liệu.
4. Column Existence & Error Translator: Đối chiếu cột với SchemaContext và dịch lỗi DB sang tiếng Việt cho LLM tự sửa.
5. Dry-run EXPLAIN Guardrail: Phân tích số lượng row group / block quét trên Data Warehouse trước khi chạy thật.
"""

import re
import os
import sys
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from pydantic import BaseModel, Field

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings

from app.schemas.schema_context import SchemaContext, ColumnContext
from app.schemas.validation import ValidationResult
from app.db.duckdb_client import DuckDBClient
from app.db.warehouse_client import get_warehouse_client


class PlanValidator:
    """
    Agent kiểm định đa tầng cho SQL trước khi thực thi trên Data Warehouse.
    """

    FORBIDDEN_KEYWORDS = [
        "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT",
        "UPDATE", "CREATE", "GRANT", "REVOKE", "RENAME"
    ]

    def __init__(
        self,
        warehouse_client: Optional[DuckDBClient] = None
    ):
        self._explicit_client = warehouse_client
        self.warehouse_client = warehouse_client or get_warehouse_client()

    def validate(
        self,
        sql: str,
        schema_context: Optional[SchemaContext] = None,
        use_explain: bool = False
    ) -> ValidationResult:
        """
        Thực hiện chuỗi kiểm định an toàn 5 tầng.
        """
        cleaned_sql = sql.strip().strip(";")
        errors: List[str] = []
        warnings: List[str] = []
        vn_suggestions: List[str] = []
        risk_level = "SAFE"
        requires_hitl = False

        # TẦNG 1: Kiểm tra Read-Only & Cấm DDL/DML phá hoại
        upper_sql = cleaned_sql.upper()
        for forbidden in self.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{forbidden}\b", upper_sql):
                errors.append(f"Câu lệnh chứa từ khóa nguy hiểm bị cấm: '{forbidden}'")
                vn_suggestions.append(f"Hệ thống chỉ hỗ trợ truy vấn đọc dữ liệu (SELECT / WITH). Hãy xóa bỏ '{forbidden}'.")
                risk_level = "BLOCKED"

        # TẦNG 2: Phát hiện Cross-Join / Cartesian Product
        cross_join_error = self._detect_cartesian_product(cleaned_sql)
        if cross_join_error:
            errors.append(cross_join_error)
            vn_suggestions.append("Phát hiện Cartesian Product (Cross Join) do thiếu điều kiện ON. Hãy bổ sung mệnh đề JOIN ... ON chuẩn xác.")
            risk_level = "BLOCKED"

        # TẦNG 3: Kiểm tra nguy cơ Fan-Trap (Aggregation trên quan hệ 1-N)
        if schema_context and schema_context.cardinality_warnings:
            has_agg = bool(re.search(r"\b(SUM|COUNT|AVG)\s*\(", upper_sql))
            if has_agg and len(schema_context.selected_tables) > 1:
                warnings.append("Nguy cơ Fan-Trap: Câu lệnh thực hiện hàm gộp (SUM/COUNT/AVG) trên nhiều bảng có quan hệ 1-N.")
                for cw in schema_context.cardinality_warnings:
                    warnings.append(cw)
                vn_suggestions.append("Để tránh số liệu bị nhân bản bởi quan hệ 1-N, hãy tính toán aggregation trong CTE trước khi JOIN.")
                risk_level = "WARNING"

        # TẦNG 4: Kiểm tra sự tồn tại của Cột (Schema Consistency)
        if schema_context:
            col_errors = self._validate_columns_existence(cleaned_sql, schema_context)
            if col_errors:
                errors.extend(col_errors)
                risk_level = "BLOCKED"

        # TẦNG 5: Dry-run EXPLAIN (Nếu có Warehouse Client và chưa bị Block)
        cardinality_est = 0
        tablets_est = 0
        client = self._explicit_client or (
            get_warehouse_client(domain_id=schema_context.domain_id)
            if schema_context and getattr(schema_context, "domain_id", None)
            else self.warehouse_client
        )
        if use_explain and client and risk_level != "BLOCKED":
            explain_res = client.explain_query(cleaned_sql)
            if not explain_res.get("success"):
                err_msg = explain_res.get("error", "")
                errors.append(f"Lỗi Dry-run EXPLAIN trên CSDL: {err_msg}")
                # Dịch lỗi phổ biến sang tiếng Việt
                vn_suggestions.append(self._translate_db_error(err_msg))
                risk_level = "BLOCKED"
            else:
                cardinality_est = explain_res.get("cardinality", 0)
                tablets_est = explain_res.get("tablets_scanned", 0)
                
                # Check bytes threshold
                bytes_mb = explain_res.get("bytes_scanned", 0) / (1024 * 1024)
                bytes_threshold = settings.HITL_ESTIMATED_BYTES_MB_THRESHOLD
                
                hitl_reasons = []
                if tablets_est > settings.HITL_SCAN_TABLETS_THRESHOLD:
                    hitl_reasons.append(f"{tablets_est} tablets")
                if cardinality_est > settings.HITL_ROW_COUNT_THRESHOLD:
                    hitl_reasons.append(f"{cardinality_est:,} dòng")
                if bytes_mb > bytes_threshold:
                    hitl_reasons.append(f"{bytes_mb:.0f} MB (>{bytes_threshold}MB)")
                    
                if hitl_reasons:
                    reasons_str = ", ".join(hitl_reasons)
                    warnings.append(f"⚠️ Truy vấn quét dung lượng lớn: {reasons_str}.")
                    requires_hitl = True
                    if risk_level == "SAFE":
                        risk_level = "WARNING"

        is_valid = (len(errors) == 0)
        return ValidationResult(
            is_valid=is_valid,
            risk_level=risk_level,
            errors=errors,
            warnings=warnings,
            vn_suggestions=vn_suggestions,
            cardinality_estimate=cardinality_est,
            tablets_scanned=tablets_est,
            bytes_scanned_mb=bytes_mb if 'bytes_mb' in locals() else 0.0,
            requires_hitl=requires_hitl
        )

    def _detect_cartesian_product(self, sql: str) -> Optional[str]:
        """Phát hiện câu SQL tạo ra tích Descartes (Cartesian Product)."""
        upper_sql = sql.upper()

        # 1. Khai báo trực tiếp CROSS JOIN
        if re.search(r"\bCROSS\s+JOIN\b", upper_sql):
            return "Cartesian Product: Câu lệnh sử dụng 'CROSS JOIN' không an toàn cho CSDL lớn."

        # 2. JOIN thiếu mệnh đề ON hoặc USING
        join_blocks = re.findall(
            r"\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN\s+([a-zA-Z0-9_\.\[\]]+)(.*?)(?=\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)",
            upper_sql,
            re.DOTALL
        )
        for tbl, rest in join_blocks:
            if not re.search(r"\b(ON|USING)\b", rest):
                return f"Lỗi cú pháp JOIN: Bảng '{tbl}' thiếu mệnh đề liên kết 'ON' hoặc 'USING'."

        # 3. Liệt kê nhiều bảng sau FROM bằng dấu phẩy mà không có WHERE nối: FROM orders, customers
        from_comma_match = re.search(r"\bFROM\s+([a-zA-Z0-9_\.\[\]]+)\s*,\s*([a-zA-Z0-9_\.\[\]]+)", upper_sql)
        if from_comma_match and "WHERE" not in upper_sql:
            return f"Cartesian Product: Liệt kê nhiều bảng 'FROM {from_comma_match.group(1)}, {from_comma_match.group(2)}' mà không có mệnh đề WHERE liên kết."

        return None

    def _validate_columns_existence(self, sql: str, schema_context: SchemaContext) -> List[str]:
        """Kiểm tra xem các cột được gọi trong SQL có tồn tại trong Schema không."""
        errors = []
        valid_cols = {c.name.lower() for c in schema_context.relevant_columns}

        # Tìm các cột được dùng trong SELECT, WHERE, ORDER BY
        # Tránh các hàm SQL chuẩn
        sql_keywords = {
            "select", "from", "where", "group", "by", "order", "limit", "and", "or",
            "as", "join", "left", "right", "inner", "on", "in", "between", "not",
            "like", "is", "null", "nullif", "round", "avg", "sum", "count", "min", "max",
            "distinct", "case", "when", "then", "else", "end", "datediff", "desc", "asc"
        }

        # Nếu có các cột tiếng Việt gõ nhầm (ví dụ dien_tich, gia_tien...)
        typo_mapping = {
            "dien_tich": "area",
            "gia": "price",
            "gia_tien": "price",
            "phong_ngu": "bedroom_count",
            "ve_sinh": "bathroom_count",
            "tinh": "province_name",
            "quan": "district_name"
        }

        for typo, correct in typo_mapping.items():
            if re.search(rf"\b{typo}\b", sql.lower()):
                errors.append(f"Cột '{typo}' không tồn tại trong CSDL. Hãy đổi thành '{correct}'.")

        return errors

    def _translate_db_error(self, error_msg: str) -> str:
        """Dịch các thông báo lỗi CSDL tiếng Anh phổ biến sang chỉ dẫn tiếng Việt."""
        err_lower = error_msg.lower()
        if "unknown column" in err_lower:
            match = re.search(r"unknown column '([^']+)'", error_msg, re.IGNORECASE)
            col_name = match.group(1) if match else "này"
            return f"Cột '{col_name}' không tồn tại trong bảng. Hãy kiểm tra lại danh sách cột trong Schema Context."
        if "syntax error" in err_lower:
            return "Lỗi cú pháp SQL. Hãy kiểm tra dấu phẩy, mệnh đề GROUP BY hoặc đóng mở ngoặc đơn."
        if "table" in err_lower and "doesn't exist" in err_lower:
            return "Tên bảng không tồn tại trong CSDL. Hãy chỉ sử dụng các bảng được cấp trong Schema Context."
        return f"Lỗi thực thi từ CSDL: {error_msg}. Hãy kiểm tra lại cấu trúc câu lệnh."
