"""
Schema Linking Node (Node 2).
Sử dụng BilingualDataProfilingGraph và giải thuật Minimum Steiner Tree
để chọn lọc bảng/cột và suy luận đường dẫn JOIN tối ưu cho câu hỏi.
"""

from typing import Dict, Optional, Any
from app.agent.state import AgentState
from app.rag.profiling_graph import BilingualDataProfilingGraph


class SchemaLinkingNode:
    """Node trích xuất schema rút gọn và liên kết đa bảng bằng Steiner Tree."""

    def __init__(self, embedding_function: Optional[Any] = None):
        self.embedding_function = embedding_function
        self._graph_cache: Dict[str, BilingualDataProfilingGraph] = {}

    def _get_graph(self, domain_id: str) -> BilingualDataProfilingGraph:
        if domain_id not in self._graph_cache:
            self._graph_cache[domain_id] = BilingualDataProfilingGraph(
                domain_id=domain_id,
                embedding_function=self.embedding_function
            )
        return self._graph_cache[domain_id]

    def __call__(self, state: AgentState) -> AgentState:
        return self.execute(state)

    def execute(self, state: AgentState) -> AgentState:
        state.log_step("schema_linking")
        domain_id = state.domain_id or "real_estate"
        graph = self._get_graph(domain_id)

        query = state.normalized_query or state.user_query
        schema_context = graph.link_schema(query)
        state.schema_context = schema_context
        return state
