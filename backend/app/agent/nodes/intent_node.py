"""
Intent & Clarification Node (Node 0 & 1).
Phân tích ý định người dùng, chuẩn hóa thực thể và kích hoạt vòng lặp hỏi lại (Clarification Loop).
"""

import re
from typing import Optional
from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.core.domain_manager import DomainManager
from app.core.normalizer import GenericVietnameseNormalizer
from app.core.glossary import VietnameseBusinessGlossary
from app.schemas.validation import ValidationResult
from app.agent.tools.definitions import CLARIFICATION_TOOL


class IntentClarifierNode:
    """Node phân loại ý định, chuẩn hóa ngôn ngữ tự nhiên và phát hiện câu hỏi mơ hồ."""

    def __init__(
        self,
        domain_manager: Optional[DomainManager] = None,
        llm: Optional[DualModelLLM] = None
    ):
        self.domain_manager = domain_manager or DomainManager()
        self.normalizer = GenericVietnameseNormalizer()
        self.glossary = VietnameseBusinessGlossary(domain_manager=self.domain_manager)
        self.llm = llm or DualModelLLM()

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("intent_clarifier")
        raw_query = state.user_query.strip()
        
        # Inject conversation history if available
        if state.conversation_history:
            last_turns = state.conversation_history[-6:]
            history_ctx = "\n".join(
                f"[{h['role'].upper()}]: {h['content']}" for h in last_turns
            )
            raw_query = (
                f"[Ngữ cảnh hội thoại trước đó:]\n{history_ctx}\n\n"
                f"[Câu hỏi mới của người dùng]: {raw_query}"
            )
        # 0. Kiểm tra an toàn bảo mật ngay từ câu hỏi thô (Pre-Execution Guardrail)
        malicious_patterns = [
            r"\bDROP\s+TABLE\b", r"\bDELETE\s+FROM\b", r"\bTRUNCATE\s+TABLE\b",
            r"\bALTER\s+TABLE\b", r"\bUPDATE\s+\w+\s+SET\b", r"\bINSERT\s+INTO\b"
        ]
        if any(re.search(pat, raw_query, re.IGNORECASE) for pat in malicious_patterns):
            state.validation_result = ValidationResult(
                is_valid=False,
                risk_level="BLOCKED",
                errors=["Cảnh báo bảo mật: Phát hiện câu lệnh thay đổi cấu trúc hoặc xóa dữ liệu (DDL/DML vi phạm chính sách an toàn)."]
            )
            state.final_response = "Truy vấn bị từ chối: Hệ thống chỉ hỗ trợ phân tích dữ liệu đọc (Read-only SELECT). Các câu lệnh xóa hoặc thay đổi dữ liệu bị nghiêm cấm."
            return state

        # 1. Định tuyến Domain nếu chưa được chỉ định
        if not state.domain_id:
            detected = self.domain_manager.detect_domain(raw_query)
            state.domain_id = detected.domain_id if hasattr(detected, "domain_id") else str(detected)

        # 2. Chuẩn hóa chung (Thời gian, tiền tệ, định lượng, limit)
        time_range = self.normalizer.extract_relative_time(raw_query)
        currency_range = self.normalizer.extract_currency_range(raw_query)
        limit_info = self.normalizer.extract_limit(raw_query)

        entities = {}
        if time_range:
            entities["time_range"] = time_range
        if currency_range[0] is not None or currency_range[1] is not None:
            entities["price_range"] = {
                "min": currency_range[0],
                "max": currency_range[1],
                "sql_filter": currency_range[3]
            }
        if limit_info:
            entities["limit"] = limit_info[0]

        # 3. Chuẩn hóa sâu theo Glossary (nếu là Real Estate)
        if state.domain_id == "real_estate":
            glossary_res = self.glossary.normalize(raw_query)
            state.normalized_query = glossary_res.normalized_query
            intent = glossary_res.intent
            if intent.property_type:
                entities["property_type"] = intent.property_type
            if intent.province:
                entities["province"] = intent.province
            if intent.district:
                entities["district"] = intent.district
            if intent.bedroom_count is not None:
                entities["bedroom_count"] = intent.bedroom_count
            if intent.direction:
                entities["direction"] = intent.direction
        else:
            state.normalized_query = raw_query

        state.extracted_entities = entities

        # 4. Kiểm tra mơ hồ (Ambiguity & Clarification Loop)
        # Nếu câu hỏi quá ngắn (< 3 từ) hoặc chỉ chứa từ khóa chung chung không có thực thể/bộ lọc nào
        is_too_vague = self._check_ambiguity(raw_query, entities)
        if is_too_vague:
            state.clarification_needed = True
            prompt = (
                f"Người dùng vừa hỏi một câu rất mơ hồ: '{raw_query}'. "
                f"Domain đang xét là: '{state.domain_id}'. "
                "Hãy đặt một câu hỏi làm rõ (clarification question) ngắn gọn, lịch sự bằng tiếng Việt "
                "để hỏi người dùng cung cấp thêm tiêu chí cần phân tích (khu vực, loại hình, khoảng giá hoặc mốc thời gian)."
            )
            tool_result = self.llm.call_with_tools(
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia phân tích dữ liệu và tư vấn nghiệp vụ cấp cao."},
                    {"role": "user", "content": prompt}
                ],
                tools=[CLARIFICATION_TOOL],
                tool_choice={"type": "function", "function": {"name": "ask_clarification"}},
                role="reasoner",
                temperature=0.3
            )
            clarify_q = ""
            if tool_result.get("tool_calls"):
                args = tool_result["tool_calls"][0].get("arguments", {})
                clarify_q = args.get("question", "")
            if not clarify_q:
                clarify_q = tool_result.get("content") or "Dạ em nhận thấy yêu cầu của anh/chị cần thêm thông tin chi tiết để kết quả phân tích chính xác nhất."

            state.clarification_question = clarify_q
            state.final_response = state.clarification_question
            return state

        state.clarification_needed = False
        state.clarification_question = None

        # 5. Phân loại độ phức tạp & Phân rã bài toán con (kế thừa DIN-SQL)
        complexity = self._classify_complexity(raw_query)
        state.complexity_level = complexity

        if complexity == "COMPLEX":
            state.decomposition_plan = self._create_decomposition_plan(raw_query, state.domain_id)

        return state

    def _classify_complexity(self, query: str) -> str:
        """Phân loại độ phức tạp câu hỏi (kế thừa DIN-SQL: EASY, MEDIUM, COMPLEX)."""
        q_lower = query.lower()

        # Dấu hiệu câu hỏi Mức 3 (COMPLEX): So sánh chu kỳ YoY/MoM hoặc Xếp hạng phân nhóm Window Function
        period_comparison_keywords = [
            "so sánh", "tăng trưởng", "biến động", "so với", "yoy", "mom",
            "chênh lệch", "thay đổi"
        ]
        window_ranking_keywords = [
            "xếp hạng", "top đầu", "cao nhất từng", "thấp nhất từng",
            "đắt nhất từng", "rẻ nhất từng", "nhiều nhất từng", "ít nhất từng"
        ]
        
        has_window_ranking = any(kw in q_lower for kw in window_ranking_keywords) or (
            "top " in q_lower and any(group_kw in q_lower for group_kw in ["từng", "mỗi"])
        )

        if any(kw in q_lower for kw in period_comparison_keywords) or has_window_ranking:
            return "COMPLEX"

        # Dấu hiệu câu hỏi Mức 2 (MEDIUM): Gom nhóm GROUP BY, nhiều điều kiện kết hợp
        medium_keywords = [
            "theo từng", "mỗi", "theo", "thống kê", "trung bình", "tổng",
            "đếm", "và", "kèm", "cùng với", "chi tiết"
        ]
        if any(kw in q_lower for kw in medium_keywords):
            return "MEDIUM"

        # Mặc định: Câu hỏi Mức 1 (EASY) - Filter đơn giản
        return "EASY"

    def _create_decomposition_plan(self, query: str, domain_id: Optional[str]) -> dict:
        """Phân rã câu hỏi Mức 3 thành các bài toán con (CTEs) logic."""
        q_lower = query.lower()

        # Dạng 1: So sánh chu kỳ thời gian / Tăng trưởng (YoY / MoM / Period Comparison)
        period_comparison_keywords = [
            "so sánh", "tăng trưởng", "biến động", "so với", "yoy", "mom",
            "chênh lệch", "thay đổi"
        ]
        if any(kw in q_lower for kw in period_comparison_keywords):
            return {
                "type": "PERIOD_COMPARISON",
                "cte_names": ["cur_period", "prev_period"],
                "target_metric": "growth_pct",
                "sub_tasks": [
                    "Bước 1 (CTE cur_period): Lấy dữ liệu và tính toán chỉ số cho kỳ hiện tại.",
                    "Bước 2 (CTE prev_period): Lấy dữ liệu và tính toán chỉ số cho kỳ trước để đối chiếu.",
                    "Bước 3 (Main Query): Nối cur_period và prev_period qua chiều danh mục (JOIN ... ON ...), tính tỷ lệ tăng trưởng: ROUND((cur.val - prev.val) * 100.0 / NULLIF(prev.val, 0), 2) AS growth_pct."
                ]
            }

        # Dạng 2: Xếp hạng phân nhóm Window Function (ROW_NUMBER OVER PARTITION BY)
        return {
            "type": "WINDOW_RANKING",
            "cte_names": ["ranked_items"],
            "sub_tasks": [
                "Bước 1 (CTE ranked_items): Sử dụng hàm ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC) để đánh số thứ tự trong từng nhóm.",
                "Bước 2 (Main Query): Lọc WHERE rank <= K để lấy các bản ghi dẫn đầu của từng nhóm."
            ]
        }

    def _check_ambiguity(self, query: str, entities: dict) -> bool:
        """Phát hiện nếu câu hỏi quá mơ hồ, thiếu thông tin."""
        words = query.strip().split()
        if len(words) <= 2:
            return True

        vague_phrases = [
            "xem giá", "tính tiền", "thống kê", "tìm kiếm", "cho tôi xem",
            "dữ liệu", "báo cáo", "phân tích", "chi tiết", "thị trường thế nào",
            "thị trường", "tình hình", "xem dữ liệu", "báo cáo chi tiết",
            "thông tin", "xem số liệu"
        ]
        q_clean = query.lower().strip().rstrip("?").rstrip(".").strip()
        if any(q_clean == phrase or q_clean.startswith(phrase) for phrase in vague_phrases) and not entities:
            return True
        if q_clean.endswith("thế nào") or q_clean.endswith("sao") or q_clean.endswith("như thế nào"):
            if not entities:
                return True

        return False
