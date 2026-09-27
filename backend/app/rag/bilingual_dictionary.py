"""
Bilingual Real Estate Domain Dictionary (Từ điển song ngữ Bất động sản Việt Nam).
Ánh xạ giữa ngôn ngữ tự nhiên (Tiếng Việt / English) với DDL Columns, Aggregation Metrics và Business Filters.
"""

from typing import Dict, Any, List

# 1. Định nghĩa chi tiết ngữ nghĩa từng cột trong bảng real_estate_listings
COLUMN_PROFILES: Dict[str, Dict[str, Any]] = {
    "province_name": {
        "vn_name": "Tỉnh / Thành phố",
        "en_name": "Province / City",
        "data_type": "VARCHAR(100)",
        "description": "Tên tỉnh hoặc thành phố trực thuộc trung ương (VD: Hồ Chí Minh, Hà Nội, Đà Nẵng, Bình Dương...)",
        "synonyms": ["tỉnh", "thành phố", "thành phố trực thuộc", "tỉnh thành", "province", "city"],
        "is_partition_or_dist": True,
        "sample_values": ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Bình Dương", "Đồng Nai", "Khánh Hòa"]
    },
    "district_name": {
        "vn_name": "Quận / Huyện / Thị xã / TP trực thuộc",
        "en_name": "District / Municipality",
        "data_type": "VARCHAR(100)",
        "description": "Tên quận, huyện, thị xã hoặc thành phố trực thuộc tỉnh (VD: Cầu Giấy, Thủ Đức, Bình Thạnh, Hải Châu...)",
        "synonyms": ["quận", "huyện", "thị xã", "tp trực thuộc", "district", "quan"],
        "is_partition_or_dist": False,
        "sample_values": ["Cầu Giấy", "Thủ Đức", "Bình Thạnh", "Gò Vấp", "Hà Đông", "Quận 1", "Quận 7"]
    },
    "ward_name": {
        "vn_name": "Phường / Xã / Thị trấn",
        "en_name": "Ward / Commune",
        "data_type": "VARCHAR(100)",
        "description": "Tên phường, xã hoặc thị trấn nơi tọa lạc bất động sản",
        "synonyms": ["phường", "xã", "thị trấn", "ward", "commune"],
        "is_partition_or_dist": False,
        "sample_values": ["Phường Bến Nghé", "Phường Thảo Điền", "Phường Dịch Vọng Hậu"]
    },
    "street_name": {
        "vn_name": "Tên Đường / Tuyến phố",
        "en_name": "Street Name",
        "data_type": "VARCHAR(255)",
        "description": "Tên tuyến đường hoặc phố của bất động sản",
        "synonyms": ["đường", "tuyến đường", "phố", "street", "road"],
        "is_partition_or_dist": False,
        "sample_values": ["Nguyễn Huệ", "Cầu Giấy", "Nguyễn Thị Minh Khai", "Phạm Văn Đồng"]
    },
    "project_name": {
        "vn_name": "Tên Dự án BĐS",
        "en_name": "Project Name / Compound",
        "data_type": "VARCHAR(255)",
        "description": "Tên khu đô thị, tòa chung cư hoặc dự án bất động sản thương mại",
        "synonyms": ["dự án", "khu đô thị", "tòa nhà", "khu dân cư", "project", "compound", "complex"],
        "is_partition_or_dist": False,
        "sample_values": ["Vinhomes Grand Park", "Vinhomes Ocean Park", "Masteri Thảo Điền", "Aqua City"]
    },
    "property_type_name": {
        "vn_name": "Loại hình Bất động sản",
        "en_name": "Property Type",
        "data_type": "VARCHAR(100)",
        "description": "Phân loại bất động sản. Gồm đúng 5 giá trị chuẩn trong CSDL: 'Nhà', 'Đất', 'Căn hộ chung cư', 'Biệt thự/Nhà liền kề', 'Shophouse'",
        "synonyms": ["loại hình", "loại bđs", "danh mục", "property type", "category"],
        "is_partition_or_dist": False,
        "sample_values": ["Nhà", "Đất", "Căn hộ chung cư", "Biệt thự/Nhà liền kề", "Shophouse"]
    },
    "published_at": {
        "vn_name": "Thời điểm đăng tin",
        "en_name": "Publication Datetime",
        "data_type": "DATETIME",
        "description": "Ngày giờ bài viết được xuất bản (Partition Key phân vùng theo tháng từ 2025-06 đến 2026-03). Bắt buộc phải có điều kiện lọc thời gian để tối ưu quét bảng",
        "synonyms": ["ngày đăng", "thời gian đăng", "tháng", "năm", "quý", "published date", "date"],
        "is_partition_or_dist": True,
        "sample_values": ["2026-03-01 10:00:00", "2026-02-15 14:30:00"]
    },
    "price": {
        "vn_name": "Giá niêm yết (VNĐ)",
        "en_name": "Listing Price (VND)",
        "data_type": "DOUBLE",
        "description": "Tổng giá bán niêm yết tính bằng đơn vị Việt Nam Đồng (VNĐ). 1 tỷ = 1,000,000,000 VNĐ; 1 triệu = 1,000,000 VNĐ",
        "synonyms": ["giá", "giá bán", "tổng giá", "số tiền", "price", "total cost", "budget"],
        "is_partition_or_dist": False,
        "sample_values": [1500000000, 3200000000, 8500000000, 25000000000]
    },
    "area": {
        "vn_name": "Diện tích (m²)",
        "en_name": "Area / Size (sqm)",
        "data_type": "DOUBLE",
        "description": "Diện tích sử dụng hoặc diện tích đất tính bằng mét vuông (m²)",
        "synonyms": ["diện tích", "diện tích sử dụng", "m2", "mét vuông", "rộng bao nhiêu", "area", "size", "sqm"],
        "is_partition_or_dist": False,
        "sample_values": [45.5, 72.0, 95.0, 120.0, 250.0]
    },
    "bedroom_count": {
        "vn_name": "Số phòng ngủ (PN)",
        "en_name": "Bedrooms Count",
        "data_type": "FLOAT",
        "description": "Số lượng phòng ngủ trong căn nhà hoặc chung cư",
        "synonyms": ["phòng ngủ", "pn", "phòng", "bedroom", "beds"],
        "is_partition_or_dist": False,
        "sample_values": [1, 2, 3, 4, 5]
    },
    "bathroom_count": {
        "vn_name": "Số phòng vệ sinh (WC)",
        "en_name": "Bathrooms Count",
        "data_type": "FLOAT",
        "description": "Số lượng phòng vệ sinh / nhà tắm",
        "synonyms": ["vệ sinh", "toilet", "wc", "phòng tắm", "bathroom", "baths"],
        "is_partition_or_dist": False,
        "sample_values": [1, 2, 3, 4]
    },
    "floor_count": {
        "vn_name": "Số tầng / Lầu",
        "en_name": "Floors Count",
        "data_type": "FLOAT",
        "description": "Tổng số tầng của ngôi nhà",
        "synonyms": ["số tầng", "tầng", "lầu", "mấy lầu", "floors", "stories"],
        "is_partition_or_dist": False,
        "sample_values": [1, 2, 3, 4, 5]
    },
    "frontage_width": {
        "vn_name": "Chiều rộng mặt tiền (m)",
        "en_name": "Frontage Width (m)",
        "data_type": "FLOAT",
        "description": "Chiều rộng mặt trước của mảnh đất hoặc ngôi nhà giáp với đường",
        "synonyms": ["mặt tiền", "chiều ngang", "bề ngang", "frontage", "width"],
        "is_partition_or_dist": False,
        "sample_values": [4.0, 5.0, 6.5, 10.0]
    },
    "house_depth": {
        "vn_name": "Chiều sâu ngôi nhà (m)",
        "en_name": "House Depth (m)",
        "data_type": "FLOAT",
        "description": "Chiều sâu tính từ mặt tiền đến điểm cuối của bất động sản",
        "synonyms": ["chiều sâu", "chiều dài", "độ dài", "depth", "length"],
        "is_partition_or_dist": False,
        "sample_values": [12.0, 15.0, 18.0, 20.0]
    },
    "road_width": {
        "vn_name": "Độ rộng đường trước nhà (m)",
        "en_name": "Road / Alley Width (m)",
        "data_type": "FLOAT",
        "description": "Độ rộng của đường, phố, ngõ hoặc hẻm trước cửa nhà. >= 4m thường xe ô tô vào được",
        "synonyms": ["đường trước nhà", "ngõ rộng", "hẻm rộng", "đường vào", "ngõ ô tô", "hẻm xe hơi", "road width", "alley"],
        "is_partition_or_dist": False,
        "sample_values": [2.5, 3.5, 5.0, 8.0, 12.0]
    },
    "house_direction": {
        "vn_name": "Hướng nhà",
        "en_name": "House Direction",
        "data_type": "VARCHAR(50)",
        "description": "Hướng phong thủy của ngôi nhà (Đông, Tây, Nam, Bắc, Đông Nam, Tây Nam, Đông Bắc, Tây Bắc)",
        "synonyms": ["hướng nhà", "hướng", "phong thủy", "hướng cửa chính", "direction", "orientation"],
        "is_partition_or_dist": False,
        "sample_values": ["Đông Nam", "Tây Nam", "Đông Bắc", "Tây Bắc", "Đông", "Tây", "Nam", "Bắc"]
    },
    "balcony_direction": {
        "vn_name": "Hướng ban công",
        "en_name": "Balcony Direction",
        "data_type": "VARCHAR(50)",
        "description": "Hướng phong thủy ban công của căn hộ chung cư",
        "synonyms": ["hướng ban công", "ban công", "balcony direction"],
        "is_partition_or_dist": False,
        "sample_values": ["Đông Nam", "Nam", "Đông"]
    },
    "name": {
        "vn_name": "Tiêu đề tin đăng",
        "en_name": "Listing Title",
        "data_type": "VARCHAR(500)",
        "description": "Tiêu đề ngắn gọn của tin rao bán bất động sản",
        "synonyms": ["tiêu đề", "tên tin", "title"],
        "is_partition_or_dist": False,
        "sample_values": ["Bán căn hộ 2PN Cầu Giấy full nội thất", "Bán đất thổ cư Thủ Đức giá ngộp"]
    },
    "description": {
        "vn_name": "Nội dung chi tiết tin đăng",
        "en_name": "Listing Description",
        "data_type": "TEXT",
        "description": "Mô tả đầy đủ chi tiết về pháp lý, tiện ích xung quanh, hiện trạng bất động sản",
        "synonyms": ["mô tả", "nội dung", "chi tiết", "description", "content"],
        "is_partition_or_dist": False,
        "sample_values": ["Chính chủ cần bán gấp căn hộ tầng trung, sổ đỏ sẵn sàng giao dịch..."]
    }
}

