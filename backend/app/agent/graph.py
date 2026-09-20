"""
LangGraph Stateful Machine & Agent Orchestrator.
Điều phối toàn diện cỗ máy trạng thái đa tác tử:
Intent & Clarification -> Schema Linking (Steiner Tree) -> SQL Generator (Coder)
-> Plan Validator (5 Tầng Guardrail & Self-Correction) -> HITL Gate -> Executor -> Response Formatter.
"""

import time
import logging
from typing import Optional, Dict, Any, Generator, Tuple, Union

from app.agent.state import AgentState
from app.agent.llm_client import DualModelLLM
from app.agent.memory.three_tier_memory import ThreeTierMemory
from app.agent.nodes.intent_node import IntentClarifierNode
from app.agent.nodes.schema_linking_node import SchemaLinkingNode
from app.agent.nodes.sql_generator import SQLGeneratorNode
from app.agent.nodes.validator_node import ValidatorNode
from app.agent.nodes.hitl_node import HITLNode
from app.agent.nodes.executor_node import ExecutorNode
from app.agent.nodes.response_formatter import ResponseFormatterNode

logger = logging.getLogger("AgentOrchestrator")


class AgentOrchestrator:
    """
    Cỗ máy điều phối State Machine đa tác tử cho Text-to-SQL.
    Cung cấp đồng thời cơ chế invoke (đồng bộ) và stream (phục vụ SSE streaming logs).
    """

    def __init__(
        self,
        llm: Optional[DualModelLLM] = None,
        embedding_function: Optional[Any] = None,
        doris_client: Optional[Any] = None,
        use_explain: bool = False
    ):
        self.llm = llm or DualModelLLM()
        self.memory = ThreeTierMemory()
        self.use_explain = use_explain

        # Khởi tạo các Node tác tử
        self.intent_node = IntentClarifierNode(llm=self.llm)
        self.schema_node = SchemaLinkingNode(embedding_function=embedding_function)
        self.sql_node = SQLGeneratorNode(llm=self.llm, memory=self.memory)
        self.validator_node = ValidatorNode(memory=self.memory, use_explain=use_explain)
        self.hitl_node = HITLNode()
        self.executor_node = ExecutorNode(doris_client=doris_client)
        self.formatter_node = ResponseFormatterNode(llm=self.llm)

    def _prepare_state(self, input_val: Union[str, Dict[str, Any], AgentState], domain_id: Optional[str] = None) -> AgentState:
        """Chuẩn hóa dữ liệu đầu vào thành đối tượng AgentState."""
        if isinstance(input_val, AgentState):
            state = input_val
        elif isinstance(input_val, dict):
            state = AgentState(**input_val)
        else:
            state = AgentState(user_query=str(input_val), domain_id=domain_id)

        if domain_id and not state.domain_id:
            state.domain_id = domain_id
        return state

    def invoke(
        self,
        input_val: Union[str, Dict[str, Any], AgentState],
        domain_id: Optional[str] = None
    ) -> AgentState:
        """
        Thực thi toàn bộ đồ thị theo cơ chế đồng bộ (blocking) và trả về AgentState cuối cùng.
        """
        state = self._prepare_state(input_val, domain_id)
        start_time = time.time()

        # BƯỚC 1: Phân tích Ý định & Làm rõ (Intent & Clarification)
        state = self.intent_node(state)
        if state.clarification_needed:
            state.execution_time_ms = (time.time() - start_time) * 1000
            return state

        # BƯỚC 2: Schema Linking & Steiner Tree Join
        state = self.schema_node(state)

        # BƯỚC 3: Vòng lặp Sinh SQL & Tự sửa lỗi (Self-Correction Loop)
        while True:
            state = self.sql_node(state)
            state = self.validator_node(state)

            if state.validation_result and state.validation_result.is_valid:
                # SQL đã hợp lệ và an toàn
                break

            # Nếu không hợp lệ và chưa vượt quá số lần thử lại tối đa
            if state.retry_count < state.max_retries:
                logger.info(f"Self-correction loop triggered: Retry {state.retry_count}/{state.max_retries}")
                continue
            else:
                # Đã hết lượt thử lại -> Dừng lại và trả về lỗi
                state.execution_time_ms = (time.time() - start_time) * 1000
                return state

        # BƯỚC 4: Cổng kiểm duyệt Human-In-The-Loop (HITL Gate)
        state = self.hitl_node(state)
        if state.requires_hitl and state.hitl_approved is not True:
            # Tạm dừng đợi duyệt hoặc người dùng đã từ chối
            state.execution_time_ms = (time.time() - start_time) * 1000
            return state

        # BƯỚC 5: Thực thi trên Database / Doris DW
        state = self.executor_node(state)
        self._record_good_plan(state)

        # BƯỚC 6: Định dạng kết quả & Biểu đồ Recharts
        state = self.formatter_node(state)

        state.execution_time_ms = (time.time() - start_time) * 1000
        return state

    def stream(
        self,
        input_val: Union[str, Dict[str, Any], AgentState],
        domain_id: Optional[str] = None
    ) -> Generator[Tuple[str, AgentState], None, None]:
        """
        Thực thi đồ thị theo dạng streaming (phù hợp cho Server-Sent Events SSE).
        Phát ra từng cặp (tên_bước, trạng_thái_hiện_tại) sau mỗi node.
        """
        state = self._prepare_state(input_val, domain_id)
        start_time = time.time()

        # Bước 1
        state = self.intent_node(state)
        yield ("intent_clarifier", state)
        if state.clarification_needed:
            state.execution_time_ms = (time.time() - start_time) * 1000
            return

        # Bước 2
        state = self.schema_node(state)
        yield ("schema_linking", state)

        # Bước 3: Self-correction loop
        while True:
            state = self.sql_node(state)
            yield ("sql_generator", state)

            state = self.validator_node(state)
            yield ("plan_validator", state)

            if state.validation_result and state.validation_result.is_valid:
                break

            if state.retry_count < state.max_retries:
                yield ("self_correction_retry", state)
                continue
            else:
                state.execution_time_ms = (time.time() - start_time) * 1000
                return

        # Bước 4
        state = self.hitl_node(state)
        yield ("hitl_gate", state)
        if state.requires_hitl and state.hitl_approved is not True:
            state.execution_time_ms = (time.time() - start_time) * 1000
            return

        # Bước 5
        state = self.executor_node(state)
        self._record_good_plan(state)
        yield ("executor", state)

        # Bước 6
        state = self.formatter_node(state)
        state.execution_time_ms = (time.time() - start_time) * 1000
        yield ("response_formatter", state)

    def resume_hitl(self, state: AgentState, approved: bool) -> AgentState:
        """
        Tiếp tục thực thi phiên đang bị tạm dừng tại HITL Gate sau khi người dùng bấm Duyệt/Từ chối.
        """
        start_time = time.time()
        state.hitl_approved = approved

        state = self.hitl_node(state)
        if not approved:
            state.execution_time_ms = (time.time() - start_time) * 1000
            return state

        # Người dùng chấp thuận -> Thực thi tiếp
        state = self.executor_node(state)
        self._record_good_plan(state)
        state = self.formatter_node(state)
        state.execution_time_ms = (time.time() - start_time) * 1000
        return state

    def _record_good_plan(self, state: AgentState) -> None:
        """Tự động ghi nhận câu SQL đã thực thi thành công vào LongTermMemory (kế thừa DAIL-SQL)."""
        if state.query_result is not None and len(state.query_result) > 0 and state.sql_query:
            tables = state.schema_context.selected_tables if state.schema_context else []
            self.memory.long_term.save_plan(
                user_query=state.user_query,
                domain_id=state.domain_id or "real_estate",
                sql=state.sql_query,
                is_successful=True,
                tables_used=tables
            )
