"""
Agent Tool Definitions (OpenAI / Qwen Function Calling Specifications).
Định nghĩa các schemas chuẩn cho Qwen Function Calling trong hệ thống Text-to-SQL.
"""

from typing import Dict, Any, List

# Công cụ sinh truy vấn SQL (dành cho Coder Model - Qwen 2.5-Coder)
SQL_GENERATION_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_sql_query",
        "description": "Sinh câu lệnh SQL phân tích dữ liệu chuẩn xác, an toàn trên Data Warehouse (DuckDB) dựa vào Schema Context và giải thuật Steiner Tree.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Câu lệnh SQL hoàn chỉnh thực thi được trên Data Warehouse (DuckDB/PostgreSQL). CHỈ chấp nhận SELECT hoặc WITH ... SELECT."
                },
                "tables_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách tên các bảng dữ liệu được truy vấn trong câu SQL."
                },
                "explanation": {
                    "type": "string",
                    "description": "Giải thích ngắn gọn bằng tiếng Việt về logic tính toán và các bảng được liên kết."
                },
                "applied_filters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách các điều kiện lọc (WHERE/HAVING) đã được trích xuất và áp dụng."
                }
            },
            "required": ["sql", "tables_used"]
        }
    }
}

# Công cụ làm rõ câu hỏi mơ hồ (dành cho Reasoner Model - Qwen 2.5/Qwen 3)
CLARIFICATION_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ask_clarification",
        "description": "Kích hoạt hỏi lại người dùng khi câu hỏi quá ngắn, mơ hồ hoặc thiếu các tham số lọc cần thiết để viết SQL.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Câu hỏi làm rõ ngắn gọn, lịch sự bằng tiếng Việt."
                },
                "missing_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách các trường hoặc chiều phân tích còn thiếu (ví dụ: 'khu vực', 'thời gian', 'loại hình')."
                },
                "suggested_options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách gợi ý nhanh để người dùng chọn (ví dụ: ['Hà Nội', 'TP. Hồ Chí Minh', 'Đà Nẵng'])."
                }
            },
            "required": ["question"]
        }
    }
}

# Danh mục tools hỗ trợ
AGENT_TOOLS = [SQL_GENERATION_TOOL, CLARIFICATION_TOOL]
