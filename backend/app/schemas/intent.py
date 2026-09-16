from typing import Optional, List, Tuple
from pydantic import BaseModel, Field

class NormalizedIntent(BaseModel):
    """Cấu trúc dữ liệu ý định người dùng đã được chuẩn hóa ngữ nghĩa bất động sản."""
    property_type: Optional[str] = Field(None, description="Loại hình BĐS chuẩn: Căn hộ chung cư, Nhà, Đất, Biệt thự/Nhà liền kề, Shophouse")
    province: Optional[str] = Field(None, description="Tỉnh / Thành phố chuẩn")
    district: Optional[str] = Field(None, description="Quận / Huyện chuẩn")
    ward: Optional[str] = Field(None, description="Phường / Xã")
    street: Optional[str] = Field(None, description="Tên đường")
    project: Optional[str] = Field(None, description="Tên dự án BĐS")
    min_price: Optional[float] = Field(None, description="Giá tối thiểu (VNĐ)")
    max_price: Optional[float] = Field(None, description="Giá tối đa (VNĐ)")
    min_area: Optional[float] = Field(None, description="Diện tích tối thiểu (m2)")
    max_area: Optional[float] = Field(None, description="Diện tích tối đa (m2)")
    bedroom_count: Optional[int] = Field(None, description="Số phòng ngủ")
    bathroom_count: Optional[int] = Field(None, description="Số phòng vệ sinh (WC)")
    direction: Optional[str] = Field(None, description="Hướng nhà chuẩn: Đông, Tây, Nam, Bắc, Đông Nam, Tây Nam, Đông Bắc, Tây Bắc")
    time_range: Optional[Tuple[str, str, str]] = Field(None, description="Khoảng thời gian: (nhãn, start_date, end_date)")
    order_by: Optional[str] = Field(None, description="Tiêu chí sắp xếp: price ASC, price DESC, area DESC, published_at DESC...")
    limit: Optional[int] = Field(None, description="Giới hạn số lượng bản ghi (LIMIT)")
    mapped_terms: List[Tuple[str, str]] = Field(default_factory=list, description="Danh sách các ánh xạ từ khóa: (từ_gốc, mệnh_đề_sql)")

class GlossaryResult(BaseModel):
    """Kết quả trả về từ bộ tiền xử lý VietnameseBusinessGlossary."""
    original_query: str
    normalized_query: str
    intent: NormalizedIntent
    enriched_hints: str
