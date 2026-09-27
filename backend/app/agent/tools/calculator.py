"""Tính toán hậu xử lý nghiệp vụ: YoY, MoM, CAGR, đơn giá."""
from typing import Optional

class BusinessCalculator:
    def yoy_growth(self, current: float, previous: float) -> Optional[float]:
        if not previous: return None
        return round((current - previous) / previous * 100, 2)

    def mom_growth(self, current: float, previous: float) -> Optional[float]:
        return self.yoy_growth(current, previous)

    def price_per_sqm(self, price: float, area: float) -> Optional[float]:
        if not area: return None
        return round(price / area, 0)

    def cagr(self, start_val: float, end_val: float, years: int) -> Optional[float]:
        if not start_val or years <= 0: return None
        return round(((end_val / start_val) ** (1 / years) - 1) * 100, 2)
