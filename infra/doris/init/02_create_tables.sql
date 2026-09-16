-- Bảng dữ liệu chính lưu trữ 3.5 triệu tin đăng bất động sản
-- Tối ưu hóa:
-- 1. DUPLICATE KEY: Tối ưu cho truy vấn phân tích tổng hợp (OLAP).
-- 2. PARTITION BY RANGE (published_at): Phân vùng theo tháng đăng tin (06/2025 -> 03/2026), giúp cắt tỉa partition (Partition Pruning) khi truy vấn theo thời gian.
-- 3. DISTRIBUTED BY HASH (province_name): Phân tán dữ liệu đều theo Tỉnh/Thành phố.

CREATE TABLE IF NOT EXISTS real_estate_analytics.real_estate_listings (
    province_name VARCHAR(100) NOT NULL COMMENT "Tỉnh / Thành phố (Hà Nội, TP.HCM, Đà Nẵng...)",
    district_name VARCHAR(100) NOT NULL DEFAULT "" COMMENT "Quận / Huyện",
    property_type_name VARCHAR(100) NOT NULL DEFAULT "" COMMENT "Loại hình BĐS (Chung cư, Nhà riêng, Đất nền, Biệt thự...)",
    published_at DATETIME NOT NULL COMMENT "Thời điểm đăng tin",
    
    ward_name VARCHAR(100) DEFAULT "" COMMENT "Phường / Xã",
    street_name VARCHAR(255) DEFAULT "" COMMENT "Tên đường / Tuyến phố",
    project_name VARCHAR(255) DEFAULT "" COMMENT "Tên dự án BĐS hoặc khu đô thị",
    name VARCHAR(500) DEFAULT "" COMMENT "Tiêu đề tin đăng",
    description STRING DEFAULT "" COMMENT "Nội dung chi tiết tin đăng",
    
    price DOUBLE DEFAULT "0.0" COMMENT "Giá chào bán niêm yết (VNĐ)",
    area DOUBLE DEFAULT "0.0" COMMENT "Diện tích mặt sàn (m²)",
    floor_count FLOAT DEFAULT "0.0" COMMENT "Số tầng của bất động sản",
    frontage_width FLOAT DEFAULT "0.0" COMMENT "Độ rộng mặt tiền (m)",
    house_depth FLOAT DEFAULT "0.0" COMMENT "Chiều sâu ngôi nhà (m)",
    road_width FLOAT DEFAULT "0.0" COMMENT "Độ rộng đường/hẻm trước nhà (m)",
    bedroom_count FLOAT DEFAULT "0.0" COMMENT "Số phòng ngủ",
    bathroom_count FLOAT DEFAULT "0.0" COMMENT "Số phòng vệ sinh",
    house_direction VARCHAR(50) DEFAULT "" COMMENT "Hướng nhà (Đông, Tây, Nam, Bắc, Đông Nam...)",
    balcony_direction VARCHAR(50) DEFAULT "" COMMENT "Hướng ban công"
)
ENGINE = OLAP
DUPLICATE KEY(province_name, district_name, property_type_name, published_at)
PARTITION BY RANGE(published_at) (
    PARTITION p2025_06 VALUES [('2025-06-01 00:00:00'), ('2025-07-01 00:00:00')),
    PARTITION p2025_07 VALUES [('2025-07-01 00:00:00'), ('2025-08-01 00:00:00')),
    PARTITION p2025_08 VALUES [('2025-08-01 00:00:00'), ('2025-09-01 00:00:00')),
    PARTITION p2025_09 VALUES [('2025-09-01 00:00:00'), ('2025-10-01 00:00:00')),
    PARTITION p2025_10 VALUES [('2025-10-01 00:00:00'), ('2025-11-01 00:00:00')),
    PARTITION p2025_11 VALUES [('2025-11-01 00:00:00'), ('2025-12-01 00:00:00')),
    PARTITION p2025_12 VALUES [('2025-12-01 00:00:00'), ('2026-01-01 00:00:00')),
    PARTITION p2026_01 VALUES [('2026-01-01 00:00:00'), ('2026-02-01 00:00:00')),
    PARTITION p2026_02 VALUES [('2026-02-01 00:00:00'), ('2026-03-01 00:00:00')),
    PARTITION p2026_03 VALUES [('2026-03-01 00:00:00'), ('2026-04-01 00:00:00')),
    PARTITION p_other VALUES [('2026-04-01 00:00:00'), ('2030-01-01 00:00:00'))
)
DISTRIBUTED BY HASH(province_name) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
