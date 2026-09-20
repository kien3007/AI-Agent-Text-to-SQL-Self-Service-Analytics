"""
Generic Vietnamese Normalizer (Bộ chuẩn hóa Tiếng Việt dùng chung cho mọi Domain).
Cung cấp các công cụ xử lý:
1. Quy đổi mốc thời gian tương đối tiếng Việt (tháng trước, quý này, năm ngoái...) thành dải ngày ISO (YYYY-MM-DD HH:MM:SS).
2. Trích xuất khoảng giá trị tiền tệ (tỷ, triệu, nghìn, tr, k...).
3. Trích xuất khoảng định lượng tổng quát (diện tích m2, số lượng, khoảng cách...).
4. Trích xuất ý định sắp xếp tổng quát (cao nhất, thấp nhất, rẻ nhất, mới nhất...).
5. Trích xuất giới hạn Top-K (Top 5, 10 bản ghi...).
"""

import re
import datetime
from typing import Dict, Any, List, Optional, Tuple


class GenericVietnameseNormalizer:
    """Bộ chuẩn hóa ngôn ngữ tự nhiên Tiếng Việt dùng chung không phụ thuộc domain."""

    def __init__(self, reference_date: Optional[datetime.date] = None):
        # Mốc thời gian tham chiếu chuẩn (mặc định 2026-03-01 theo dữ liệu gần nhất của DW)
        self.ref_date = reference_date or datetime.date(2026, 3, 1)

    def extract_relative_time(
        self,
        text: str,
        ref_date: Optional[datetime.date] = None
    ) -> Optional[Tuple[str, str, str]]:
        """
        Quy đổi các mốc thời gian tiếng Việt sang (Nhãn nhận diện, Start Datetime, End Datetime).
        Ví dụ: 'tháng trước' -> ('tháng trước', '2026-02-01 00:00:00', '2026-02-28 23:59:59')
        """
        active_ref = ref_date or self.ref_date
        year = active_ref.year
        month = active_ref.month
        cleaned = text.lower()

        # 1. Tháng tương đối
        if "tháng này" in cleaned:
            start = datetime.date(year, month, 1)
            end = datetime.date(year, month, 28) + datetime.timedelta(days=4)
            end = datetime.date(end.year, end.month, 1) - datetime.timedelta(days=1)
            return ("tháng này", start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59"))

        if "tháng trước" in cleaned:
            first_this_month = datetime.date(year, month, 1)
            last_month_end = first_this_month - datetime.timedelta(days=1)
            last_month_start = datetime.date(last_month_end.year, last_month_end.month, 1)
            return ("tháng trước", last_month_start.strftime("%Y-%m-%d 00:00:00"), last_month_end.strftime("%Y-%m-%d 23:59:59"))

        # 2. Quý tương đối
        current_quarter = (month - 1) // 3 + 1
        if "quý này" in cleaned:
            q_start_month = (current_quarter - 1) * 3 + 1
            q_end_month = current_quarter * 3
            start = datetime.date(year, q_start_month, 1)
            end = datetime.date(year, q_end_month, 28) + datetime.timedelta(days=4)
            end = datetime.date(end.year, end.month, 1) - datetime.timedelta(days=1)
            return ("quý này", start.strftime("%Y-%m-%d 00:00:00"), end.strftime("%Y-%m-%d 23:59:59"))

        if "quý trước" in cleaned:
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

        # 3. Quý chỉ định trong năm
        if "quý 1" in cleaned or "quý một" in cleaned:
            return ("quý 1", f"{year}-01-01 00:00:00", f"{year}-03-31 23:59:59")
        if "quý 2" in cleaned or "quý hai" in cleaned:
            return ("quý 2", f"{year}-04-01 00:00:00", f"{year}-06-30 23:59:59")
        if "quý 3" in cleaned or "quý ba" in cleaned:
            return ("quý 3", f"{year}-07-01 00:00:00", f"{year}-09-30 23:59:59")
        if "quý 4" in cleaned or "quý bốn" in cleaned:
            return ("quý 4", f"{year}-10-01 00:00:00", f"{year}-12-31 23:59:59")

        # 4. Năm tương đối
        if "năm ngoái" in cleaned:
            return ("năm ngoái", f"{year - 1}-01-01 00:00:00", f"{year - 1}-12-31 23:59:59")
        if "năm nay" in cleaned:
            return ("năm nay", f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59")

        # 5. Ngày tương đối
        if "hôm nay" in cleaned:
            today_str = active_ref.strftime("%Y-%m-%d")
            return ("hôm nay", f"{today_str} 00:00:00", f"{today_str} 23:59:59")
        if "hôm qua" in cleaned:
            yesterday = active_ref - datetime.timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            return ("hôm qua", f"{yesterday_str} 00:00:00", f"{yesterday_str} 23:59:59")

        return None

    def extract_currency_range(self, text: str) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """
        Trích xuất khoảng tiền tệ tiếng Việt (VNĐ).
        Trả về: (min_value, max_value, matched_text, sql_filter)
        """
        cleaned = text.lower()
        min_price = None
        max_price = None
        matched_str = None
        sql_filter = None

        # Case A: từ X đến Y tỷ / triệu
        range_match = re.search(r"từ\s*([\d\.,]+)\s*(?:đến|-)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned)
        if range_match:
            v1 = float(range_match.group(1).replace(",", "."))
            v2 = float(range_match.group(2).replace(",", "."))
            unit = range_match.group(3)
            multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
            min_price = v1 * multiplier
            max_price = v2 * multiplier
            matched_str = range_match.group(0)
            sql_filter = f"BETWEEN {min_price} AND {max_price}"
            return min_price, max_price, matched_str, sql_filter

        # Case B: 'X tỷ rưỡi' -> X.5 tỷ
        ruoi_match = re.search(r"(dưới|<|<=)?\s*(\d+)\s*(?:tỷ|tỉ)\s*rưỡi", cleaned)
        if ruoi_match:
            base_ty = float(ruoi_match.group(2)) + 0.5
            max_price = base_ty * 1_000_000_000
            matched_str = ruoi_match.group(0)
            sql_filter = f"<= {max_price}"
            return min_price, max_price, matched_str, sql_filter

        # Case C: dưới / < / <= X tỷ/triệu
        under_match = re.search(r"(dưới|<|<=|tối đa|không quá)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned)
        if under_match:
            v = float(under_match.group(2).replace(",", "."))
            unit = under_match.group(3)
            multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
            max_price = v * multiplier
            matched_str = under_match.group(0)
            sql_filter = f"<= {max_price}"
            return min_price, max_price, matched_str, sql_filter

        # Case D: trên / > / >= X tỷ/triệu
        above_match = re.search(r"(trên|>|>=|tối thiểu|hơn)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu|tr|ty|củ)", cleaned)
        if above_match:
            v = float(above_match.group(2).replace(",", "."))
            unit = above_match.group(3)
            multiplier = 1_000_000_000 if unit in ["tỷ", "tỉ", "ty"] else 1_000_000
            min_price = v * multiplier
            matched_str = above_match.group(0)
            sql_filter = f">= {min_price}"
            return min_price, max_price, matched_str, sql_filter

        return None, None, None, None

    def extract_numeric_range(
        self,
        text: str,
        unit_regex: str
    ) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """
        Trích xuất khoảng định lượng kèm đơn vị (ví dụ: m2, mét vuông, đơn, kg...).
        Trả về: (min_val, max_val, matched_text, sql_filter)
        """
        cleaned = text.lower()
        # Range: từ X đến Y <đơn_vị>
        range_m = re.search(rf"từ\s*([\d\.,]+)\s*(?:đến|-)\s*([\d\.,]+)\s*(?:{unit_regex})", cleaned)
        if range_m:
            min_v = float(range_m.group(1).replace(",", "."))
            max_v = float(range_m.group(2).replace(",", "."))
            return min_v, max_v, range_m.group(0), f"BETWEEN {min_v} AND {max_v}"

        # Under: dưới / <= X <đơn_vị>
        under_m = re.search(rf"(?:dưới|<|<=|tối đa|không quá)\s*([\d\.,]+)\s*(?:{unit_regex})", cleaned)
        if under_m:
            max_v = float(under_m.group(1).replace(",", "."))
            return None, max_v, under_m.group(0), f"<= {max_v}"

        # Above: trên / >= X <đơn_vị>
        above_m = re.search(rf"(?:trên|>|>=|tối thiểu|hơn)\s*([\d\.,]+)\s*(?:{unit_regex})", cleaned)
        if above_m:
            min_v = float(above_m.group(1).replace(",", "."))
            return min_v, None, above_m.group(0), f">= {min_v}"

        return None, None, None, None

    def extract_limit(self, text: str, entity_keywords: Optional[List[str]] = None) -> Optional[Tuple[int, str]]:
        """
        Trích xuất giới hạn Top-K (VD: 'top 5', 'top 10', 'lấy 5 đơn', 'lấy 10 căn').
        Trả về: (limit_number, matched_text)
        """
        cleaned = text.lower()
        entity_pattern = ""
        if entity_keywords:
            kw_escaped = "|".join(re.escape(k) for k in entity_keywords)
            entity_pattern = rf"|\b(\d+)\s*(?:{kw_escaped})\b"

        pattern = rf"\b(?:top|lấy)\s*(\d+)\b{entity_pattern}"
        match = re.search(pattern, cleaned)
        if match:
            cand = int(match.group(1) or match.group(2))
            if 1 <= cand <= 1000:
                return cand, match.group(0).strip()
        return None
