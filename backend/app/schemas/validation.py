"""
Schema for SQL Query Validation and Safety Guardrails.
"""

from typing import List
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Kết quả kiểm định an toàn của câu lệnh SQL."""
    is_valid: bool = Field(..., description="Câu lệnh SQL có hợp lệ và an toàn để thực thi không")
    risk_level: str = Field("SAFE", description="Mức độ rủi ro: 'SAFE', 'WARNING', 'BLOCKED'")
    errors: List[str] = Field(default_factory=list, description="Danh sách lỗi cú pháp hoặc vi phạm an toàn")
    warnings: List[str] = Field(default_factory=list, description="Danh sách cảnh báo (Fan-trap, hiệu năng, bytes scan)")
    vn_suggestions: List[str] = Field(default_factory=list, description="Chỉ dẫn bằng tiếng Việt cho LLM sửa câu lệnh")
    cardinality_estimate: int = Field(0, description="Ước tính số dòng kết quả từ EXPLAIN")
    tablets_scanned: int = Field(0, description="Ước tính số tablet quét trên Apache Doris")
    requires_hitl: bool = Field(False, description="Có bắt buộc người dùng phê duyệt Human-In-The-Loop không")
