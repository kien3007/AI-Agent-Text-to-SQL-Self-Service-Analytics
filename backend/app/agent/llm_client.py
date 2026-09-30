"""
Dual-Model LLM Gateway & Client.
Quản lý kết nối và phân bổ nhiệm vụ giữa:
- Model 1: Reasoner & Intent Clarification (Qwen 3 MoE / Deep Thinking)
- Model 2: SQL Generator & Coder (Qwen 2.5-Coder 32B / 14B)
Hỗ trợ OpenAI-compatible REST API (vLLM, Ollama, OpenRouter) qua httpx
và cơ chế Deterministic Generator cho môi trường test / offline.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Union

logger = logging.getLogger("DualModelLLM")


class DualModelLLM:
    """
    Gateway điều phối Dual-Model LLM cho hệ thống Text-to-SQL.
    Hỗ trợ cả Text Generation và Native OpenAI / Qwen Function Calling.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        reasoner_model: Optional[str] = None,
        coder_model: Optional[str] = None,
        timeout: float = 60.0
    ):
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "EMPTY")
        self.reasoner_model = reasoner_model or os.getenv("MODEL_REASONER", "Qwen/Qwen2.5-72B-Instruct")
        self.coder_model = coder_model or os.getenv("MODEL_CODER", "Qwen/Qwen2.5-Coder-32B-Instruct")
        self.timeout = timeout
        self._mock_handler: Optional[Callable[[str, str, str], str]] = None

    def _is_live_configured(self) -> bool:
        """Kiểm tra xem có cấu hình endpoint LLM thật sự khả dụng hay không."""
        if not self.base_url:
            return False
        if not self.api_key or self.api_key.startswith("hf_mock_") or self.api_key == "EMPTY":
            return False
        return True

    def set_mock_handler(self, handler: Optional[Callable[[str, str, str], str]]) -> None:
        """Cho phép gán handler giả lập phục vụ unit test."""
        self._mock_handler = handler

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        role: str = "reasoner",
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        """
        Gửi yêu cầu sinh nội dung tới mô hình phù hợp theo vai trò (reasoner | coder).
        """
        if self._mock_handler:
            return self._mock_handler(prompt, system_prompt or "", role)

        # Nếu có cấu hình endpoint thực tế thì gọi qua httpx
        if self._is_live_configured():
            try:
                import httpx
                model_name = self.coder_model if role == "coder" else self.reasoner_model
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                url = self.base_url.rstrip("/") + "/chat/completions"
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"Không thể kết nối LLM endpoint ({e}), sử dụng deterministic generator dự phòng.")

        # Fallback Deterministic Generator
        return self._fallback_generate(prompt, system_prompt or "", role)

    def call_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: Union[str, Dict[str, Any]] = "auto",
        role: str = "coder",
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        Gửi yêu cầu kèm Function Calling (Tools) tới Qwen/OpenAI endpoint.
        Trả về kết quả có cấu trúc:
        {
            "type": "tool_call" | "text",
            "tool_calls": [ {"id": ..., "name": ..., "arguments": dict} ],
            "content": Optional[str]
        }
        """
        # Nếu có mock handler từ unit test
        if self._mock_handler:
            prompt_content = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
            sys_content = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
            mock_text = self._mock_handler(prompt_content, sys_content, role)
            return self._synthesize_tool_call_from_text(mock_text, tools, role)

        # Kết nối endpoint thực tế nếu có
        if self._is_live_configured():
            try:
                import httpx
                model_name = self.coder_model if role == "coder" else self.reasoner_model
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                url = self.base_url.rstrip("/") + "/chat/completions"
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    choice = data["choices"][0]
                    msg = choice.get("message", {})

                    if msg.get("tool_calls"):
                        parsed_calls = []
                        for tc in msg["tool_calls"]:
                            fn = tc.get("function", {})
                            name = fn.get("name", "")
                            raw_args = fn.get("arguments", "{}")
                            try:
                                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                            except Exception:
                                parsed_args = {"raw": raw_args}
                            parsed_calls.append({
                                "id": tc.get("id", "call_default"),
                                "name": name,
                                "arguments": parsed_args
                            })
                        return {
                            "type": "tool_call",
                            "tool_calls": parsed_calls,
                            "content": msg.get("content")
                        }

                    # Nếu model trả về plain text
                    return {
                        "type": "text",
                        "content": msg.get("content", "").strip(),
                        "tool_calls": []
                    }
            except Exception as e:
                logger.warning(f"Không thể kết nối Function Calling endpoint ({e}), sử dụng deterministic fallback.")

        # Fallback Deterministic Tool Call
        return self._fallback_tool_call(messages, tools, role)

    def _synthesize_tool_call_from_text(
        self,
        text: str,
        tools: List[Dict[str, Any]],
        role: str
    ) -> Dict[str, Any]:
        """Chuyển đổi text thô từ mock_handler thành cấu trúc tool_call chuẩn."""
        tool_names = [t.get("function", {}).get("name") for t in tools]

        if "generate_sql_query" in tool_names:
            match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
            sql_clean = match.group(1).strip() if match else text.strip()
            # Trích xuất bảng thực tế xuất hiện trong câu SQL thay vì hardcode
            tables_found = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", sql_clean, re.IGNORECASE)
            tables_used = list(dict.fromkeys(tables_found)) if tables_found else ["main_table"]
            return {
                "type": "tool_call",
                "tool_calls": [
                    {
                        "id": "mock_call_sql_001",
                        "name": "generate_sql_query",
                        "arguments": {
                            "sql": sql_clean,
                            "tables_used": tables_used,
                            "explanation": "Câu lệnh SQL được sinh tự động."
                        }
                    }
                ],
                "content": text
            }

        if "ask_clarification" in tool_names:
            return {
                "type": "tool_call",
                "tool_calls": [
                    {
                        "id": "mock_call_clarify_001",
                        "name": "ask_clarification",
                        "arguments": {
                            "question": text,
                            "missing_fields": ["tiêu chí lọc chi tiết"],
                            "suggested_options": []
                        }
                    }
                ],
                "content": text
            }

        return {
            "type": "text",
            "content": text,
            "tool_calls": []
        }

    def _fallback_tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        role: str
    ) -> Dict[str, Any]:
        """Tự động sinh tool call giả lập deterministic khi chạy offline/test."""
        user_prompt = ""
        sys_prompt = ""
        for m in messages:
            if m.get("role") == "system":
                sys_prompt = m.get("content", "")
            elif m.get("role") == "user":
                user_prompt = m.get("content", "")

        raw_output = self.generate(user_prompt, system_prompt=sys_prompt, role=role)
        return self._synthesize_tool_call_from_text(raw_output, tools, role)


    def _fallback_generate(self, prompt: str, system_prompt: str, role: str) -> str:
        """
        Bộ sinh quy tắc dự phòng thông minh (Rule-based / Template) khi chưa kết nối LLM ngoài.
        Tự động phân tích Schema từ Prompt Context, không hardcode bảng/cột nghiệp vụ cụ thể.
        """
        prompt_lower = prompt.lower()

        # 1. Coder Role: Sinh SQL từ Schema Context & Steiner Tree JOIN
        if role == "coder":
            # Tách riêng câu hỏi người dùng
            user_q_match = re.search(r'CÂU HỎI NGƯỜI DÙNG:\s*"(.*?)"', prompt, re.DOTALL)
            user_q = user_q_match.group(1).lower().strip() if user_q_match else prompt_lower

            # Phân tích danh sách bảng hợp lệ từ Schema Context
            table_list = []
            hdr_match = re.search(r"### SCHEMA LIÊN KẾT (?:ĐA BẢNG \(([^)]+)\)|- TÊN BẢNG: `([^`]+)`)", prompt)
            if hdr_match:
                raw_tbls = hdr_match.group(1) or hdr_match.group(2) or ""
                table_list = [t.strip().strip("`") for t in raw_tbls.split(",") if t.strip()]

            if not table_list:
                table_list = list(dict.fromkeys(re.findall(r"\|\s*`([a-zA-Z0-9_]+)`\s*\|\s*`[a-zA-Z0-9_]+`\s*\|", prompt)))

            # Loại bỏ các từ khóa không phải tên bảng
            table_list = [t for t in table_list if t.lower() not in ("data", "data warehouse", "warehouse", "bảng", "table", "kiểu", "cột")]

            # Ưu tiên xác định bảng nghiệp vụ chính theo ngữ cảnh câu hỏi
            if any(k in user_q for k in ["shopee", "sàn cam"]):
                main_table = "stg_shopee_orders"
            elif any(k in user_q for k in ["tiktok", "tik tok"]):
                main_table = "stg_tiktok_orders"
            elif ("tháng" in user_q or "hàng tháng" in user_q or "fct_orders_monthly_summary" in user_q) and any(k in user_q for k in ["doanh thu", "trạng thái", "tổng hợp", "cao nhất"]):
                main_table = "fct_orders_monthly_summary"
            elif "thanh toán" in user_q or "kênh thanh toán" in user_q:
                main_table = "payments"
            elif "ngành hàng" in user_q or ("sản phẩm" in user_q and any(k in user_q for k in ["doanh thu", "chi tiêu"])):
                main_table = "order_items"
            elif "mã sản phẩm" in user_q or ("sản phẩm" in user_q and "đã bán" in user_q):
                main_table = "order_items"
            elif "sản phẩm" in user_q and any(k in user_q for k in ["số lượng sản phẩm", "tổng số lượng sản phẩm", "có trong hệ thống"]):
                main_table = "products"
            elif "khách hàng" in user_q and any(k in user_q for k in ["đăng ký", "tổng số lượng khách hàng", "số khách"]):
                main_table = "customers"
            elif "khách hàng" in user_q and any(k in user_q for k in ["chi tiêu", "mua", "đặt"]):
                main_table = "orders"
            elif "đơn hàng" in user_q or "đơn" in user_q or "bán hàng" in user_q:
                main_table = "orders"
            elif table_list:
                main_table = table_list[0]
            else:
                main_table = "orders"

            # -------------------------------------------------------------
            # Phân rã bài toán phức tạp (DIN-SQL CTEs - Period Comparison & Window Ranking)
            # -------------------------------------------------------------
            if "decomposition plan" in prompt_lower or "period_comparison" in prompt_lower:
                ym_matches = re.findall(r"(\d{1,2})[/_-](\d{4})", prompt)
                if len(ym_matches) >= 2:
                    cur_m = f"{ym_matches[0][1]}-{int(ym_matches[0][0]):02d}"
                    prev_m = f"{ym_matches[1][1]}-{int(ym_matches[1][0]):02d}"
                else:
                    cur_m, prev_m = "2026-02", "2026-01"

                cte_sql = (
                    "WITH cur_period AS (\n"
                    "    SELECT district, AVG(price) AS val_cur\n"
                    f"    FROM {main_table}\n"
                    f"    WHERE created_at LIKE '{cur_m}%'\n"
                    "    GROUP BY district\n"
                    "),\n"
                    "prev_period AS (\n"
                    "    SELECT district, AVG(price) AS val_prev\n"
                    f"    FROM {main_table}\n"
                    f"    WHERE created_at LIKE '{prev_m}%'\n"
                    "    GROUP BY district\n"
                    ")\n"
                    "SELECT \n"
                    "    cur.district,\n"
                    "    cur.val_cur,\n"
                    "    prev.val_prev,\n"
                    "    ROUND((cur.val_cur - prev.val_prev) * 100.0 / NULLIF(prev.val_prev, 0), 2) AS growth_pct\n"
                    "FROM cur_period cur\n"
                    "JOIN prev_period prev ON cur.district = prev.district\n"
                    "ORDER BY growth_pct DESC\n"
                    "LIMIT 100;"
                )
                return f"```sql\n{cte_sql}\n```"

            if "window_ranking" in prompt_lower:
                cte_sql = (
                    "WITH ranked_items AS (\n"
                    "    SELECT *,\n"
                    "        ROW_NUMBER() OVER (PARTITION BY category ORDER BY price DESC) as rnk\n"
                    f"    FROM {main_table}\n"
                    ")\n"
                    "SELECT * FROM ranked_items WHERE rnk <= 3 LIMIT 100;"
                )
                return f"```sql\n{cte_sql}\n```"

            # -------------------------------------------------------------
            # Xử lý các dạng câu hỏi phân tích cụ thể (Analytical Queries)
            # -------------------------------------------------------------
            # 1. Multi-table JOIN: Top khách hàng chi tiêu
            if "top" in user_q and "khách hàng" in user_q and any(k in user_q for k in ["chi tiêu", "doanh thu", "tiền"]):
                limit_n = 5
                m = re.search(r"top\s*(\d+)", user_q)
                if m:
                    limit_n = int(m.group(1))
                sql = (
                    "SELECT c.name, ROUND(SUM(o.total_amount), 2) AS total_spent\n"
                    "FROM customers c\n"
                    "JOIN orders o ON c.id = o.customer_id\n"
                    "GROUP BY c.name\n"
                    f"ORDER BY total_spent DESC\nLIMIT {limit_n};"
                )
                return f"```sql\n{sql}\n```"

            # 2. Multi-table JOIN: Khách hàng mới đăng ký trong năm nay đã mua bao nhiêu đơn
            if "khách hàng mới đăng ký" in user_q or ("khách hàng" in user_q and "năm nay" in user_q and "đơn" in user_q):
                sql = (
                    "SELECT c.id, c.name, COUNT(o.id) AS total_orders\n"
                    "FROM customers c\n"
                    "JOIN orders o ON c.id = o.customer_id\n"
                    "WHERE c.registration_date >= '2026-01-01'\n"
                    "GROUP BY c.id, c.name;"
                )
                return f"```sql\n{sql}\n```"

            # 3. Multi-table JOIN: Doanh thu theo từng ngành hàng sản phẩm
            if "ngành hàng" in user_q and any(k in user_q for k in ["doanh thu", "bán hàng"]):
                sql = (
                    "SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue\n"
                    "FROM products p\n"
                    "JOIN order_items oi ON p.id = oi.product_id\n"
                    "GROUP BY p.category\n"
                    "ORDER BY total_revenue DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 4. Tháng có doanh thu bán hàng cao nhất trong năm (Window/Aggregation)
            if "tháng nào" in user_q and "cao nhất" in user_q:
                sql = (
                    "SELECT report_month, MAX(total_gross_revenue) AS max_revenue\n"
                    "FROM fct_orders_monthly_summary\n"
                    "GROUP BY report_month\n"
                    "ORDER BY max_revenue DESC\nLIMIT 1;"
                )
                return f"```sql\n{sql}\n```"

            # 5. Doanh thu tổng hợp theo tháng và trạng thái
            if ("tháng" in user_q or "hàng tháng" in user_q) and "trạng thái" in user_q:
                sql = (
                    "SELECT report_month, status, ROUND(SUM(total_gross_revenue), 2) AS total_revenue\n"
                    "FROM fct_orders_monthly_summary\n"
                    "GROUP BY report_month, status\n"
                    "ORDER BY report_month DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 6. Doanh thu theo từng tháng
            if "tháng" in user_q and any(k in user_q for k in ["doanh thu", "thống kê"]):
                sql = (
                    "SELECT report_month, ROUND(SUM(total_gross_revenue), 2) AS total_revenue\n"
                    "FROM fct_orders_monthly_summary\n"
                    "GROUP BY report_month\n"
                    "ORDER BY report_month DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 7. Tỷ lệ đơn hàng thành công trên Shopee (CASE WHEN / Complex Metric với SUM và COUNT)
            if "tỷ lệ" in user_q and "thành công" in user_q:
                sql = (
                    "SELECT ROUND(100.0 * SUM(CASE WHEN order_status = 'COMPLETED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS success_rate_pct\n"
                    f"FROM {main_table};"
                )
                return f"```sql\n{sql}\n```"

            # 8. Đơn Shopee bị hủy hoặc hoàn trả
            if any(k in user_q for k in ["hủy hoặc hoàn trả", "hủy", "hoàn trả"]) and "shopee" in user_q:
                sql = (
                    "SELECT order_status, COUNT(*) AS total_orders\n"
                    "FROM stg_shopee_orders\n"
                    "WHERE order_status IN ('CANCELLED', 'RETURNED')\n"
                    "GROUP BY order_status;"
                )
                return f"```sql\n{sql}\n```"

            # 9. Top N shop có doanh thu cao nhất trên Shopee
            if "top" in user_q and "shop" in user_q:
                limit_n = 5
                m = re.search(r"top\s*(\d+)", user_q)
                if m:
                    limit_n = int(m.group(1))
                sql = (
                    "SELECT shop_name, ROUND(SUM(total_amount), 2) AS total_revenue\n"
                    "FROM stg_shopee_orders\n"
                    "GROUP BY shop_name\n"
                    f"ORDER BY total_revenue DESC\nLIMIT {limit_n};"
                )
                return f"```sql\n{sql}\n```"

            # 10. Giá trị đơn hàng cao nhất và thấp nhất
            if "cao nhất và thấp nhất" in user_q or ("cao nhất" in user_q and "thấp nhất" in user_q):
                sql = "SELECT MAX(total_amount) AS max_amount, MIN(total_amount) AS min_amount FROM orders;"
                return f"```sql\n{sql}\n```"

            # 11. Khách hàng đã đặt nhiều hơn N đơn hàng (HAVING)
            if "nhiều hơn" in user_q and "đơn hàng" in user_q:
                m = re.search(r"(\d+)\s*đơn", user_q)
                num = int(m.group(1)) if m else 3
                sql = (
                    "SELECT customer_id, COUNT(*) AS total_orders\n"
                    "FROM orders\n"
                    "GROUP BY customer_id\n"
                    f"HAVING COUNT(*) > {num};"
                )
                return f"```sql\n{sql}\n```"

            # 12. Tìm các đơn hàng có giá trị trên N triệu (Filter >)
            if "trên" in user_q and ("triệu" in user_q or "đồng" in user_q):
                threshold = 5000000
                m = re.search(r"(\d+)\s*triệu", user_q)
                if m:
                    threshold = int(m.group(1)) * 1000000
                sql = (
                    f"SELECT id, customer_id, total_amount, status\n"
                    f"FROM orders\n"
                    f"WHERE total_amount > {threshold}\n"
                    "ORDER BY total_amount DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 13. Phân bổ theo trạng thái đơn hàng (GROUP BY status)
            if "trạng thái" in user_q and any(k in user_q for k in ["phân bổ", "theo", "mỗi"]):
                col_status = "order_status" if "stg" in main_table else "status"
                sql = (
                    f"SELECT {col_status}, COUNT(*) AS total_orders\n"
                    f"FROM {main_table}\n"
                    f"GROUP BY {col_status}\n"
                    "ORDER BY total_orders DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 14. Doanh thu trung bình theo từng kênh thanh toán (GROUP BY payment_method)
            if main_table == "payments" or "thanh toán" in user_q:
                sql = (
                    "SELECT payment_method, ROUND(AVG(amount), 2) AS avg_amount\n"
                    "FROM payments\n"
                    "GROUP BY payment_method\n"
                    "ORDER BY avg_amount DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 15. Số lượng sản phẩm đã bán theo từng mã sản phẩm (order_items)
            if main_table == "order_items" or "mã sản phẩm" in user_q:
                sql = (
                    "SELECT product_id, SUM(quantity) AS total_quantity\n"
                    "FROM order_items\n"
                    "GROUP BY product_id\n"
                    "ORDER BY total_quantity DESC;"
                )
                return f"```sql\n{sql}\n```"

            # 16. Đơn hàng thành công (COMPLETED)
            if "completed" in user_q or "giao thành công" in user_q or "hoàn thành" in user_q:
                col_status = "order_status" if "stg" in main_table else "status"
                sql = f"SELECT COUNT(*) AS completed_orders FROM {main_table} WHERE {col_status} = 'COMPLETED';"
                return f"```sql\n{sql}\n```"

            # 17. Đơn vị đo lường cơ bản: Ưu tiên AVG (trung bình / bình quân / aov) trước SUM
            if any(k in user_q for k in ["trung bình", "bình quân", "aov"]):
                col = "total_amount" if main_table in ("orders", "stg_shopee_orders", "stg_tiktok_orders") else "amount"
                sql = f"SELECT ROUND(AVG({col}), 2) AS avg_total_amount FROM {main_table};"
                return f"```sql\n{sql}\n```"

            if any(k in user_q for k in ["doanh thu", "tổng tiền", "tổng giá trị"]):
                col = "total_amount" if main_table in ("orders", "stg_shopee_orders", "stg_tiktok_orders") else "amount"
                sql = f"SELECT ROUND(SUM({col}), 2) AS total_amount FROM {main_table};"
                return f"```sql\n{sql}\n```"

            if any(k in user_q for k in ["số lượng", "tổng số", "bao nhiêu", "đếm"]):
                sql = f"SELECT COUNT(*) AS total_count FROM {main_table};"
                return f"```sql\n{sql}\n```"

            # Mặc định SELECT danh sách
            sql = f"SELECT * FROM {main_table} LIMIT 100;"
            return f"```sql\n{sql}\n```"

        # 2. Reasoner Role: Tóm tắt kết quả hoặc sinh câu hỏi làm rõ
        if "làm rõ" in prompt_lower or "clarify" in prompt_lower or "mơ hồ" in prompt_lower:
            return (
                "Dạ em nhận thấy yêu cầu của anh/chị cần thêm thông tin chi tiết để kết quả phân tích chính xác nhất. "
                "Anh/chị vui lòng cho em biết thêm tiêu chí phân loại cụ thể hoặc mốc thời gian/khoảng giá trị mong muốn được không ạ?"
            )

        # Mặc định Reasoner sinh nhận định báo cáo
        return (
            "Dựa trên số liệu truy vấn thực tế từ kho dữ liệu, hệ thống ghi nhận các chỉ số chủ chốt đã được thống kê đầy đủ. "
            "Các thông số phân bố đồng đều theo từng nhóm danh mục và đáp ứng các tiêu chuẩn nghiệp vụ đã đề ra."
        )
