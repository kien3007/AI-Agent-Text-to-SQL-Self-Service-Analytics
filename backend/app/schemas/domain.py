"""
Mô hình dữ liệu cho Kiến trúc Đa Domain Hướng Cấu hình (Config-Driven Multi-Domain Models).
Định nghĩa các Pydantic Schema cho Bảng, Cột, Mối quan hệ Khóa ngoại, Chỉ số nghiệp vụ và Toàn bộ Domain.
"""

import os
import yaml
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """Hồ sơ định nghĩa một cột trong bảng CSDL."""
    name: str = Field(..., description="Tên cột kỹ thuật trong CSDL")
    vn_name: str = Field(..., description="Tên tiếng Việt hiển thị / nghiệp vụ")
    en_name: Optional[str] = Field(None, description="Tên tiếng Anh")
    data_type: str = Field(..., description="Kiểu dữ liệu SQL (VARCHAR, DOUBLE, DATETIME...)")
    description: str = Field(..., description="Mô tả ý nghĩa nghiệp vụ của cột")
    synonyms: List[str] = Field(default_factory=list, description="Từ đồng nghĩa, từ khóa tìm kiếm liên quan")
    is_partition_or_dist: bool = Field(False, description="Cột có dùng làm Partition hoặc Distributed key không")
    is_primary_key: bool = Field(False, description="Cột có phải Primary Key không")
    foreign_key: Optional[str] = Field(None, description="Đích khóa ngoại (định dạng 'table.column')")
    sample_values: List[Any] = Field(default_factory=list, description="Các giá trị mẫu thực tế")


class RelationshipProfile(BaseModel):
    """Định nghĩa mối quan hệ (khóa ngoại / liên kết logic) giữa hai bảng."""
    from_table: str = Field(..., description="Bảng xuất phát (VD: orders)")
    from_column: str = Field(..., description="Cột khóa ngoại ở bảng xuất phát (VD: customer_id)")
    to_table: str = Field(..., description="Bảng đích (VD: customers)")
    to_column: str = Field(..., description="Cột khóa chính ở bảng đích (VD: id)")
    cardinality: Literal["1:1", "1:N", "N:1", "N:N"] = Field("N:1", description="Độ bội quan hệ")
    join_type: Literal["INNER", "LEFT", "RIGHT"] = Field("INNER", description="Loại phép join mặc định")
    description: Optional[str] = Field(None, description="Mô tả ý nghĩa của mối liên kết")
    weight: float = Field(1.0, description="Trọng số liên kết dùng cho thuật toán Steiner Tree (mặc định: 1.0)")

    @property
    def join_clause(self) -> str:
        """Sinh mệnh đề JOIN ... ON chuẩn."""
        return f"{self.join_type} JOIN {self.to_table} ON {self.from_table}.{self.from_column} = {self.to_table}.{self.to_column}"


class TableProfile(BaseModel):
    """Hồ sơ thông tin bảng dữ liệu."""
    table_name: str = Field(..., description="Tên bảng trong CSDL")
    vn_name: Optional[str] = Field(None, description="Tên tiếng Việt của bảng")
    description: Optional[str] = Field(None, description="Mô tả nghiệp vụ tổng quan của bảng")
    primary_key: List[str] = Field(default_factory=list, description="Danh sách cột khóa chính")
    partition_key: Optional[str] = Field(None, description="Cột phân vùng")
    distribution_key: Optional[str] = Field(None, description="Cột phân tán (Distributed key)")
    columns: Dict[str, ColumnProfile] = Field(default_factory=dict, description="Từ điển các cột thuộc bảng")


class MetricProfile(BaseModel):
    """Chỉ số nghiệp vụ phân tích (Business Analytics Metric)."""
    metric_id: str = Field(..., description="Mã định danh chỉ số (VD: avg_price_per_sqm, gmv)")
    vn_terms: List[str] = Field(..., description="Thuật ngữ tiếng Việt gọi chỉ số này")
    en_terms: List[str] = Field(default_factory=list, description="Thuật ngữ tiếng Anh")
    sql_expression: str = Field(..., description="Biểu thức SQL (VD: ROUND(AVG(price / NULLIF(area, 0)), 0))")
    description: str = Field(..., description="Ý nghĩa và công thức tính")
    depends_on_tables: List[str] = Field(default_factory=list, description="Các bảng cần thiết để tính metric")
    depends_on_columns: List[str] = Field(default_factory=list, description="Các cột cần thiết để tính metric")


