from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ColumnContext(BaseModel):
    name: str = Field(..., description="Tên cột trong CSDL Data Warehouse")
    table_name: Optional[str] = Field(None, description="Tên bảng chứa cột này (hỗ trợ đa bảng)")
    data_type: str = Field(..., description="Kiểu dữ liệu SQL")
    vn_name: str = Field(..., description="Tên tiếng Việt")
    description: str = Field(..., description="Mô tả nghiệp vụ")
    is_partition_or_dist: bool = Field(False, description="Có phải cột phân vùng hoặc phân tán không")
    is_sensitive: bool = Field(False, description="Dữ liệu nhạy cảm (ẩn đối với analyst thông thường)")
    sample_values: List[Any] = Field(default_factory=list, description="Giá trị mẫu")


class MetricContext(BaseModel):
    name: str = Field(..., description="Tên chỉ số")
    vn_terms: List[str] = Field(..., description="Từ khóa tiếng Việt")
    sql_expression: str = Field(..., description="Biểu thức SQL (VD: AVG(price / NULLIF(area, 0)))")
    description: str = Field(..., description="Mô tả công thức")


class SchemaContext(BaseModel):
    """
    Ngữ cảnh Schema Linking thu gọn và chính xác (hỗ trợ cả 1 bảng lẫn đa bảng có quan hệ JOIN),
    cung cấp cho Dual-Model LLM (Qwen 3 Planner + Qwen 2.5-Coder).
    """
    selected_tables: List[str] = Field(default_factory=list, description="Danh sách các bảng liên quan tham gia truy vấn")
    table_name: str = Field("real_estate_listings", description="Tên bảng dữ liệu chính (alias tương thích ngược)")
    join_paths: List[str] = Field(default_factory=list, description="Các mệnh đề JOIN ... ON ... được thuật toán Steiner Tree suy luận")
    cardinality_warnings: List[str] = Field(default_factory=list, description="Cảnh báo Fan-trap nếu có hàm gộp (SUM/COUNT) trên quan hệ 1-N")
    relevant_columns: List[ColumnContext] = Field(..., description="Danh sách các cột liên quan nhất đến câu hỏi")
    suggested_filters: List[str] = Field(default_factory=list, description="Các mệnh đề WHERE được gợi ý từ danh mục chuẩn")
    suggested_metrics: List[MetricContext] = Field(default_factory=list, description="Các chỉ số tổng hợp được gợi ý")
    order_by_clause: Optional[str] = Field(None, description="Gợi ý mệnh đề ORDER BY")
    limit_clause: Optional[str] = Field(None, description="Gợi ý mệnh đề LIMIT")
    partition_pruning_hint: Optional[str] = Field(
        None,
        description="Gợi ý tối ưu phân vùng"
    )
    prompt_context: str = Field(..., description="Đoạn ngữ cảnh văn bản Markdown sẵn sàng đưa vào LLM System Prompt")
