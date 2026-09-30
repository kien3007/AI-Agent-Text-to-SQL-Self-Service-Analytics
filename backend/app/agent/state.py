"""
AgentState Definition for Text-to-SQL Self-Service Analytics.
Định nghĩa trạng thái xuyên suốt của State Machine / LangGraph Agent.
"""

import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.schemas.schema_context import SchemaContext
from app.schemas.validation import ValidationResult


class AgentState(BaseModel):
    """
    Trạng thái toàn cục của phiên truy vấn Text-to-SQL.
    Lưu trữ đầy đủ ngữ cảnh từ câu hỏi tự nhiên đến kết quả phân tích cuối cùng.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Định danh phiên hội thoại")
    user_query: str = Field(..., description="Câu hỏi ngôn ngữ tự nhiên ban đầu của người dùng")
    domain_id: Optional[str] = Field(None, description="Domain được định tuyến (real_estate, ecommerce, healthcare...)")
    normalized_query: Optional[str] = Field(None, description="Câu hỏi sau khi chuẩn hóa mốc thời gian và từ lóng")
    extracted_entities: Dict[str, Any] = Field(default_factory=dict, description="Các tham số lọc đã trích xuất")
    
    # Multi-turn & RBAC Context
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Lịch sử hội thoại: [{role: user|assistant, content: ...}]"
    )
    user_id: Optional[str] = Field(None, description="ID người dùng (audit)")
    user_role: Optional[str] = Field(None, description="Vai trò: analyst | admin")
    
    # Vòng lặp hỏi lại (Clarification Loop)
    clarification_needed: bool = Field(False, description="Cờ xác định câu hỏi có bị mơ hồ cần hỏi lại người dùng không")
    clarification_question: Optional[str] = Field(None, description="Câu hỏi làm rõ gửi lại cho người dùng")
    
    # Phân loại độ phức tạp & Phân rã câu hỏi (kế thừa DIN-SQL)
    complexity_level: str = Field("EASY", description="Mức độ phức tạp: 'EASY', 'MEDIUM', 'COMPLEX'")
    decomposition_plan: Optional[Dict[str, Any]] = Field(None, description="Kế hoạch phân rã CTEs cho câu hỏi Mức 3")

    # Ngữ cảnh Schema Linking & Steiner Tree
    schema_context: Optional[SchemaContext] = Field(None, description="Ngữ cảnh schema và gợi ý JOIN đa bảng")
    
    # Sinh SQL & Kiểm định
    sql_query: Optional[str] = Field(None, description="Câu lệnh SQL do mô hình Coder sinh ra")
    validation_result: Optional[ValidationResult] = Field(None, description="Kết quả kiểm định an toàn và cú pháp SQL")
    retry_count: int = Field(0, description="Số lần đã thử sửa lỗi cú pháp / logic (Self-correction count)")
    max_retries: int = Field(3, description="Số lần thử sửa lỗi tối đa trước khi dừng")
    error_message: Optional[str] = Field(None, description="Thông điệp lỗi nếu quá trình thực thi thất bại")
    error_history: List[Dict[str, Any]] = Field(default_factory=list, description="Lịch sử các lỗi ngắn hạn đã gặp trong phiên")
    
    # Cổng kiểm duyệt người dùng (Human-In-The-Loop)
    requires_hitl: bool = Field(False, description="Có bắt buộc duyệt thủ công trước khi thực thi không")
    hitl_approved: Optional[bool] = Field(None, description="Trạng thái phê duyệt: True (Duyệt), False (Từ chối), None (Chờ)")
    
    # Thực thi & Dữ liệu
    query_result: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách các dòng kết quả từ CSDL")
    column_names: Optional[List[str]] = Field(None, description="Danh sách tên các cột trong kết quả")
    
    # Định dạng đầu ra & Trực quan hóa
    final_response: Optional[str] = Field(None, description="Báo cáo tóm tắt insights bằng tiếng Việt")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="Cấu hình vẽ biểu đồ Recharts JSON")
    
    # Giám sát & Quá trình thực thi
    execution_time_ms: Optional[float] = Field(None, description="Tổng thời gian xử lý toàn bộ đồ thị (ms)")
    steps_executed: List[str] = Field(default_factory=list, description="Danh sách các bước (nodes) đã đi qua")

    def log_step(self, step_name: str) -> None:
        """Ghi nhận một bước đã xử lý trong đồ thị."""
        self.steps_executed.append(step_name)

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi trạng thái sang dictionary an toàn."""
        return self.model_dump()
