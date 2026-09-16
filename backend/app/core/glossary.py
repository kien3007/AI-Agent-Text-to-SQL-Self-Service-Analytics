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

class VietnameseBusinessGlossary:
    """
    Bộ tiền xử lý chuẩn hóa câu hỏi Bất động sản Tiếng Việt (Business Glossary & Normalizer).
    Chức năng:
    1. Chuẩn hóa từ lóng, viết tắt ngành BĐS: 2PN, 3PN, 2WC, duplex, penthouse, chung cư mini, đất thổ cư...
    2. Quy đổi các mốc thời gian tương đối: 'quý này', 'tháng trước', 'năm ngoái', 'quý 3'... thành dải ngày cụ thể.
    3. Trích xuất khoảng giá (tỷ, triệu, tr, củ, tỷ rưỡi) và diện tích (m2).
    4. Suy luận quan hệ địa lý (Quận -> Tỉnh).
    5. Cung cấp metadata có cấu trúc (NormalizedIntent) cho Query Planner & SQL Generator.
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

    def __init__(self, reference_date: Optional[datetime.date] = None):
        # Mốc thời gian tham chiếu (theo dữ liệu gần nhất: 2026-03-01)
        self.ref_date = reference_date or datetime.date(2026, 3, 1)

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
        # Regex cho dạng quận viết tắt: q1, q2, q.7, quan 7...
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

        # 7. Trích xuất Giá tiền (dưới 3 tỷ, từ 2 đến 3 tỷ rưỡi, trên 800tr...)
        # Case A: từ X đến Y tỷ / triệu
        range_match = re.search(r"từ\s*([\d\.,]+)\s*(?:đến|-)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned_text)
        if range_match:
            v1 = float(range_match.group(1).replace(",", "."))
            v2 = float(range_match.group(2).replace(",", "."))
            unit = range_match.group(3)
            multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
            min_price = v1 * multiplier
            max_price = v2 * multiplier
            mapped_terms.append((range_match.group(0), f"price BETWEEN {min_price} AND {max_price}"))
        else:
            # Case B: xử lý 'X tỷ rưỡi' -> X.5 tỷ
            ruoi_match = re.search(r"(dưới|<|<=)?\s*(\d+)\s*(?:tỷ|tỉ)\s*rưỡi", cleaned_text)
            if ruoi_match:
                base_ty = float(ruoi_match.group(2)) + 0.5
                max_price = base_ty * 1_000_000_000
                mapped_terms.append((ruoi_match.group(0), f"price <= {max_price}"))
            else:
                # Case C: dưới / < / <= X tỷ/triệu
                under_match = re.search(r"(dưới|<|<=|tối đa|không quá)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned_text)
                if under_match:
                    v = float(under_match.group(2).replace(",", "."))
                    unit = under_match.group(3)
                    multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
                    max_price = v * multiplier
                    mapped_terms.append((under_match.group(0), f"price <= {max_price}"))

                # Case D: trên / > / >= X tỷ/triệu
                above_match = re.search(r"(trên|>|>=|tối thiểu|hơn)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned_text)
                if above_match:
                    v = float(above_match.group(2).replace(",", "."))
                    unit = above_match.group(3)
                    multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
                    min_price = v * multiplier
                    mapped_terms.append((above_match.group(0), f"price >= {min_price}"))

        # 8. Trích xuất Diện tích (m2)
        area_range = re.search(r"từ\s*([\d\.,]+)\s*(?:đến|-)\s*([\d\.,]+)\s*(m2|mét vuông)", cleaned_text)
        if area_range:
            min_area = float(area_range.group(1).replace(",", "."))
            max_area = float(area_range.group(2).replace(",", "."))
            mapped_terms.append((area_range.group(0), f"area BETWEEN {min_area} AND {max_area}"))
        else:
            area_under = re.search(r"(dưới|<|<=)\s*([\d\.,]+)\s*(m2|mét vuông)", cleaned_text)
            if area_under:
                max_area = float(area_under.group(2).replace(",", "."))
                mapped_terms.append((area_under.group(0), f"area <= {max_area}"))

            area_above = re.search(r"(trên|>|>=)\s*([\d\.,]+)\s*(m2|mét vuông)", cleaned_text)
            if area_above:
                min_area = float(area_above.group(2).replace(",", "."))
                mapped_terms.append((area_above.group(0), f"area >= {min_area}"))

        # 9. Quy đổi mốc thời gian tương đối
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

        # 11. Trích xuất Giới hạn (LIMIT: 'top 5', 'top 10', 'lấy 5 căn'...)
        top_match = re.search(r"\b(?:top|lấy)\s*(\d+)\b|\b(\d+)\s*(?:căn|bản ghi|tin|lô đất)\b", cleaned_text)
        if top_match:
            cand_limit = int(top_match.group(1) or top_match.group(2))
            if 1 <= cand_limit <= 500:
                limit = cand_limit
                matched_str = top_match.group(0).strip()
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
        """Quy đổi các mốc thời gian tiếng Việt sang (Nhãn, Start Date, End Date)."""
        year = self.ref_date.year
        month = self.ref_date.month

        if "tháng này" in text:
            start = datetime.date(year, month, 1)
            end = datetime.date(year, month, 28) + datetime.timedelta(days=4)
            end = datetime.date(end.year, end.month, 1) - datetime.timedelta(days=1)
            return ("tháng này", start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59"))

        if "tháng trước" in text:
            first_this_month = datetime.date(year, month, 1)
            last_month_end = first_this_month - datetime.timedelta(days=1)
            last_month_start = datetime.date(last_month_end.year, last_month_end.month, 1)
            return ("tháng trước", last_month_start.strftime("%Y-%m-%d 00:00:00"), last_month_end.strftime("%Y-%m-%d 23:59:59"))

        # Quý tương đối
        current_quarter = (month - 1) // 3 + 1
        if "quý này" in text:
            q_start_month = (current_quarter - 1) * 3 + 1
            q_end_month = current_quarter * 3
            start = datetime.date(year, q_start_month, 1)
            end = datetime.date(year, q_end_month, 28) + datetime.timedelta(days=4)
            end = datetime.date(end.year, end.month, 1) - datetime.timedelta(days=1)
            return ("quý này", start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59"))

        if "quý trước" in text:
            prev_quarter = current_quarter - 1
            prev_year = year
            if prev_quarter == 0:
                prev_quarter = 4
                prev_year -= 1
            q_start_month = (prev_quarter - 1) * 3 + 1
            q_end_month = prev_quarter * 3
            start = datetime.date(prev_year, q_start_month, 1)
            end = datetime.date(prev_year, q_end_month, 28) + datetime.timedelta(days=4)
            end = datetime.date(end.year, end.month, 1) - datetime.timedelta(days=1)
            return ("quý trước", start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59"))

        # Quý chỉ định
        if "quý 1" in text or "quý một" in text:
            return ("quý 1", f"{year}-01-01 00:00:00", f"{year}-03-31 23:59:59")
        if "quý 2" in text or "quý hai" in text:
            return ("quý 2", f"{year}-04-01 00:00:00", f"{year}-06-30 23:59:59")
        if "quý 3" in text or "quý ba" in text:
            return ("quý 3", f"{year}-07-01 00:00:00", f"{year}-09-30 23:59:59")
        if "quý 4" in text or "quý bốn" in text:
            return ("quý 4", f"{year}-10-01 00:00:00", f"{year}-12-31 23:59:59")

        if "năm ngoái" in text:
            return ("năm ngoái", f"{year - 1}-01-01 00:00:00", f"{year - 1}-12-31 23:59:59")
        if "năm nay" in text:
            return ("năm nay", f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59")

        return None

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
