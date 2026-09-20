"""
Validator Node (Node 4).
Kiểm định an toàn và tính hợp lệ của SQL qua PlanValidator (5 tầng guardrail).
Quản lý bộ đếm thử lại và định tuyến vòng lặp Self-Correction.
"""

from typing import Optional
from app.agent.state import AgentState
from app.agent.nodes.plan_validator import PlanValidator, ValidationResult
from app.agent.memory.three_tier_memory import ThreeTierMemory


class ValidatorNode:
    """Node thực thi kiểm định kế hoạch truy vấn và điều phối sửa lỗi."""

    def __init__(
        self,
        plan_validator: Optional[PlanValidator] = None,
        memory: Optional[ThreeTierMemory] = None,
        use_explain: bool = False
    ):
        self.plan_validator = plan_validator or PlanValidator()
        self.memory = memory or ThreeTierMemory()
        self.use_explain = use_explain

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("plan_validator")
        
        sql = state.sql_query or ""
        val_result = self.plan_validator.validate(
            sql=sql,
            schema_context=state.schema_context,
            use_explain=self.use_explain
        )
        state.validation_result = val_result

        if not val_result.is_valid:
            # Ghi nhận lỗi vào bộ nhớ ngắn hạn
            raw_err = "; ".join(val_result.errors)
            vn_adv = "; ".join(val_result.vn_suggestions) or "Hãy kiểm tra lại danh sách cột và bảng."
            
            error_record = {
                "raw_error": raw_err,
                "vn_advice": vn_adv,
                "sql": sql,
                "retry_count": state.retry_count + 1
            }
            state.error_history.append(error_record)
            self.memory.short_term.record_error(raw_err, vn_adv, sql)
            self.memory.temporary.add_step("plan_validator_failed", error_record, reward=-0.5)

            state.retry_count += 1
            if state.retry_count >= state.max_retries:
                state.final_response = (
                    f"Rất tiếc, hệ thống đã thử sửa câu lệnh {state.max_retries} lần nhưng vẫn gặp lỗi cú pháp / an toàn: {raw_err}. "
                    f"Chỉ dẫn: {vn_adv}"
                )
        else:
            state.requires_hitl = val_result.requires_hitl
            self.memory.temporary.add_step(
                "plan_validator_success",
                {"sql": sql, "warnings": val_result.warnings},
                reward=1.0 if not val_result.warnings else 0.5
            )

        return state
