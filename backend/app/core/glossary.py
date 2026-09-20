import os
import sys
import re
import datetime
from typing import Dict, Any, List, Optional, Tuple

# Đảm bảo import được app package khi chạy độc lập
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.intent import NormalizedIntent, GlossaryResult
from app.core.normalizer import GenericVietnameseNormalizer
from app.core.domain_manager import DomainManager


class VietnameseBusinessGlossary:
    """
    Bộ tiền xử lý chuẩn hóa câu hỏi Bất động sản Tiếng Việt (Business Glossary & Normalizer).
    Được tái cấu trúc theo mô hình Adapter kết hợp GenericVietnameseNormalizer và DomainManager:
    1. Tận dụng GenericVietnameseNormalizer để chuẩn hóa thời gian, tiền tệ và định lượng.
    2. Tận dụng DomainManager để truy xuất cấu hình YAML của domain 'real_estate'.
    3. Bảo đảm tương thích ngược 100% với toàn bộ unit test và pipeline hiện tại.
    """

    # Danh mục Loại hình BĐS chuẩn trong Database (Apache Doris)
    PROPERTY_TYPE_MAPPING = {
        r"\b(chung cư mini|cc mini|căn hộ mini|officetel|penthouse|duplex|studio|căn hộ dịch vụ|chung cư cao cấp|căn hộ cao cấp|chung cư|căn hộ|chcc|cc)\b": "Căn hộ chung cư",
        r"\b(nhà riêng|nhà phố|nhà ngõ|nhà hẻm|nhà ở|nhà cấp 4|nhà mặt tiền|nhà mặt phố|nhà hẻm xe hơi|nhà ngõ ô tô|nhà)\b": "Nhà",
        r"\b(đất thổ cư|thổ cư|đất nền|đất phân lô|đất rẫy|đất vườn|đất nông nghiệp|đất quy hoạch|đất)\b": "Đất",
        r"\b(biệt thự đơn lập|biệt thự song lập|biệt thự|liền kề|nhà liền kề|bt|lk)\b": "Biệt thự/Nhà liền kề",
        r"\b(shophouse khối đế|shophouse liền kề|shophouse|nhà phố thương mại)\b": "Shophouse"
    }

    # Hướng nhà chuẩn
    DIRECTION_MAPPING = {
        r"\b(đông nam|đông - nam|đn)\b": "Đông Nam",
        r"\b(tây nam|tây - nam|tn)\b": "Tây Nam",
        r"\b(đông bắc|đông - bắc|đb)\b": "Đông Bắc",
        r"\b(tây bắc|tây - bắc|tb)\b": "Tây Bắc",
        r"\b(chính đông|hướng đông)\b": "Đông",
        r"\b(chính tây|hướng tây)\b": "Tây",
        r"\b(chính nam|hướng nam)\b": "Nam",
        r"\b(chính bắc|hướng bắc)\b": "Bắc"
    }

    # Danh sách các tỉnh thành phố chính và alias
    PROVINCE_ALIASES = {
        "Hồ Chí Minh": [r"\b(hồ chí minh|tp\.hcm|tphcm|tp hcm|sài gòn|saigon|hcm)\b"],
        "Hà Nội": [r"\b(hà nội|hn|thủ đô)\b"],
        "Đà Nẵng": [r"\b(đà nẵng|đn)\b"],
        "Bình Dương": [r"\b(bình dương|bd)\b"],
        "Khánh Hòa": [r"\b(khánh hòa|nha trang)\b"],
        "Đồng Nai": [r"\b(đồng nai|biên hòa)\b"],
        "Hải Phòng": [r"\b(hải phòng|hp)\b"],
        "Cần Thơ": [r"\b(cần thơ)\b"],
        "Quảng Nam": [r"\b(quảng nam|hội an)\b"],
        "Bà Rịa - Vũng Tàu": [r"\b(bà rịa - vũng tàu|bà rịa vũng tàu|vũng tàu|vt)\b"],
        "Lâm Đồng": [r"\b(lâm đồng|đà lạt)\b"],
        "Kiên Giang": [r"\b(kiên giang|phú quốc)\b"],
        "Bắc Ninh": [r"\b(bắc ninh)\b"],
        "Hưng Yên": [r"\b(hưng yên)\b"],
        "Long An": [r"\b(long an)\b"]
    }

    # Bản đồ suy luận Quận/Huyện -> Tỉnh/Thành
    DISTRICT_TO_PROVINCE = {
        # Hà Nội
        "Cầu Giấy": "Hà Nội", "Bắc Từ Liêm": "Hà Nội", "Nam Từ Liêm": "Hà Nội",
        "Thanh Xuân": "Hà Nội", "Hà Đông": "Hà Nội", "Hoàng Mai": "Hà Nội",
        "Đống Đa": "Hà Nội", "Ba Đình": "Hà Nội", "Hai Bà Trưng": "Hà Nội",
        "Tây Hồ": "Hà Nội", "Long Biên": "Hà Nội", "Gia Lâm": "Hà Nội",
        "Đông Anh": "Hà Nội", "Hoài Đức": "Hà Nội", "Thanh Trì": "Hà Nội",
        # TP. Hồ Chí Minh
        "Thủ Đức": "Hồ Chí Minh", "Bình Thạnh": "Hồ Chí Minh", "Gò Vấp": "Hồ Chí Minh",
        "Tân Bình": "Hồ Chí Minh", "Tân Phú": "Hồ Chí Minh", "Phú Nhuận": "Hồ Chí Minh",
        "Bình Tân": "Hồ Chí Minh", "Quận 1": "Hồ Chí Minh", "Quận 2": "Hồ Chí Minh",
        "Quận 3": "Hồ Chí Minh", "Quận 4": "Hồ Chí Minh", "Quận 5": "Hồ Chí Minh",
        "Quận 6": "Hồ Chí Minh", "Quận 7": "Hồ Chí Minh", "Quận 8": "Hồ Chí Minh",
        "Quận 9": "Hồ Chí Minh", "Quận 10": "Hồ Chí Minh", "Quận 11": "Hồ Chí Minh",
        "Quận 12": "Hồ Chí Minh", "Nhà Bè": "Hồ Chí Minh", "Bình Chánh": "Hồ Chí Minh",
        "Hóc Môn": "Hồ Chí Minh", "Củ Chi": "Hồ Chí Minh",
        # Đà Nẵng
        "Hải Châu": "Đà Nẵng", "Sơn Trà": "Đà Nẵng", "Ngũ Hành Sơn": "Đà Nẵng",
        "Liên Chiểu": "Đà Nẵng", "Cẩm Lệ": "Đà Nẵng", "Thanh Khê": "Đà Nẵng",
        # Bình Dương
        "Dĩ An": "Bình Dương", "Thuận An": "Bình Dương", "Thủ Dầu Một": "Bình Dương",
        "Bến Cát": "Bình Dương", "Tân Uyên": "Bình Dương",
        # Khánh Hòa
        "Nha Trang": "Khánh Hòa", "Cam Ranh": "Khánh Hòa", "Ninh Hòa": "Khánh Hòa"
    }

    def __init__(
        self,
        reference_date: Optional[datetime.date] = None,
        domain_manager: Optional[DomainManager] = None
    ):
        # Mốc thời gian tham chiếu (theo dữ liệu gần nhất: 2026-03-01)
        self.ref_date = reference_date or datetime.date(2026, 3, 1)
        self.normalizer = GenericVietnameseNormalizer(reference_date=self.ref_date)
        self.domain_manager = domain_manager or DomainManager()
        self.domain = self.domain_manager.get_domain("real_estate")

    def normalize(self, query: str) -> GlossaryResult:
        """
        Chuẩn hóa toàn diện câu hỏi tiếng Việt và trích xuất cấu trúc NormalizedIntent.
        """
        original_query = query.strip()
        cleaned_text = original_query.lower()

        mapped_terms: List[Tuple[str, str]] = []
        property_type = None
        province = None
        district = None
        ward = None
        min_price = None
        max_price = None
        min_area = None
        max_area = None
        bedroom_count = None
        bathroom_count = None
        direction = None
        time_range = None
        order_by = None
        limit = None

        # 1. Trích xuất Loại hình BĐS
        for pattern, std_name in self.PROPERTY_TYPE_MAPPING.items():
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                property_type = std_name
                mapped_terms.append((match.group(0), f"property_type_name = '{std_name}'"))
                break

        # 2. Trích xuất Tỉnh / Thành phố
        for prov_name, aliases in self.PROVINCE_ALIASES.items():
            for alias_pattern in aliases:
                match = re.search(alias_pattern, cleaned_text, re.IGNORECASE)
                if match:
                    province = prov_name
                    mapped_terms.append((match.group(0), f"province_name = '{prov_name}'"))
                    break
            if province:
                break

        # 3. Trích xuất Quận / Huyện (bao gồm cả dạng viết tắt q1, q2, q7...)
        q_short_match = re.search(r"\b(?:q|quận|quan)\.?\s*([0-9]{1,2})\b", cleaned_text)
        if q_short_match:
            q_num = int(q_short_match.group(1))
            if 1 <= q_num <= 12:
                district = f"Quận {q_num}"
                mapped_terms.append((q_short_match.group(0), f"district_name = '{district}'"))
                if not province:
                    province = "Hồ Chí Minh"
                    mapped_terms.append((f"suy luận từ {district}", "province_name = 'Hồ Chí Minh'"))

        if not district:
            for dist_name in sorted(self.DISTRICT_TO_PROVINCE.keys(), key=len, reverse=True):
                pattern = rf"\b(?:quận|huyện|thị xã|tp|thành phố)?\s*{re.escape(dist_name.lower())}\b"
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    district = dist_name
                    mapped_terms.append((match.group(0), f"district_name = '{dist_name}'"))
                    # Tự động suy luận Tỉnh nếu người dùng không nói rõ tỉnh
                    if not province:
                        inferred_province = self.DISTRICT_TO_PROVINCE[dist_name]
                        province = inferred_province
                        mapped_terms.append((f"suy luận từ {dist_name}", f"province_name = '{inferred_province}'"))
                    break

        # 4. Trích xuất Số phòng ngủ (2PN, 3PN, 2 phòng ngủ, 3 phòng...)
        pn_match = re.search(r"(\d+)\s*(?:pn|phòng ngủ|phong ngu|p\.ngủ|p ngủ)\b", cleaned_text)
        if pn_match:
            count = int(pn_match.group(1))
            bedroom_count = count
            mapped_terms.append((pn_match.group(0), f"bedroom_count = {count}"))

        # 5. Trích xuất Số phòng vệ sinh (2WC, 2 vệ sinh, 1 toilet...)
        wc_match = re.search(r"(\d+)\s*(?:wc|vệ sinh|toilet|phòng tắm|p\.tắm)\b", cleaned_text)
        if wc_match:
            count = int(wc_match.group(1))
            bathroom_count = count
            mapped_terms.append((wc_match.group(0), f"bathroom_count = {count}"))

        # 6. Trích xuất Hướng nhà
        for pattern, dir_name in self.DIRECTION_MAPPING.items():
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                direction = dir_name
                mapped_terms.append((match.group(0), f"house_direction LIKE '%{dir_name}%'"))
                break

        # 7. Trích xuất Giá tiền (dùng GenericVietnameseNormalizer)
        c_min, c_max, c_str, c_filt = self.normalizer.extract_currency_range(cleaned_text)
        if c_str:
            min_price, max_price = c_min, c_max
            mapped_terms.append((c_str, f"price {c_filt}"))

        # 8. Trích xuất Diện tích (m2) (dùng GenericVietnameseNormalizer)
        a_min, a_max, a_str, a_filt = self.normalizer.extract_numeric_range(cleaned_text, r"m2|mét vuông")
        if a_str:
            min_area, max_area = a_min, a_max
            mapped_terms.append((a_str, f"area {a_filt}"))

        # 9. Quy đổi mốc thời gian tương đối (dùng GenericVietnameseNormalizer)
        time_res = self._extract_relative_time(cleaned_text)
        if time_res:
            time_range = time_res
            mapped_terms.append((time_res[0], f"published_at BETWEEN '{time_res[1]}' AND '{time_res[2]}'"))

        # 10. Trích xuất ý định Sắp xếp (Order By)
        if re.search(r"\b(giá rẻ nhất|giá rẻ|rẻ nhất|giá thấp nhất)\b", cleaned_text):
            order_by = "price ASC"
            mapped_terms.append(("giá rẻ", "ORDER BY price ASC"))
        elif re.search(r"\b(đắt nhất|giá cao nhất)\b", cleaned_text):
            order_by = "price DESC"
            mapped_terms.append(("giá đắt", "ORDER BY price DESC"))
        elif re.search(r"\b(diện tích lớn nhất|rộng nhất)\b", cleaned_text):
            order_by = "area DESC"
            mapped_terms.append(("rộng nhất", "ORDER BY area DESC"))
        elif re.search(r"\b(mới nhất|gần đây nhất)\b", cleaned_text):
            order_by = "published_at DESC"
            mapped_terms.append(("mới nhất", "ORDER BY published_at DESC"))

        # 11. Trích xuất Giới hạn (LIMIT) (dùng GenericVietnameseNormalizer)
        l_res = self.normalizer.extract_limit(cleaned_text, ["căn", "bản ghi", "tin", "lô đất"])
        if l_res:
            limit, matched_str = l_res
            mapped_terms.append((matched_str, f"LIMIT {limit}"))

        # Tạo chuỗi gợi ý ngữ nghĩa (Enriched Hints)
        hints_list = [f"[{t} -> {m}]" for t, m in mapped_terms]
        enriched_hints = " ".join(hints_list)

        normalized_query = (
            f"{original_query} (Gợi ý phân giải nghiệp vụ: {enriched_hints})"
            if hints_list else original_query
        )

        intent = NormalizedIntent(
            property_type=property_type,
            province=province,
            district=district,
            ward=ward,
            min_price=min_price,
            max_price=max_price,
            min_area=min_area,
            max_area=max_area,
            bedroom_count=bedroom_count,
            bathroom_count=bathroom_count,
            direction=direction,
            time_range=time_range,
            order_by=order_by,
            limit=limit,
            mapped_terms=mapped_terms
        )

        return GlossaryResult(
            original_query=original_query,
            normalized_query=normalized_query,
            intent=intent,
            enriched_hints=enriched_hints
        )

    def _extract_relative_time(self, text: str) -> Optional[Tuple[str, str, str]]:
        """Quy đổi mốc thời gian qua GenericVietnameseNormalizer."""
        return self.normalizer.extract_relative_time(text, ref_date=self.ref_date)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    normalizer = VietnameseBusinessGlossary()
    test_cases = [
        "chung cư 2PN Cầu Giấy dưới 3 tỷ",
        "đất thổ cư Thủ Đức giá rẻ",
        "căn hộ 3 phòng ngủ q7 view sông",
        "nhà hẻm xe hơi Bình Thạnh dưới 5 tỷ",
        "biệt thự liền kề ĐN hướng đông nam trên 15 tỷ quý trước",
        "Top 5 căn hộ đắt nhất tại Đà Nẵng năm nay"
    ]

    print("=" * 60)
    print("DEMO VIETNAMESE BUSINESS GLOSSARY & NORMALIZER")
    print("=" * 60)
    for q in test_cases:
        res = normalizer.normalize(q)
        print(f"\n[GỐC]: {res.original_query}")
        print(f"[CHUẨN HÓA]: {res.normalized_query}")
        print(f"[INTENT]: {res.intent.model_dump_json(exclude_none=True)}")
