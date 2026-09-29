"""
API Request and Response Schemas for FastAPI Endpoints.
Định nghĩa cấu trúc dữ liệu cho REST API và SSE Streaming.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Yêu cầu truy vấn từ người dùng."""
    query: str = Field(..., description="Câu hỏi ngôn ngữ tự nhiên (tiếng Việt)")
    domain_id: Optional[str] = Field(None, description="Mã domain mục tiêu (nếu bỏ trống, hệ thống tự định tuyến)")
    session_id: Optional[str] = Field(None, description="Mã phiên hội thoại (nếu có)")
    conversation_id: Optional[str] = Field(None, description="ID hội thoại dài hạn (cho multi-turn)")


class HITLDecisionRequest(BaseModel):
    """Quyết định phê duyệt hoặc từ chối tại cổng Human-In-The-Loop."""
    session_id: str = Field(..., description="Mã định danh phiên cần phê duyệt")
    approved: bool = Field(..., description="True (Duyệt cho phép chạy) hoặc False (Từ chối)")
    sql_override: Optional[str] = Field(None, description="SQL đã được chỉnh sửa bởi user")


class DomainSwitchRequest(BaseModel):
    """Yêu cầu chuyển đổi domain hoạt động mặc định."""
    domain_id: str = Field(..., description="Mã domain muốn kích hoạt")


class BootstrapRequest(BaseModel):
    """Yêu cầu tự động khám phá CSDL mới và tạo dbt pipeline."""
    db_name: str = Field(..., description="Tên cơ sở dữ liệu cần quét (DuckDB / MySQL)")
    domain_id: Optional[str] = Field(None, description="Mã domain mới (mặc định lấy theo tên db)")
    display_name: Optional[str] = Field(None, description="Tên hiển thị tiếng Việt của domain mới")
    auto_dbt: bool = Field(True, description="Có tự động tạo dbt pipeline và semantic metrics không")


class StepLog(BaseModel):
    """Thông tin một bước xử lý của Agent gửi qua SSE."""
    step: str = Field(..., description="Tên bước hiện tại (intent_clarifier, schema_linking...)")
    status: str = Field("running", description="Trạng thái của bước (running, completed, failed)")
    message: Optional[str] = Field(None, description="Thông điệp mô tả ngắn gọn")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dữ liệu trung gian nếu có")


class ChatResponse(BaseModel):
    """Phản hồi hoàn chỉnh của một phiên truy vấn Text-to-SQL."""
    session_id: str
    domain_id: Optional[str] = None
    user_query: str
    complexity_level: str = "EASY"
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    requires_hitl: bool = False
    hitl_approved: Optional[bool] = None
    sql_query: Optional[str] = None
    final_response: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    column_names: Optional[List[str]] = None
    query_result: Optional[List[Dict[str, Any]]] = None
    execution_time_ms: Optional[float] = None
    steps_executed: List[str] = Field(default_factory=list)
