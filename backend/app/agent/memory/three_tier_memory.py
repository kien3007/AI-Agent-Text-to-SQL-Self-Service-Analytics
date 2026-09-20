"""
3-Tier Memory Architecture for Text-to-SQL Agent:
1. Short-Term Memory: Lưu tối đa 3 lỗi gần nhất theo 3 ngăn (DATA, SEMANTIC, GRAMMAR) để định tuyến cho LLM tự sửa.
2. Temporary Memory: Chấm điểm trạng thái theo phương trình Bellman v(St) = R_{t+1} + γ * v(S_{t+1}) để cắt tỉa nhánh lặp bế tắc.
3. Long-Term Memory: Lưu trữ tri thức Good Plans / Bad Plans / Common Knowledge chia sẻ giữa các phiên.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ShortTermErrorRecord(BaseModel):
    category: str = Field(..., description="Ngăn phân loại lỗi: 'GRAMMAR', 'SEMANTIC', 'DATA'")
    raw_error: str = Field(..., description="Thông báo lỗi gốc")
    vn_advice: str = Field(..., description="Chỉ dẫn tiếng Việt")
    sql_attempted: str = Field(..., description="Câu lệnh SQL gặp lỗi")


class ShortTermMemory:
    """Quản lý các lỗi phát sinh trong phiên hiện tại."""

    def __init__(self, max_errors: int = 3):
        self.max_errors = max_errors
        self.grammar_errors: List[ShortTermErrorRecord] = []
        self.semantic_errors: List[ShortTermErrorRecord] = []
        self.data_errors: List[ShortTermErrorRecord] = []

    def record_error(self, raw_error: str, vn_advice: str, sql: str) -> ShortTermErrorRecord:
        """Phân loại và lưu trữ lỗi vào ngăn tương ứng."""
        err_lower = raw_error.lower()
        if "syntax" in err_lower or "unknown column" in err_lower or "cartesian" in err_lower or "table" in err_lower:
            category = "GRAMMAR"
            target_list = self.grammar_errors
        elif "fan-trap" in err_lower or "order by" in err_lower or "logic" in err_lower:
            category = "SEMANTIC"
            target_list = self.semantic_errors
        else:
            category = "DATA"
            target_list = self.data_errors

        record = ShortTermErrorRecord(
            category=category,
            raw_error=raw_error,
            vn_advice=vn_advice,
            sql_attempted=sql
        )
        target_list.append(record)
        if len(target_list) > self.max_errors:
            target_list.pop(0)
        return record

    def get_feedback_prompt(self) -> str:
        """Tạo đoạn prompt hướng dẫn ngắn gọn cho LLM sửa đổi."""
        all_errors = self.grammar_errors + self.semantic_errors + self.data_errors
        if not all_errors:
            return ""

        latest = all_errors[-1]
        lines = [
            "\n### LỊCH SỬ SỬA LỖI (SHORT-TERM MEMORY FEEDBACK):",
            f"- Ngăn lỗi: [{latest.category}]",
            f"- Chi tiết lỗi: {latest.raw_error}",
            f"- Hướng dẫn sửa: {latest.vn_advice}",
            f"- Câu lệnh bị lỗi trước đó: `{latest.sql_attempted}`",
            "YÊU CẦU: Hãy phân tích lỗi trên và sinh lại câu SQL đã sửa chữa triệt để, không lặp lại sai sót."
        ]
        return "\n".join(lines)


class TemporaryMemory:
    """
    Quản lý đánh giá kế hoạch theo phương trình Bellman:
    v(S_t) = R_{t+1} + gamma * v(S_{t+1})
    """

    def __init__(self, gamma: float = 0.9):
        self.gamma = gamma
        self.step_history: List[Dict[str, Any]] = []

    def add_step(self, step_name: str, state_summary: Dict[str, Any], reward: float) -> None:
        """Thêm một bước thực thi kèm điểm thưởng reward."""
        self.step_history.append({
            "step": step_name,
            "summary": state_summary,
            "reward": reward,
            "bellman_value": 0.0
        })
        self._recompute_bellman_values()

    def _recompute_bellman_values(self) -> None:
        """Tính toán lại giá trị Bellman từ bước cuối cùng ngược về trước."""
        accumulated = 0.0
        for item in reversed(self.step_history):
            accumulated = item["reward"] + self.gamma * accumulated
            item["bellman_value"] = accumulated

    def is_stuck_in_loop(self, max_consecutive_negative: int = 3) -> bool:
        """Phát hiện nếu agent đang bị bế tắc lặp lại với điểm thưởng âm liên tiếp."""
        if len(self.step_history) < max_consecutive_negative:
            return False
        recent = self.step_history[-max_consecutive_negative:]
        return all(item["reward"] < 0 for item in recent)

    def get_latest_value(self) -> float:
        """Lấy điểm Bellman hiện tại."""
        return self.step_history[-1]["bellman_value"] if self.step_history else 0.0


class LongTermMemory:
    """
    Lưu trữ tri thức dài hạn chia sẻ giữa các phiên hội thoại (kế thừa DAIL-SQL pattern).
    Hỗ trợ:
    - Nạp sẵn (Seed) các mẫu SQL chuẩn dựa trên dbt Data Marts và multi-table joins.
    - Tìm kiếm Top-K ví dụ mẫu tương đồng nhất (Dynamic Few-Shot) theo domain và nội dung câu hỏi.
    - Tự động học (Auto-learning): Ghi nhận các câu truy vấn thành công vào tập Good Plans.
    """

    def __init__(self, seed_defaults: bool = True):
        self.good_plans: List[Dict[str, Any]] = []
        self.bad_plans: List[Dict[str, Any]] = []
        self.common_knowledge: List[Dict[str, Any]] = []
        if seed_defaults:
            self._seed_initial_plans()

    def _seed_initial_plans(self) -> None:
        """Nạp các mẫu SQL chuẩn tối ưu từ dbt Data Marts và Steiner Tree Joins."""
        seed_data = [
            # Real Estate: dbt Aggregated Monthly Summary Mart
            {
                "query": "Thống kê xu hướng giá chung cư tại Cầu Giấy qua các tháng",
                "domain_id": "real_estate",
                "sql": "SELECT published_year_month, avg_price_per_sqm, total_listings FROM fct_district_monthly_summary WHERE district_name = 'Cầu Giấy' AND property_type_name = 'Căn hộ chung cư' ORDER BY published_year_month ASC LIMIT 12;",
                "tables_used": ["fct_district_monthly_summary"],
                "description": "Truy vấn bảng dbt Marts tổng hợp theo tháng và quận huyện"
            },
            # Real Estate: dbt Curated Analytics Mart
            {
                "query": "Tìm các căn chung cư cao cấp trên 10 tỷ tại Hà Nội",
                "domain_id": "real_estate",
                "sql": "SELECT listing_title, project_name, district_name, price_vnd, area_sqm, price_segment FROM fct_real_estate_analytics WHERE province_name = 'Hà Nội' AND price_segment = 'Siêu cao cấp (> 15 tỷ)' ORDER BY price_vnd DESC LIMIT 10;",
                "tables_used": ["fct_real_estate_analytics"],
                "description": "Truy vấn bảng dbt Fact chi tiết kèm phân khúc giá"
            },
            # Real Estate: Raw Listings filter
            {
                "query": "Tìm nhà riêng diện tích trên 80m2 tại Quận 1",
                "domain_id": "real_estate",
                "sql": "SELECT name, price, area, street_name FROM real_estate_listings WHERE district_name = 'Quận 1' AND property_type_name = 'Nhà' AND area >= 80 ORDER BY price ASC LIMIT 20;",
                "tables_used": ["real_estate_listings"],
                "description": "Lọc nhà riêng theo diện tích và quận trên bảng thô"
            },
            # E-commerce: Multi-table JOIN (Steiner Tree)
            {
                "query": "Thống kê tổng doanh thu GMV và số lượng đơn hàng theo khách hàng",
                "domain_id": "ecommerce",
                "sql": "SELECT c.customer_name, COUNT(o.id) AS total_orders, SUM(o.total_amount) AS gmv FROM customers c LEFT JOIN orders o ON c.id = o.customer_id GROUP BY c.customer_name ORDER BY gmv DESC LIMIT 10;",
                "tables_used": ["customers", "orders"],
                "description": "Multi-table JOIN tính GMV khách hàng"
            },
            # Healthcare: Multi-table JOIN
            {
                "query": "Thống kê số lượng bệnh nhân theo từng loại chẩn đoán",
                "domain_id": "healthcare",
                "sql": "SELECT d.diagnosis_code, d.description, COUNT(DISTINCT e.patient_id) AS total_patients FROM diagnoses d JOIN encounters e ON d.encounter_id = e.id GROUP BY d.diagnosis_code, d.description ORDER BY total_patients DESC LIMIT 10;",
                "tables_used": ["diagnoses", "encounters"],
                "description": "Multi-table JOIN thống kê bệnh nhân theo chẩn đoán"
            }
        ]
        for item in seed_data:
            self.save_plan(
                user_query=item["query"],
                domain_id=item["domain_id"],
                sql=item["sql"],
                is_successful=True,
                tables_used=item.get("tables_used"),
                metadata={"description": item.get("description", "")}
            )

    def save_plan(
        self,
        user_query: str,
        domain_id: str,
        sql: str,
        is_successful: bool,
        tables_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        record = {
            "query": user_query,
            "domain_id": domain_id,
            "sql": sql,
            "tables_used": tables_used or [],
            "metadata": metadata or {}
        }
        if is_successful:
            if not any(p["query"] == user_query and p["sql"] == sql for p in self.good_plans):
                self.good_plans.append(record)
        else:
            self.bad_plans.append(record)

    def get_relevant_few_shots(
        self,
        query: str,
        domain_id: str,
        top_k: int = 2,
        target_tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm Top-K ví dụ mẫu tương đồng nhất (Dynamic Few-Shot Retrieval theo DAIL-SQL).
        Kết hợp độ tương đồng từ khóa câu hỏi và tập bảng liên quan.
        """
        candidates = [p for p in self.good_plans if p["domain_id"] == domain_id]
        if not candidates:
            return []

        query_tokens = set(query.lower().split())
        target_tables_set = set(t.lower() for t in (target_tables or []))

        scored_candidates = []
        for cand in candidates:
            score = 0.0
            cand_tokens = set(cand["query"].lower().split())
            overlap = len(query_tokens & cand_tokens)
            union = len(query_tokens | cand_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            score += jaccard * 5.0

            cand_tables = set(t.lower() for t in cand.get("tables_used", []))
            if target_tables_set and cand_tables:
                table_overlap = len(target_tables_set & cand_tables)
                score += table_overlap * 2.0

            scored_candidates.append((score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_candidates[:top_k]]


class ThreeTierMemory:
    """Bộ điều phối thống nhất toàn bộ 3 tầng bộ nhớ."""

    def __init__(self):
        self.short_term = ShortTermMemory()
        self.temporary = TemporaryMemory()
        self.long_term = LongTermMemory()
