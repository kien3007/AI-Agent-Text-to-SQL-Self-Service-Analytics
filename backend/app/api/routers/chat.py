"""
Chat & SSE Streaming API Router.
Xử lý các câu hỏi ngôn ngữ tự nhiên từ người dùng,
truyền dữ liệu nhật ký suy nghĩ thời gian thực qua Server-Sent Events (SSE),
và quản lý phê duyệt Human-In-The-Loop (HITL Gate).
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends
from sse_starlette.sse import EventSourceResponse

from app.agent.state import AgentState
from app.agent.graph import AgentOrchestrator
from app.schemas.api import ChatRequest, ChatResponse, HITLDecisionRequest

router = APIRouter(prefix="/chat", tags=["Chat"])

# --------------------------------------------------------------------------
# Persistent State: thread-safe với asyncio.Lock
# --------------------------------------------------------------------------
SESSION_STORE: Dict[str, AgentState] = {}
CONVERSATION_HISTORY: Dict[str, List[Dict[str, str]]] = {}

_STATE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent  # backend/
    / "data" / "chat_state.json"
)
_state_lock = asyncio.Lock()


def _load_chat_state():
    """Load state từ file khi khởi động (chạy 1 lần, không cần lock)."""
    if not _STATE_FILE.exists():
        return
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.get("history", {}).items():
            CONVERSATION_HISTORY[k] = v
        for k, v in data.get("sessions", {}).items():
            try:
                SESSION_STORE[k] = AgentState(**v)
            except Exception:
                pass  # Bỏ qua session không còn compatible
    except Exception as e:
        import logging; logging.getLogger("chat").warning(f"Không thể load chat state: {e}")


async def _save_chat_state():
    """Ghi state vào file với asyncio.Lock để tránh race condition."""
    async with _state_lock:
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "history":  CONVERSATION_HISTORY,
                "sessions": {
                    k: v.model_dump()
                    for k, v in SESSION_STORE.items()
                },
            }
            # Ghi vào file tạm rồi rename để tránh corruption
            tmp_file = _STATE_FILE.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp_file.replace(_STATE_FILE)
        except Exception as e:
            import logging; logging.getLogger("chat").error(f"Không thể lưu chat state: {e}")


# Load khi khởi động
_load_chat_state()

# Khởi tạo instance AgentOrchestrator dùng chung
orchestrator = AgentOrchestrator(use_explain=True)


def _convert_state_to_response(state: AgentState) -> ChatResponse:
    """Chuyển đổi đối tượng AgentState nội bộ thành ChatResponse chuẩn API."""
    return ChatResponse(
        session_id=state.session_id,
        domain_id=state.domain_id,
        user_query=state.user_query,
        complexity_level=state.complexity_level,
        clarification_needed=state.clarification_needed,
        clarification_question=state.clarification_question,
        requires_hitl=state.requires_hitl,
        hitl_approved=state.hitl_approved,
        sql_query=state.sql_query,
        final_response=state.final_response,
        chart_config=state.chart_config,
        column_names=state.column_names,
        query_result=state.query_result,
        execution_time_ms=state.execution_time_ms,
        steps_executed=state.steps_executed
    )

def _load_history(conversation_id: Optional[str]) -> List[Dict]:
    if not conversation_id:
        return []
    return CONVERSATION_HISTORY.get(conversation_id, [])[-6:]  # Giữ 3 turns gần nhất

async def _save_history(conversation_id: str, query: str, response: str):
    if conversation_id not in CONVERSATION_HISTORY:
        CONVERSATION_HISTORY[conversation_id] = []
    CONVERSATION_HISTORY[conversation_id].extend([
        {"role": "user", "content": query},
        {"role": "assistant", "content": response or ""}
    ])
    await _save_chat_state()

from app.core.auth import get_current_user, UserContext, check_and_deduct_budget

@router.post("", response_model=ChatResponse)
async def execute_query_sync(req: ChatRequest, user: UserContext = Depends(get_current_user)):
    """
    Thực thi câu hỏi tự nhiên theo cơ chế đồng bộ (blocking REST API).
    Trả về toàn bộ kết quả sau khi hoàn tất.
    """
    check_and_deduct_budget(user.user_id)
    try:
        history = _load_history(req.conversation_id)
        initial_state = {
            "user_query": req.query,
            "domain_id": req.domain_id,
            "conversation_history": history,
            "user_id": user.user_id,
            "user_role": user.role
        }
        if req.session_id:
            initial_state["session_id"] = req.session_id

        loop = asyncio.get_event_loop()
        state = await loop.run_in_executor(None, lambda: orchestrator.invoke(input_val=initial_state, domain_id=req.domain_id))

        if state.requires_hitl and state.hitl_approved is None:
            SESSION_STORE[state.session_id] = state
            await _save_chat_state()
        else:
            if req.conversation_id:
                await _save_history(req.conversation_id, req.query, state.final_response)
            from app.core.logger import log_audit_event
            log_audit_event(
                user_id=user.user_id,
                action="QUERY_SUCCESS_SYNC",
                domain_id=state.domain_id,
                sql_query=state.sql_query,
                details={"tables_used": getattr(state.schema_context, "selected_tables", []) if state.schema_context else []}
            )

        return _convert_state_to_response(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi Agent: {e}")


@router.post("/stream")
async def execute_query_stream(req: ChatRequest, request: Request, user: UserContext = Depends(get_current_user)):
    """
    Thực thi câu hỏi tự nhiên và phát luồng sự kiện Server-Sent Events (SSE).
    Phù hợp cho giao diện Chatbot hiển thị từng bước suy nghĩ của Agent.
    """
    check_and_deduct_budget(user.user_id)
    async def event_generator():
        try:
            # Load history
            history = _load_history(req.conversation_id)
            initial_state = {
                "user_query": req.query,
                "domain_id": req.domain_id,
                "conversation_history": history,
                "user_id": user.user_id,
                "user_role": user.role
            }
            if req.session_id:
                initial_state["session_id"] = req.session_id

            # Chạy generator stream của orchestrator
            for step_name, current_state in orchestrator.stream(input_val=initial_state, domain_id=req.domain_id):
                # Kiểm tra client ngắt kết nối
                if await request.is_disconnected():
                    break

                # 1. Phát sự kiện từng bước xử lý
                step_data = {
                    "step": step_name,
                    "session_id": current_state.session_id,
                    "domain_id": current_state.domain_id,
                    "complexity_level": current_state.complexity_level,
                    "sql_query": current_state.sql_query
                }
                yield {
                    "event": "step",
                    "data": json.dumps(step_data, ensure_ascii=False)
                }

                # 2. Nếu cần làm rõ câu hỏi (Clarification)
                if current_state.clarification_needed:
                    yield {
                        "event": "clarification",
                        "data": json.dumps({
                            "session_id": current_state.session_id,
                            "question": current_state.clarification_question
                        }, ensure_ascii=False)
                    }
                    return

                # 3. Nếu cần duyệt HITL
                if current_state.requires_hitl and current_state.hitl_approved is None:
                    SESSION_STORE[current_state.session_id] = current_state
                    await _save_chat_state()
                    yield {
                        "event": "hitl_required",
                        "data": json.dumps({
                            "session_id": current_state.session_id,
                            "sql_query": current_state.sql_query,
                            "warning": "Truy vấn lớn cần phê duyệt trước khi thực thi."
                        }, ensure_ascii=False)
                    }
                    return

                await asyncio.sleep(0.02)

            # 4. Khi hoàn tất toàn bộ pipeline, phát sự kiện complete
            if req.conversation_id:
                await _save_history(req.conversation_id, req.query, current_state.final_response)
                
            from app.core.logger import log_audit_event
            log_audit_event(
                user_id=user.user_id,
                action="QUERY_SUCCESS_STREAM",
                domain_id=current_state.domain_id,
                sql_query=current_state.sql_query,
                details={"tables_used": getattr(current_state.schema_context, "selected_tables", []) if current_state.schema_context else []}
            )
                
            resp = _convert_state_to_response(current_state)
            yield {
                "event": "complete",
                "data": json.dumps(resp.model_dump(), ensure_ascii=False)
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


@router.post("/hitl", response_model=ChatResponse)
async def handle_hitl_decision(req: HITLDecisionRequest, user: UserContext = Depends(get_current_user)):
    """
    Tiếp tục thực thi câu lệnh SQL bị tạm dừng sau khi người dùng bấm Duyệt/Từ chối trên Modal.
    """
    state = SESSION_STORE.get(req.session_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy phiên '{req.session_id}' đang chờ duyệt HITL."
        )

    try:
        if req.sql_override:
            state.sql_query = req.sql_override

        loop = asyncio.get_event_loop()
        finished_state = await loop.run_in_executor(
            None, lambda: orchestrator.resume_hitl(state, approved=req.approved)
        )
        SESSION_STORE.pop(req.session_id, None)
        await _save_chat_state()
        return _convert_state_to_response(finished_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tiếp tục phiên HITL: {e}")