class PriceSegmentProfile(BaseModel):
    """Phân khúc định lượng (ví dụ: phân khúc giá, phân khúc khách hàng)."""
    segment_id: str = Field(..., description="Mã phân khúc (VD: luxury, mid_tier, affordable)")
    vn_terms: List[str] = Field(..., description="Từ khóa nhận diện tiếng Việt")
    en_terms: List[str] = Field(default_factory=list, description="Từ khóa nhận diện tiếng Anh")
    condition: str = Field(..., description="Mệnh đề điều kiện SQL WHERE")
    description: str = Field(..., description="Mô tả phân khúc")


class DomainConfig(BaseModel):
    """Cấu hình toàn diện của một Domain Nghiệp vụ."""
    domain_id: str = Field(..., description="Mã định danh domain (VD: real_estate, ecommerce, healthcare)")
    display_name: str = Field(..., description="Tên hiển thị (VD: Bất Động Sản Việt Nam)")
    description: str = Field(..., description="Mô tả tổng quan về domain")
    domain_keywords: List[str] = Field(default_factory=list, description="Từ khóa đặc trưng phục vụ Domain Router")
    tables: Dict[str, TableProfile] = Field(default_factory=dict, description="Các bảng dữ liệu trong domain")
    relationships: List[RelationshipProfile] = Field(default_factory=list, description="Các mối quan hệ giữa các bảng")
    metrics: Dict[str, MetricProfile] = Field(default_factory=dict, description="Các chỉ số phân tích nghiệp vụ")
    segments: Dict[str, PriceSegmentProfile] = Field(default_factory=dict, description="Các phân khúc định lượng")
    synonyms: Dict[str, Union[str, List[str]]] = Field(default_factory=dict, description="Từ điển từ lóng / viết tắt nội bộ")

    @classmethod
    def load_from_folder(cls, folder_path: str) -> "DomainConfig":
        """
        Nạp cấu hình domain từ thư mục chứa domain.yaml, schema.yaml và metrics.yaml.
        """
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Không tìm thấy thư mục domain tại: {folder_path}")

        domain_data: Dict[str, Any] = {}

        # 1. Đọc domain.yaml
        domain_file = os.path.join(folder_path, "domain.yaml")
        if os.path.exists(domain_file):
            with open(domain_file, "r", encoding="utf-8") as f:
                d_meta = yaml.safe_load(f) or {}
                domain_data.update(d_meta)
        else:
            domain_id = os.path.basename(os.path.normpath(folder_path))
            domain_data["domain_id"] = domain_id
            domain_data["display_name"] = domain_id.capitalize()
            domain_data["description"] = f"Domain {domain_id}"

        # 2. Đọc schema.yaml
        schema_file = os.path.join(folder_path, "schema.yaml")
        tables_dict: Dict[str, Any] = {}
        relationships_list: List[Any] = []
        if os.path.exists(schema_file):
            with open(schema_file, "r", encoding="utf-8") as f:
                s_meta = yaml.safe_load(f) or {}
                tables_raw = s_meta.get("tables", {})
                for t_name, t_info in tables_raw.items():
                    if "table_name" not in t_info:
                        t_info["table_name"] = t_name
                    tables_dict[t_name] = t_info
                relationships_list = s_meta.get("relationships", [])
        domain_data["tables"] = tables_dict
        domain_data["relationships"] = relationships_list

        # 3. Đọc metrics.yaml
        metrics_file = os.path.join(folder_path, "metrics.yaml")
        metrics_dict: Dict[str, Any] = {}
        segments_dict: Dict[str, Any] = {}
        if os.path.exists(metrics_file):
            with open(metrics_file, "r", encoding="utf-8") as f:
                m_meta = yaml.safe_load(f) or {}
                metrics_raw = m_meta.get("metrics", {})
                for m_id, m_info in metrics_raw.items():
                    if "metric_id" not in m_info:
                        m_info["metric_id"] = m_id
                    metrics_dict[m_id] = m_info
                segments_raw = m_meta.get("segments", {})
                for seg_id, seg_info in segments_raw.items():
                    if "segment_id" not in seg_info:
                        seg_info["segment_id"] = seg_id
                    segments_dict[seg_id] = seg_info
        domain_data["metrics"] = metrics_dict
        domain_data["segments"] = segments_dict

        return cls(**domain_data)
