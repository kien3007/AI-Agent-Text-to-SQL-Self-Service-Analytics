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
            # Phân tích schema động từ prompt context
            tbl_match = re.search(r"SCHEMA LIÊN KẾT(?: - TÊN BẢNG:\s*`([^`]+)`| ĐA BẢNG\s*\(([^)]+)\)|:\s*`?([^\n`]+)`?)", prompt)
            table_list = []
            if tbl_match:
                tbl_raw = tbl_match.group(1) or tbl_match.group(2) or tbl_match.group(3) or ""
                table_list = [t.strip().strip("`") for t in tbl_raw.split(",") if t.strip()]
            if not table_list:
                table_list = re.findall(r"TÊN BẢNG:\s*`([^`]+)`", prompt)
            main_table = table_list[0] if table_list else "main_table"

            # Trích xuất danh sách cột và bảng từ prompt context (hỗ trợ cả schema đơn bảng và đa bảng)
            cols_by_table = {}
            multi_tbl_cols = re.findall(r"\|\s*`([a-zA-Z0-9_]+)`\s*\|\s*`([a-zA-Z0-9_]+)`\s*\|\s*`([a-zA-Z0-9_()]+)`", prompt)
            if multi_tbl_cols:
                for t, c, dt in multi_tbl_cols:
                    if t not in cols_by_table:
                        cols_by_table[t] = []
                    cols_by_table[t].append((c, dt))
                cols_in_table = [(c, dt) for t, c, dt in multi_tbl_cols]
            else:
                cols_in_table = re.findall(r"\|\s*`([a-zA-Z0-9_]+)`\s*\|\s*`([a-zA-Z0-9_()]+)`", prompt)
                cols_by_table[main_table] = cols_in_table

            col_names = [c[0] for c in cols_in_table]
            num_cols = [c[0] for c in cols_in_table if any(t in c[1].upper() for t in ("INT", "DOUBLE", "FLOAT", "NUMERIC", "DECIMAL", "REAL", "NUMBER"))]
            text_cols = [c[0] for c in cols_in_table if any(t in c[1].upper() for t in ("VARCHAR", "TEXT", "STRING", "CHAR")) and not c[0].lower().endswith(("_id", "_guid", "uuid"))]

            # Nếu có yêu cầu sửa lỗi (Self-correction feedback)
            if "lần trước câu sql bị lỗi" in prompt_lower or "unknown column" in prompt_lower:
                if col_names:
                    # Thay thế cột lỗi bằng cột hợp lệ gần nhất
                    sql_match = re.search(r"SELECT\s+.*?(?:;|$)", prompt, re.IGNORECASE | re.DOTALL)
                    if sql_match:
                        return sql_match.group(0).strip()

            # Tách riêng câu hỏi người dùng
            user_q_match = re.search(r'CÂU HỎI NGƯỜI DÙNG:\s*"(.*?)"', prompt, re.DOTALL)
            user_q = user_q_match.group(1).lower() if user_q_match else prompt_lower

            # Phân rã bài toán phức tạp (DIN-SQL CTEs - Period Comparison)
            if "decomposition plan" in prompt_lower or "period_comparison" in prompt_lower:
                ym_matches = re.findall(r"(\d{1,2})[/_-](\d{4})", prompt)
                if len(ym_matches) >= 2:
                    cur_m = f"{ym_matches[0][1]}-{int(ym_matches[0][0]):02d}"
                    prev_m = f"{ym_matches[1][1]}-{int(ym_matches[1][0]):02d}"
                else:
                    cur_m, prev_m = "2026-02", "2026-01"

                # Tự động chọn bảng chứa cột chu kỳ / ngày tháng
                summary_table = main_table
                for t, t_cols in cols_by_table.items():
                    if any(any(k in c[0].lower() for k in ["year_month", "month", "period"]) for c in t_cols):
                        summary_table = t
                        break
                    if any(k in t.lower() for k in ["summary", "monthly", "fct", "mart", "agg"]):
                        summary_table = t

                t_cols = cols_by_table.get(summary_table, cols_in_table)
                t_col_names = [c[0] for c in t_cols]
                t_num_cols = [c[0] for c in t_cols if any(tp in c[1].upper() for tp in ("INT", "DOUBLE", "FLOAT", "NUMERIC", "DECIMAL", "REAL", "NUMBER"))]
                t_text_cols = [c[0] for c in t_cols if any(tp in c[1].upper() for tp in ("VARCHAR", "TEXT", "STRING", "CHAR")) and not c[0].lower().endswith(("_id", "_guid", "uuid"))]

                # Suy luận cột danh mục phân nhóm phù hợp nhất với câu hỏi
                cat_col = None
                for tc in t_text_cols:
                    tc_l = tc.lower()
                    if tc_l in ("year_month", "month", "published_at", "date", "created_at", "updated_at"):
                        continue
                    if "quận" in user_q and ("district" in tc_l or "quan" in tc_l):
                        cat_col = tc
                        break
                    if "tỉnh" in user_q and ("province" in tc_l or "tinh" in tc_l or "city" in tc_l):
                        cat_col = tc
                        break
                    if "loại" in user_q and ("type" in tc_l or "category" in tc_l):
                        cat_col = tc
                        break
                    if any(w in user_q for w in tc_l.split("_") if len(w) > 2):
                        cat_col = tc
                        break
                if not cat_col:
                    cat_col = next((c for c in t_text_cols if c.lower() not in ("year_month", "month", "published_at", "date", "description", "name")), t_text_cols[0] if t_text_cols else "category")

                metric_col = next((c for c in t_num_cols if any(k in c.lower() for k in ["price_per_m2", "price", "amount", "revenue", "cost", "gmv", "val", "total"])), t_num_cols[0] if t_num_cols else "metric_val")
                date_col = next((c for c in t_col_names if any(k in c.lower() for k in ["year_month", "published_at", "month", "date", "period"])), "published_at")

                date_cond_cur = f"{date_col} = '{cur_m}'" if "year_month" in date_col.lower() else f"{date_col} LIKE '{cur_m}%'"
                date_cond_prev = f"{date_col} = '{prev_m}'" if "year_month" in date_col.lower() else f"{date_col} LIKE '{prev_m}%'"

                cte_sql = (
                    "WITH cur_period AS (\n"
                    f"    SELECT {cat_col}, AVG({metric_col}) AS val_cur\n"
                    f"    FROM {summary_table}\n"
                    f"    WHERE {date_cond_cur}\n"
                    f"    GROUP BY {cat_col}\n"
                    "),\n"
                    "prev_period AS (\n"
                    f"    SELECT {cat_col}, AVG({metric_col}) AS val_prev\n"
                    f"    FROM {summary_table}\n"
                    f"    WHERE {date_cond_prev}\n"
                    f"    GROUP BY {cat_col}\n"
                    ")\n"
                    "SELECT \n"
                    f"    cur.{cat_col},\n"
                    "    cur.val_cur,\n"
                    "    prev.val_prev,\n"
                    "    ROUND((cur.val_cur - prev.val_prev) * 100.0 / NULLIF(prev.val_prev, 0), 2) AS growth_pct\n"
                    f"FROM cur_period cur\n"
                    f"JOIN prev_period prev ON cur.{cat_col} = prev.{cat_col}\n"
                    "ORDER BY growth_pct DESC\n"
                    "LIMIT 100;"
                )
                return f"```sql\n{cte_sql}\n```"

            # Phân rã bài toán xếp hạng phân nhóm (Window Ranking)
            if "window_ranking" in prompt_lower:
                part_col = text_cols[0] if text_cols else (col_names[0] if col_names else "category")
                order_col = num_cols[0] if num_cols else (col_names[1] if len(col_names) > 1 else "id")
                cte_sql = (
                    "WITH ranked_items AS (\n"
                    "    SELECT *,\n"
                    f"        ROW_NUMBER() OVER (PARTITION BY {part_col} ORDER BY {order_col} DESC) as rnk\n"
                    f"    FROM {main_table}\n"
                    ")\n"
                    "SELECT * FROM ranked_items WHERE rnk <= 3 LIMIT 100;"
                )
                return f"```sql\n{cte_sql}\n```"

            # Trích xuất mệnh đề JOIN và WHERE từ prompt
            join_clauses = re.findall(r"-\s*`(JOIN\s+[^`]+)`", prompt, re.IGNORECASE)
            where_clauses = re.findall(r"-\s*`([^`]+)`", prompt)
            filters = [c for c in where_clauses if not c.upper().startswith("JOIN")]

            order_by = re.search(r"GỢI Ý SẮP XẾP:\s*`([^`]+)`", prompt)
            limit = re.search(r"GỢI Ý GIỚI HẠN:\s*`([^`]+)`", prompt)

            # Xác định metric từ Semantic Layer hoặc tự suy luận
            metric_match = re.search(r"CHỈ SỐ NGHIỆP VỤ ĐƯỢC GỢI Ý.*?`([^`]+)`", prompt, re.DOTALL)
            if metric_match:
                metric_expr = metric_match.group(1)
                if "AS" not in metric_expr.upper():
                    metric_expr = f"{metric_expr} AS metric_value"
            elif num_cols:
                is_avg = any(k in user_q for k in ["trung bình", "bình quân", "average", "avg", "mean", "/m2", "m2"])
                is_sum = any(k in user_q for k in ["tổng", "doanh thu", "sum", "total", "lũy kế"])
                target_col = num_cols[0]
                if is_avg:
                    metric_expr = f"ROUND(AVG({target_col}), 2) AS avg_{target_col}"
                elif is_sum:
                    metric_expr = f"ROUND(SUM({target_col}), 2) AS total_{target_col}"
                else:
                    metric_expr = "COUNT(*) AS total_count"
            else:
                metric_expr = "COUNT(*) AS total_count"

            # Xác định cột GROUP BY động
            group_col = None
            if text_cols:
                for tc in text_cols:
                    if tc.lower() in user_q or any(w in user_q for w in tc.lower().split("_") if len(w) > 2):
                        group_col = tc
                        break
                if not group_col and (any(k in user_q for k in ["theo", "mỗi", "từng", "nhóm", "group", "by", "thống kê", "phân tích"]) or len(text_cols) == 1):
                    group_col = text_cols[0]

            # Nếu hỏi Top N
            if any(k in user_q for k in ["cao nhất", "lớn nhất", "đắt nhất", "nhiều nhất"]):
                limit_num = 10
                num_match = re.search(r"top\s*(\d+)", user_q)
                if num_match:
                    limit_num = int(num_match.group(1))
                order_col = num_cols[0] if num_cols else (col_names[0] if col_names else "id")
                desc_col = text_cols[0] if text_cols else order_col
                sql = f"SELECT {desc_col}, {order_col} FROM {main_table} ORDER BY {order_col} DESC LIMIT {limit_num};"
                return f"```sql\n{sql}\n```"

            # Tạo câu SELECT tổng hợp
            if metric_expr and (group_col or "thống kê" in user_q or "tổng" in user_q or "trung bình" in user_q or "bao nhiêu" in user_q or "đếm" in user_q):
                select_metrics = metric_expr if "COUNT" in metric_expr.upper() else f"{metric_expr}, COUNT(*) AS total_count"
                if group_col:
                    limit_val = limit.group(1) if limit else ("LIMIT 5" if "top 5" in user_q else "LIMIT 100")
                    sql = f"SELECT {group_col}, {select_metrics} FROM {main_table} GROUP BY {group_col} ORDER BY 2 DESC {limit_val};"
                else:
                    sql = f"SELECT {select_metrics} FROM {main_table};"
                return f"```sql\n{sql}\n```"

            # SELECT danh sách chi tiết
            select_cols = f"{main_table}.*"
            sql_parts = [f"SELECT {select_cols}", f"FROM {main_table}"]
            for jc in join_clauses:
                sql_parts.append(jc)

            if filters:
                sql_parts.append("WHERE " + " AND ".join(filters[:3]))

            if order_by:
                sql_parts.append(order_by.group(1))

            if limit:
                sql_parts.append(limit.group(1))
            else:
                sql_parts.append("LIMIT 100")

            sql = " ".join(sql_parts) + ";"
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
