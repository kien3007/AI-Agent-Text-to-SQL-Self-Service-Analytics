from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ColumnContext(BaseModel):
    name: str = Field(..., description="Tên cột trong CSDL Doris")
    data_type: str = Field(..., description="Kiểu dữ liệu SQL")
    vn_name: str = Field(..., description="Tên tiếng Việt")
    description: str = Field(..., description="Mô tả nghiệp vụ")
    is_partition_or_dist: bool = Field(False, description="Có phải cột phân vùng hoặc phân tán không")
    sample_values: List[Any] = Field(default_factory=list, description="Giá trị mẫu")

class MetricContext(BaseModel):
    name: str = Field(..., description="Tên chỉ số")
    vn_terms: List[str] = Field(..., description="Từ khóa tiếng Việt")
    sql_expression: str = Field(..., description="Biểu thức SQL (VD: AVG(price / NULLIF(area, 0)))")
    description: str = Field(..., description="Mô tả công thức")

class SchemaContext(BaseModel):
    """
    Ngữ cảnh Schema Linking thu gọn và chính xác,
    cung cấp cho Dual-Model LLM (Qwen 3 Planner + Qwen 2.5-Coder).
    """
    table_name: str = Field("real_estate_listings", description="Tên bảng dữ liệu chính")
    relevant_columns: List[ColumnContext] = Field(..., description="Danh sách các cột liên quan nhất đến câu hỏi")
    suggested_filters: List[str] = Field(default_factory=list, description="Các mệnh đề WHERE được gợi ý từ danh mục chuẩn")
    suggested_metrics: List[MetricContext] = Field(default_factory=list, description="Các chỉ số tổng hợp được gợi ý")
    order_by_clause: Optional[str] = Field(None, description="Gợi ý mệnh đề ORDER BY")
    limit_clause: Optional[str] = Field(None, description="Gợi ý mệnh đề LIMIT")
    partition_pruning_hint: str = Field(
        "Bảng được PARTITION BY RANGE(published_at) theo tháng. Hãy luôn thêm điều kiện published_at BETWEEN ... để tối ưu số tablet quét.",
        description="Gợi ý tối ưu phân vùng"
    )
    prompt_context: str = Field(..., description="Đoạn ngữ cảnh văn bản Markdown sẵn sàng đưa vào LLM System Prompt")