# 2. Ánh xạ các Chỉ số Nghiệp vụ phân tích (Business Analytics Metrics)
BUSINESS_METRICS: Dict[str, Dict[str, Any]] = {
    "avg_price_per_sqm": {
        "vn_terms": ["giá bán trung bình m2", "giá trung bình m2", "đơn giá m2", "giá mỗi mét vuông", "đơn giá trung bình", "m2 bao nhiêu tiền", "giá m2", "đơn giá mỗi mét vuông"],
        "en_terms": ["average price per sqm", "unit price per sqm", "price per square meter"],
        "sql_expression": "ROUND(AVG(price / NULLIF(area, 0)), 0)",
        "description": "Đơn giá trung bình mỗi mét vuông diện tích"
    },
    "avg_total_price": {
        "vn_terms": ["giá bán trung bình", "giá trung bình", "giá bán bình quân", "giá bình quân", "giá căn hộ trung bình", "mức giá trung bình", "giá nhà trung bình", "giá đất trung bình"],
        "en_terms": ["average price", "mean listing price", "average selling price"],
        "sql_expression": "ROUND(AVG(price), 0)",
        "description": "Tổng giá trị bình quân của các bất động sản"
    },
    "listing_count": {
        "vn_terms": ["số lượng tin đăng", "tổng số bất động sản", "nguồn cung", "số lượng căn", "mật độ tin", "thanh khoản nguồn cung"],
        "en_terms": ["listing count", "total listings", "supply volume", "number of properties"],
        "sql_expression": "COUNT(*)",
        "description": "Tổng số lượng tin đăng / bất động sản ghi nhận trong CSDL"
    },
    "total_market_value": {
        "vn_terms": ["tổng giá trị thị trường", "tổng giá trị niêm yết", "tổng tiền"],
        "en_terms": ["total market value", "total gross value"],
        "sql_expression": "SUM(price)",
        "description": "Tổng giá trị niêm yết lũy kế của tất cả bất động sản"
    },
    "price_per_sqm_column": {
        "vn_terms": ["đơn giá m2 của từng căn", "tính theo m2"],
        "en_terms": ["price per sqm"],
        "sql_expression": "ROUND(price / NULLIF(area, 0), 0) AS price_per_sqm",
        "description": "Cột tính đơn giá trên từng dòng bất động sản"
    }
}

# 3. Phân khúc giá thị trường (Price Segments)
PRICE_SEGMENTS: Dict[str, Dict[str, Any]] = {
    "luxury": {
        "vn_terms": ["phân khúc cao cấp", "hạng sang", "bất động sản cao cấp", "bất động sản triệu đô", "nhà giàu"],
        "en_terms": ["luxury segment", "high-end properties"],
        "condition": "price >= 10000000000",
        "description": "Bất động sản có giá từ 10 tỷ VNĐ trở lên"
    },
    "mid_tier": {
        "vn_terms": ["phân khúc trung cấp", "giá tầm trung", "vừa túi tiền"],
        "en_terms": ["mid-tier segment", "middle class"],
        "condition": "price BETWEEN 3000000000 AND 10000000000",
        "description": "Bất động sản có giá từ 3 tỷ đến 10 tỷ VNĐ"
    },
    "affordable": {
        "vn_terms": ["phân khúc bình dân", "giá rẻ", "nhà ở xã hội", "giá rẻ nhất", "vốn ít"],
        "en_terms": ["affordable segment", "low cost", "budget friendly"],
        "condition": "price < 3000000000",
        "description": "Bất động sản có giá dưới 3 tỷ VNĐ"
    }
}
