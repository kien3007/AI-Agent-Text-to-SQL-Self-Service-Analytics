"""
SQL Generator Node (Node 3 - Model 2: Qwen 2.5-Coder).
Sinh câu lệnh truy vấn SQL chuẩn cú pháp MySQL / Apache Doris
từ Schema Context, Steiner Tree JOIN paths và phản hồi sửa lỗi từ Short-Term Memory.
"""

import re
from typing import Optional
from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.memory.three_tier_memory import ShortTermMemory, LongTermMemory, ThreeTierMemory


class SQLGeneratorNode:
    """Node sinh câu truy vấn SQL đảm bảo an toàn và tối ưu."""

    SYSTEM_PROMPT = """Bạn là Chuyên gia Kỹ thuật Dữ liệu cấp cao (Data Engineer & Text-to-SQL Expert) chuyên về Apache Doris và MySQL.
Nhiệm vụ của bạn là chuyển đổi câu hỏi tự nhiên của người dùng thành câu truy vấn SQL chuẩn xác, an toàn và tối ưu hiệu năng.

NGUYÊN TẮC BẮT BUỘC:
1. CHỈ sinh câu lệnh đọc dữ liệu (SELECT hoặc WITH ... SELECT). Tuyệt đối KHÔNG sinh bất kỳ lệnh DDL/DML nào (DROP, DELETE, UPDATE, INSERT, ALTER...).
2. Chỉ sử dụng các Bảng và Cột được cung cấp trong phần SCHEMA LIÊN KẾT. Không tự bịa thêm tên cột hoặc tên bảng.
3. Khi truy vấn đa bảng, BẮT BUỘC tuân thủ các mệnh đề JOIN ... ON ... được gợi ý từ giải thuật Steiner Tree. Tuyệt đối KHÔNG viết CROSS JOIN hoặc liệt kê nhiều bảng sau FROM bằng dấu phẩy.
4. Tránh chia cho 0: Luôn dùng NULLIF(ten_cot, 0) khi thực hiện phép chia.
5. Luôn thêm mệnh đề LIMIT hợp lý (mặc định LIMIT 100 nếu người dùng không yêu cầu số lượng cụ thể).
6. Định dạng đầu ra: Chỉ trả về duy nhất khối mã SQL trong thẻ ```sql ... ```, không giải thích dài dòng."""

    def __init__(
        self,
        llm: Optional[DualModelLLM] = None,
        memory: Optional[ThreeTierMemory] = None,
        long_term_memory: Optional[LongTermMemory] = None
    ):
        self.llm = llm or DualModelLLM()
        if memory:
            self.long_term_memory = memory.long_term
        elif long_term_memory:
            self.long_term_memory = long_term_memory
        else:
            self.long_term_memory = LongTermMemory()

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("sql_generator")
        
        prompt_parts = [
            f"CÂU HỎI NGƯỜI DÙNG: \"{state.user_query}\"",
            f"DOMAIN HIỆN TẠI: {state.domain_id or 'real_estate'}"
        ]

        if state.schema_context:
            prompt_parts.append("\n" + state.schema_context.prompt_context)

        # Dynamic Few-Shot In-Context Learning (kế thừa DAIL-SQL)
        if self.long_term_memory:
            target_tables = state.schema_context.selected_tables if state.schema_context else []
            few_shots = self.long_term_memory.get_relevant_few_shots(
                query=state.user_query,
                domain_id=state.domain_id or "real_estate",
                top_k=2,
                target_tables=target_tables
            )
            if few_shots:
                fs_lines = ["\n### CÁC VÍ DỤ TRUY VẤN MẪU THAM KHẢO (DYNAMIC FEW-SHOT TỪ LONG-TERM MEMORY):"]
                for idx, fs in enumerate(few_shots, 1):
                    fs_lines.append(f"Ví dụ {idx}:")
                    fs_lines.append(f"- Câu hỏi: \"{fs['query']}\"")
                    fs_lines.append(f"- SQL chuẩn:\n```sql\n{fs['sql']}\n```")
                prompt_parts.append("\n".join(fs_lines))

        # Phân rã bài toán con & CTEs cho câu hỏi Mức 3 (kế thừa DIN-SQL)
        if state.complexity_level == "COMPLEX" and state.decomposition_plan:
            plan = state.decomposition_plan
            decomp_lines = [
                "\n### KẾ HOẠCH PHÂN RÃ BÀI TOÁN CON (DECOMPOSITION PLAN - DIN-SQL):",
                f"- Dạng câu hỏi phức tạp: {plan.get('type', 'COMPLEX')}",
                f"- CTEs đề xuất: {', '.join(plan.get('cte_names', []))}",
                "- Các bước thực thi logic:"
            ]
            for step in plan.get("sub_tasks", []):
                decomp_lines.append(f"  * {step}")
            decomp_lines.append("YÊU CẦU: Sử dụng cấu trúc `WITH ... AS (...)` tương ứng các bước trên để viết câu truy vấn rõ ràng, chuẩn xác.")
            prompt_parts.append("\n".join(decomp_lines))

        # Nếu có lịch sử lỗi từ các lần thử trước (Self-Correction feedback)
        if state.error_history:
            latest_err = state.error_history[-1]
            feedback_block = [
                "\n### CẢNH BÁO LỖI TỪ LẦN CHẠY TRƯỚC (YÊU CẦU SỬA ĐỔI):",
                f"- Lỗi gặp phải: {latest_err.get('raw_error', '')}",
                f"- Chỉ dẫn sửa: {latest_err.get('vn_advice', '')}",
                f"- Câu SQL bị lỗi: `{latest_err.get('sql', '')}`",
                "HÃY PHÂN TÍCH KỸ VÀ SINH LẠI CÂU LỆNH SQL ĐÃ KHẮC PHỤC TRIỆT ĐỂ LỖI TRÊN."
            ]
            prompt_parts.append("\n".join(feedback_block))

        prompt_parts.append("\nHÃY SINH CÂU TRUY VẤN SQL CHUẨN XÁC TRONG KHỐI MÃ ```sql ... ```:")
        user_prompt = "\n".join(prompt_parts)

        raw_output = self.llm.generate(
            prompt=user_prompt,
            system_prompt=self.SYSTEM_PROMPT,
            role="coder",
            temperature=0.0
        )

        extracted_sql = self._extract_clean_sql(raw_output)
        state.sql_query = extracted_sql
        return state

    def _extract_clean_sql(self, text: str) -> str:
        """Bóc tách chuỗi SQL sạch sẽ từ markdown code block hoặc chuỗi văn bản."""
        # Thử trích xuất từ ```sql ... ```
        block_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if block_match:
            candidate = block_match.group(1).strip()
        else:
            # Tìm từ khóa SELECT hoặc WITH đầu tiên
            select_match = re.search(r"\b(SELECT|WITH)\b.*?(?:;|$)", text, re.DOTALL | re.IGNORECASE)
            if select_match:
                candidate = select_match.group(0).strip()
            else:
                candidate = text.strip()

        # Dọn dẹp khoảng trắng thừa và dấu chấm phẩy cuối cùng
        return candidate.strip().rstrip(";")
