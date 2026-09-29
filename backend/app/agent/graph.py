"""
LangGraph Stateful Machine & Agent Orchestrator.
Điều phối toàn diện cỗ máy trạng thái đa tác tử bằng LangGraph:
START -> Intent & Clarification -> Schema Linking (Steiner Tree) -> SQL Generator (Coder)
-> Plan Validator (5 Tầng Guardrail & Self-Correction Loop) -> HITL Gate -> Executor -> Response Formatter -> END.
"""

import time
import logging
from typing import Optional, Dict, Any, Generator, Tuple, Union

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

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
    Cỗ máy điều phối State Machine đa tác tử cho Text-to-SQL dựa trên LangGraph.
    Cung cấp đồng thời cơ chế invoke (đồng bộ) và stream (phục vụ SSE streaming logs),
    kèm State Persistence (Checkpointer) và Self-Correction Loop.
    """

    def __init__(
        self,
        llm: Optional[DualModelLLM] = None,
        embedding_function: Optional[Any] = None,
        doris_client: Optional[Any] = None,
        use_explain: bool = False,
        checkpointer: Optional[Any] = None
    ):
        self.llm = llm or DualModelLLM()
        self.memory = ThreeTierMemory(embedding_function=embedding_function)
        self.use_explain = use_explain

        # Khởi tạo các Node tác tử độc lập
        self.intent_node = IntentClarifierNode(llm=self.llm)
        self.schema_node = SchemaLinkingNode(embedding_function=embedding_function)
        self.sql_node = SQLGeneratorNode(llm=self.llm, memory=self.memory)
        self.validator_node = ValidatorNode(memory=self.memory, use_explain=use_explain)
        self.hitl_node = HITLNode()
        self.executor_node = ExecutorNode(doris_client=doris_client)
        self.formatter_node = ResponseFormatterNode(llm=self.llm)

        # Bộ lưu trữ trạng thái phiên làm việc (Checkpointer)
        self.checkpointer = checkpointer if checkpointer is not None else MemorySaver()

        # Xây dựng và biên dịch LangGraph StateGraph
        self.graph = self._build_graph()

    def _build_graph(self):
        """Xây dựng và biên dịch LangGraph StateGraph chuẩn."""
        workflow = StateGraph(AgentState)

        # 1. Đăng ký các Nodes vào StateGraph
        workflow.add_node("intent_clarifier", self.intent_node)
        workflow.add_node("schema_linking", self.schema_node)
        workflow.add_node("sql_generator", self.sql_node)
        workflow.add_node("plan_validator", self.validator_node)
        workflow.add_node("hitl_gate", self.hitl_node)
        workflow.add_node("executor", self._execute_and_record)
        workflow.add_node("response_formatter", self.formatter_node)

        # 2. Cạnh bắt đầu (START -> intent_clarifier)
        workflow.add_edge(START, "intent_clarifier")

        # 3. Điều kiện rẽ nhánh sau Intent Clarifier
        def route_after_intent(state: Union[AgentState, dict]) -> str:
            clarify = state.clarification_needed if isinstance(state, AgentState) else state.get("clarification_needed", False)
            val_res = state.validation_result if isinstance(state, AgentState) else state.get("validation_result")
            if clarify or (val_res and not getattr(val_res, "is_valid", True)):
                return END
            return "schema_linking"

        workflow.add_conditional_edges(
            "intent_clarifier",
            route_after_intent,
            {
                "schema_linking": "schema_linking",
                END: END
            }
        )

        workflow.add_edge("schema_linking", "sql_generator")
        workflow.add_edge("sql_generator", "plan_validator")

        # 4. Điều kiện rẽ nhánh sau Plan Validator (Self-Correction Loop & Bellman pruning)
        def route_after_validator(state: Union[AgentState, dict]) -> str:
            val_res = state.validation_result if isinstance(state, AgentState) else state.get("validation_result")
            is_valid = getattr(val_res, "is_valid", False) if val_res else False
            if is_valid:
                return "hitl_gate"

            # Cắt tỉa sớm nếu phát hiện kẹt vòng lặp (Bellman scoring)
            if self.memory.temporary.is_stuck_in_loop():
                logger.warning("LangGraph: Phát hiện kẹt vòng lặp (Bellman Pruning), dừng lặp.")
                return END

            retry_count = state.retry_count if isinstance(state, AgentState) else state.get("retry_count", 0)
            max_retries = state.max_retries if isinstance(state, AgentState) else state.get("max_retries", 3)
            if retry_count < max_retries:
                logger.info(f"LangGraph Self-correction: Thử sửa lỗi lần {retry_count}/{max_retries}")
                return "sql_generator"
            return END

        workflow.add_conditional_edges(
            "plan_validator",
            route_after_validator,
            {
                "hitl_gate": "hitl_gate",
                "sql_generator": "sql_generator",
                END: END
            }
        )

        # 5. Điều kiện rẽ nhánh sau HITL Gate
        def route_after_hitl(state: Union[AgentState, dict]) -> str:
            requires_hitl = state.requires_hitl if isinstance(state, AgentState) else state.get("requires_hitl", False)
            hitl_approved = state.hitl_approved if isinstance(state, AgentState) else state.get("hitl_approved")
            if requires_hitl and hitl_approved is not True:
                return END  # Tạm dừng đợi duyệt thủ công
            return "executor"

        workflow.add_conditional_edges(
            "hitl_gate",
            route_after_hitl,
            {
                "executor": "executor",
                END: END
            }
        )

        workflow.add_edge("executor", "response_formatter")
        workflow.add_edge("response_formatter", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _execute_and_record(self, state: AgentState) -> AgentState:
        """Thực thi truy vấn và tự động lưu mẫu tốt vào LongTermMemory."""
        state = self.executor_node(state)
        self._record_good_plan(state)
        return state

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
        domain_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> AgentState:
        """
        Thực thi toàn bộ đồ thị theo cơ chế đồng bộ qua LangGraph.
        """
        from app.core.logger import log_audit_event
        state = self._prepare_state(input_val, domain_id)
        start_time = time.time()
        
        log_audit_event(
            user_id=getattr(state, "user_id", None),
            action="EXECUTE_QUERY_SYNC",
            domain_id=state.domain_id,
            details={"query": state.user_query}
        )

        run_config = config or {
            "configurable": {"thread_id": state.session_id},
            "recursion_limit": 50
        }

        result = self.graph.invoke(state, config=run_config)

        if isinstance(result, dict):
            final_state = AgentState(**result)
        else:
            final_state = result

        final_state.execution_time_ms = (time.time() - start_time) * 1000
        return final_state

    def stream(
        self,
        input_val: Union[str, Dict[str, Any], AgentState],
        domain_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Generator[Tuple[str, AgentState], None, None]:
        """
        Thực thi đồ thị theo dạng streaming (phục vụ Server-Sent Events SSE).
        Phát ra từng cặp (tên_node, trạng_thái_hiện_tại) sau mỗi bước của LangGraph.
        """
        from app.core.logger import log_audit_event
        state = self._prepare_state(input_val, domain_id)
        start_time = time.time()
        
        log_audit_event(
            user_id=getattr(state, "user_id", None),
            action="EXECUTE_QUERY_STREAM",
            domain_id=state.domain_id,
            details={"query": state.user_query}
        )

        run_config = config or {
            "configurable": {"thread_id": state.session_id},
            "recursion_limit": 50
        }

        for step in self.graph.stream(state, config=run_config):
            for node_name, state_val in step.items():
                if isinstance(state_val, dict):
                    curr_state = AgentState(**state_val)
                else:
                    curr_state = state_val
                curr_state.execution_time_ms = (time.time() - start_time) * 1000
                yield (node_name, curr_state)

    def resume_hitl(self, state: AgentState, approved: bool) -> AgentState:
        """Tiếp tục quy trình sau khi HITL duyệt hoặc từ chối."""
        from app.core.logger import log_audit_event
        start_time = time.time()
        
        log_audit_event(
            user_id=getattr(state, "user_id", None),
            action="HITL_APPROVE" if approved else "HITL_REJECT",
            domain_id=state.domain_id,
            sql_query=state.sql_query
        )
        
        state.hitl_approved = approved

        state = self.hitl_node(state)
        if not approved:
            state.execution_time_ms = (time.time() - start_time) * 1000
            return state

        # Người dùng chấp thuận -> Thực thi tiếp các bước còn lại
        state = self._execute_and_record(state)
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
