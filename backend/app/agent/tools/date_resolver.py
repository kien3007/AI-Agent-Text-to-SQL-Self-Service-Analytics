"""Giải mốc thời gian tương đối → khoảng ngày tuyệt đối SQL-ready."""
import re
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional, Dict

class DateResolver:
    def resolve(self, phrase: str, anchor: date = None) -> Optional[Dict]:
        anchor = anchor or date.today()
        q = phrase.lower()

        if re.search(r"tháng trước", q):
            return self._last_month(anchor)
        elif re.search(r"tháng này", q):
            return self._this_month(anchor)
        elif re.search(r"năm ngoái", q):
            return self._last_year(anchor)
        elif re.search(r"6 tháng đầu năm", q):
            return self._h1(anchor.year)
        elif re.search(r"6 tháng cuối năm", q):
            return self._h2(anchor.year)
            
        m_q = re.search(r"quý ([1-4]) năm (\d{4})", q)
        if m_q:
            return self._quarter(int(m_q.group(1)), int(m_q.group(2)))
            
        m_y = re.search(r"năm (\d{4})", q)
        if m_y:
            y = int(m_y.group(1))
            return {"start": f"{y}-01-01", "end": f"{y}-12-31", "sql_filter": f"published_year = {y}"}

        m_months = re.search(r"(\d+) tháng (gần đây|qua)", q)
        if m_months:
            return self._last_n_months(int(m_months.group(1)), anchor)

        return None  # fallback

    def _last_month(self, anchor):
        first = (anchor - relativedelta(months=1)).replace(day=1)
        last  = anchor.replace(day=1) - relativedelta(days=1)
        return {"start": str(first), "end": str(last),
                "sql_filter": f"published_date BETWEEN '{first}' AND '{last}'"}

    def _this_month(self, anchor):
        first = anchor.replace(day=1)
        return {"start": str(first), "end": str(anchor),
                "sql_filter": f"published_date BETWEEN '{first}' AND '{anchor}'"}

    def _last_year(self, anchor):
        y = anchor.year - 1
        return {"start": f"{y}-01-01", "end": f"{y}-12-31",
                "sql_filter": f"published_year = {y}"}

    def _h1(self, year):
        return {"start": f"{year}-01-01", "end": f"{year}-06-30",
                "sql_filter": f"published_date BETWEEN '{year}-01-01' AND '{year}-06-30'"}

    def _h2(self, year):
        return {"start": f"{year}-07-01", "end": f"{year}-12-31",
                "sql_filter": f"published_date BETWEEN '{year}-07-01' AND '{year}-12-31'"}

    def _quarter(self, q: int, year: int):
        starts = ["01-01", "04-01", "07-01", "10-01"]
        ends = ["03-31", "06-30", "09-30", "12-31"]
        return {"start": f"{year}-{starts[q-1]}", "end": f"{year}-{ends[q-1]}",
                "sql_filter": f"published_date BETWEEN '{year}-{starts[q-1]}' AND '{year}-{ends[q-1]}'"}
                
    def _last_n_months(self, n: int, anchor):
        first = anchor - relativedelta(months=n)
        return {"start": str(first), "end": str(anchor),
                "sql_filter": f"published_date BETWEEN '{first}' AND '{anchor}'"}
