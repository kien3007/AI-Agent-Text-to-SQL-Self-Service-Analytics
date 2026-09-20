"""
Response Formatter Node (Node 7 - Model 1: Qwen 3 Reasoner).
Định dạng dữ liệu đầu ra:
1. Chuẩn hóa hiển thị tiền tệ VNĐ (tỷ, triệu), diện tích (m2), tỷ lệ phần trăm.
2. Sinh cấu hình biểu đồ động Recharts JSON với nhãn tiếng Việt có dấu.
3. Sinh đoạn tóm tắt nhận định nghiệp vụ (Executive Insights) bằng tiếng Việt.
"""

from typing import Dict, Any, List, Optional
from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM


class ResponseFormatterNode:
    """Node định dạng hiển thị bảng dữ liệu, cấu hình Recharts và tóm tắt nghiệp vụ."""

    def __init__(self, llm: Optional[DualModelLLM] = None):
        self.llm = llm or DualModelLLM()

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("response_formatter")

        rows = state.query_result or []
        cols = state.column_names or []

        # 1. Định dạng dữ liệu hiển thị (Format tiền tệ, diện tích)
        formatted_rows = self._format_table_data(rows)

        # 2. Xây dựng cấu hình biểu đồ động Recharts
        chart_config = self._build_recharts_spec(rows, cols, state.user_query)
        state.chart_config = chart_config

        # 3. Sinh tóm tắt nhận định nghiệp vụ qua Reasoner
        insights_prompt = (
            f"CÂU HỎI BAN ĐẦU: \"{state.user_query}\"\n"
            f"DOMAIN: {state.domain_id}\n"
            f"SỐ DÒNG KẾT QUẢ: {len(rows)}\n"
            f"DỮ LIỆU ĐẦU RA (TỐI ĐA 5 DÒNG MẪU): {str(formatted_rows[:5])}\n\n"
            "HÃY VIẾT MỘT ĐOẠN TÓM TẮT BÁO CÁO NGHIỆP VỤ (EXECUTIVE INSIGHTS) NGẮN GỌN (2-4 câu) "
            "BẰNG TIẾNG VIỆT, NÊU BẬT CON SỐ ĐÁNG CHÚ Ý VÀ XU HƯỚNG CHÍNH DÀNH CHO LÃNH ĐẠO DOANH NGHIỆP."
        )

        insights = self.llm.generate(
            prompt=insights_prompt,
            role="reasoner",
            temperature=0.2
        )

        # 4. Đóng gói Final Response bằng Markdown
        response_parts = [
            f"### 📊 KẾT QUẢ PHÂN TÍCH CHO CÂU HỎI: \"{state.user_query}\"\n",
            f"**💡 Nhận định Chuyên sâu (Business Insights):**\n{insights}\n",
        ]

        if formatted_rows:
            response_parts.append(f"**📋 Bảng Số liệu Thống kê ({len(rows)} bản ghi):**\n")
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            response_parts.append(header)
            response_parts.append(sep)
            for r in formatted_rows[:10]:
                row_str = "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |"
                response_parts.append(row_str)
            if len(rows) > 10:
                response_parts.append(f"\n*(Đang hiển thị 10/{len(rows)} dòng dữ liệu)*")

        if state.sql_query:
            response_parts.append(f"\n```sql\n-- Câu lệnh SQL đã thực thi an toàn:\n{state.sql_query}\n```")

        state.final_response = "\n".join(response_parts)
        return state

    def _format_currency_vn(self, val: float) -> str:
        """Định dạng tiền tệ theo chuẩn Việt Nam (tỷ, triệu VNĐ)."""
        if val >= 1_000_000_000:
            ty_val = round(val / 1_000_000_000, 2)
            return f"{ty_val:g} tỷ VNĐ"
        elif val >= 1_000_000:
            tr_val = round(val / 1_000_000, 1)
            return f"{tr_val:g} triệu VNĐ"
        else:
            return f"{val:,.0f} VNĐ"

    def _format_table_data(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duyệt qua các dòng và định dạng số hiển thị thân thiện."""
        formatted = []
        for r in rows:
            new_r = {}
            for k, v in r.items():
                if isinstance(v, (int, float)):
                    k_lower = k.lower()
                    if "price" in k_lower or "amount" in k_lower or "revenue" in k_lower or "gmv" in k_lower or "cost" in k_lower:
                        new_r[k] = self._format_currency_vn(float(v))
                    elif "area" in k_lower:
                        new_r[k] = f"{round(float(v), 1)} m²"
                    elif "growth" in k_lower or "pct" in k_lower:
                        val_f = float(v)
                        sign = "+" if val_f > 0 else ""
                        if abs(val_f) <= 1.0 and val_f != 0:
                            new_r[k] = f"{sign}{round(val_f * 100, 2)}%"
                        else:
                            new_r[k] = f"{sign}{round(val_f, 2)}%"
                    elif "rate" in k_lower or "percent" in k_lower:
                        new_r[k] = f"{round(float(v) * 100, 1)}%"
                    else:
                        new_r[k] = f"{v:,}"
                else:
                    new_r[k] = v
            formatted.append(new_r)
        return formatted

    def _build_recharts_spec(
        self,
        rows: List[Dict[str, Any]],
        cols: List[str],
        query: str
    ) -> Optional[Dict[str, Any]]:
        """Tự động suy luận cấu hình biểu đồ Recharts JSON tối ưu."""
        if not rows or len(cols) < 2:
            return None

        # Tìm cột danh mục (X-axis) và cột định lượng (Y-axis)
        date_cols = [c for c in cols if any(w in c.lower() for w in ["date", "month", "year", "quarter", "at", "time"])]
        cat_cols = [c for c in cols if any(w in c.lower() for w in ["name", "type", "category", "district", "province", "status"])]
        metric_cols = [c for c in cols if any(w in c.lower() for w in ["price", "area", "count", "amount", "revenue", "gmv", "total", "avg", "metric"])]

        if not metric_cols:
            # Lấy cột số bất kỳ
            for c in cols:
                if rows and isinstance(rows[0].get(c), (int, float)):
                    metric_cols.append(c)

        if not metric_cols:
            return None

        # Quyết định loại chart
        chart_type = "bar"
        x_key = cols[0]
        if date_cols:
            chart_type = "line"
            x_key = date_cols[0]
        elif cat_cols:
            chart_type = "bar"
            x_key = cat_cols[0]

        y_key = metric_cols[0]
        metric_title = y_key.replace("_", " ").title()

        return {
            "chartType": chart_type,
            "title": f"Biểu đồ trực quan hóa dữ liệu theo {x_key}",
            "xKey": x_key,
            "yKeys": [
                {
                    "key": y_key,
                    "name": metric_title,
                    "color": "#3b82f6"
                }
            ],
            "data": rows[:20]
        }
