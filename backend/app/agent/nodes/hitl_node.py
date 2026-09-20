"""
Human-In-The-Loop (HITL) Gate Node (Node 5).
Quản lý điểm ngắt (Interrupt) phê duyệt trước khi chạy các truy vấn nặng hoặc rủi ro cao.
"""

from typing import Optional
from app.agent.state import AgentState


class HITLNode:
    """Node cổng kiểm duyệt con người trước khi thực thi truy vấn lớn."""

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("hitl_gate")

        if not state.requires_hitl:
            return state

        # Nếu cần duyệt nhưng chưa có quyết định (hitl_approved is None)
        if state.hitl_approved is None:
            vr = state.validation_result
            tablets = vr.tablets_scanned if vr else 0
            rows = vr.cardinality_estimate if vr else 0
            state.final_response = (
                f"[HITL_AWAITING_APPROVAL] Truy vấn cần được người dùng phê duyệt trước khi thực thi "
                f"do ước tính quét dung lượng lớn ({tablets} tablets, ~{rows:,} dòng dữ liệu). "
                f"Câu SQL chờ duyệt: `{state.sql_query}`"
            )
            return state

        # Nếu người dùng từ chối
        if state.hitl_approved is False:
            state.final_response = (
                "Người dùng đã từ chối phê duyệt thực thi câu lệnh SQL này (HITL Rejected). Quá trình kết thúc."
            )
            return state

        # Nếu người dùng chấp thuận (hitl_approved is True)
        return state
