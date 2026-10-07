"""
3-Tier Memory Architecture for Text-to-SQL Agent:
1. Short-Term Memory: Lưu tối đa 3 lỗi gần nhất theo 3 ngăn (DATA, SEMANTIC, GRAMMAR) để định tuyến cho LLM tự sửa.
2. Temporary Memory: Chấm điểm trạng thái theo phương trình Bellman v(St) = R_{t+1} + γ * v(S_{t+1}) để cắt tỉa nhánh lặp bế tắc.
3. Long-Term Memory: Lưu trữ tri thức Good Plans / Bad Plans / Common Knowledge chia sẻ giữa các phiên.
"""

import os
import json
from pathlib import Path
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

    def __init__(
        self,
        seed_defaults: bool = True,
        vector_backend: Optional[str] = None,
        qdrant_client: Optional[Any] = None,
        in_memory: bool = False,
        embedding_function: Optional[Any] = None
    ):
        self.good_plans: List[Dict[str, Any]] = []
        self.bad_plans: List[Dict[str, Any]] = []
        self.common_knowledge: List[Dict[str, Any]] = []
        self.vector_backend = vector_backend or "qdrant"
        self.in_memory = in_memory
        self.qdrant_client = qdrant_client
        self.embedding_function = embedding_function
        self.vector_index = None

        # Detect mock/dummy embedding: all-zero vectors make cosine similarity
        # undefined (0/0), producing non-deterministic retrieval. Skip the vector
        # index in that case and rely on Jaccard keyword matching instead.
        _is_mock_emb = (
            embedding_function is not None and (
                getattr(embedding_function, "_is_mock", False)
                or getattr(embedding_function, "name", lambda: "")() == "mock_embedding"
            )
        )

        if self.vector_backend == "qdrant" and not _is_mock_emb:
            try:
                from llama_index.core import VectorStoreIndex
                from app.rag.llamaindex_embedding import LlamaIndexBGEM3Embedding
                from app.rag.qdrant_provider import get_qdrant_client, get_qdrant_vector_store

                if self.qdrant_client is None:
                    self.qdrant_client = get_qdrant_client(in_memory=self.in_memory)
                self.embed_model = LlamaIndexBGEM3Embedding(embedding_function=self.embedding_function)
                try:
                    probe_vec = self.embed_model.get_text_embedding("probe")
                    vector_dim = len(probe_vec) if probe_vec else 1024
                except Exception:
                    vector_dim = 1024
                self.vector_store = get_qdrant_vector_store(self.qdrant_client, "few_shot_sql_plans", vector_dim=vector_dim)
                self.vector_index = VectorStoreIndex.from_vector_store(self.vector_store, embed_model=self.embed_model)
            except Exception as e:
                self.vector_index = None

        self.storage_file = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "data"
            / "long_term_memory.json"
        )

        if seed_defaults:
            self._seed_initial_plans()

        # Nạp các kế hoạch đã tích lũy và phản hồi người dùng trước đó
        self._load_persisted_plans()

    def _seed_initial_plans(self) -> None:
        """Nạp các mẫu SQL chuẩn tối ưu từ dbt Data Marts và Steiner Tree Joins cho E-commerce."""
        seed_data = [
            # E-commerce: dbt Marts Monthly Summary
            {
                "query": "Thống kê doanh thu và số lượng đơn hàng theo tháng",
                "domain_id": "ecommerce",
                "sql": "SELECT report_month, status, total_records, total_gross_revenue FROM fct_orders_monthly_summary ORDER BY report_month DESC LIMIT 12;",
                "tables_used": ["fct_orders_monthly_summary"],
                "description": "Truy vấn bảng dbt Marts tổng hợp theo tháng cho orders"
            },
            # E-commerce: Multi-table JOIN (Steiner Tree)
            {
                "query": "Thống kê tổng doanh thu GMV và số lượng đơn hàng theo khách hàng",
                "domain_id": "ecommerce",
                "sql": "SELECT c.customer_name, COUNT(o.order_id) AS total_orders, SUM(o.total_amount) AS gmv FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_name ORDER BY gmv DESC LIMIT 10;",
                "tables_used": ["customers", "orders"],
                "description": "Multi-table JOIN tính GMV khách hàng"
            },
            # Vietnam E-commerce: Shopee Orders Filter
            {
                "query": "Tìm các đơn hàng Shopee đã hoàn tất gần đây",
                "domain_id": "vietnam_ecommerce",
                "sql": "SELECT order_id, shop_name, order_status, total_amount FROM stg_shopee_orders WHERE order_status = 'COMPLETED' ORDER BY created_at DESC LIMIT 20;",
                "tables_used": ["stg_shopee_orders"],
                "description": "Lọc đơn hàng Shopee theo trạng thái"
            },
            # Vietnam E-commerce: TikTok / Shopee GMV by Shop
            {
                "query": "Thống kê tổng doanh thu GMV theo từng shop",
                "domain_id": "vietnam_ecommerce",
                "sql": "SELECT shop_name, COUNT(order_id) AS total_orders, SUM(total_amount) AS total_gmv FROM stg_shopee_orders GROUP BY shop_name ORDER BY total_gmv DESC LIMIT 10;",
                "tables_used": ["stg_shopee_orders"],
                "description": "Tính tổng GMV theo cửa hàng"
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

    def _index_doc_to_qdrant(self, record: Dict[str, Any]) -> None:
        """Đưa một kế hoạch tốt vào Qdrant Vector Index nếu có."""
        if self.vector_index:
            try:
                from llama_index.core import Document
                doc_text = (
                    f"Yêu cầu: {record['query']}\n"
                    f"Domain: {record['domain_id']}\n"
                    f"Bảng: {', '.join(record.get('tables_used', []))}\n"
                    f"Mô tả: {record.get('metadata', {}).get('description', '')}\n"
                    f"SQL: {record['sql']}"
                )
                doc = Document(
                    text=doc_text,
                    metadata={
                        "query": record["query"],
                        "domain_id": record["domain_id"],
                        "sql": record["sql"],
                        "tables_used": record.get("tables_used", []),
                        "description": record.get("metadata", {}).get("description", "")
                    }
                )
                self.vector_index.insert(doc)
            except Exception:
                pass

    def _sync_to_duckdb(self, record: Dict[str, Any], is_successful: bool) -> None:
        """Đồng bộ bản ghi tri thức vào bảng DuckDB _agent_memory_plans để lưu trữ và truy vấn phân tích."""
        try:
            from app.core.config import AppSettings
            db_path = AppSettings().DUCKDB_PATH
            if not os.path.exists(db_path):
                return
            import duckdb
            import hashlib
            from datetime import datetime

            plan_id = hashlib.md5(f"{record.get('domain_id', '')}:{record['query']}:{record['sql']}".encode()).hexdigest()
            conn = duckdb.connect(db_path, read_only=False)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _agent_memory_plans (
                    plan_id VARCHAR PRIMARY KEY,
                    query VARCHAR,
                    domain_id VARCHAR,
                    sql VARCHAR,
                    is_successful BOOLEAN,
                    tables_used VARCHAR,
                    rating VARCHAR,
                    source VARCHAR,
                    updated_at TIMESTAMP
                )
            """)
            tables_str = ", ".join(record.get("tables_used", []))
            rating_val = record.get("metadata", {}).get("rating", "up" if is_successful else "down")
            source_val = record.get("metadata", {}).get("source", "agent_auto" if is_successful else "user_feedback")

            conn.execute("""
                INSERT OR REPLACE INTO _agent_memory_plans 
                (plan_id, query, domain_id, sql, is_successful, tables_used, rating, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                plan_id,
                record["query"],
                record.get("domain_id", "default"),
                record["sql"],
                is_successful,
                tables_str,
                rating_val,
                source_val,
                datetime.now()
            ])
            conn.close()
        except Exception:
            pass

    def _load_persisted_plans(self) -> None:
        """Đọc danh sách good_plans và bad_plans đã lưu từ đĩa, phục hồi lại Qdrant index nếu cần."""
        if hasattr(self, "storage_file") and self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for gp in data.get("good_plans", []):
                    if not any(p["query"] == gp["query"] and p["sql"] == gp["sql"] for p in self.good_plans):
                        self.good_plans.append(gp)
                        self._index_doc_to_qdrant(gp)
                for bp in data.get("bad_plans", []):
                    if not any(p["query"] == bp["query"] and p["sql"] == bp["sql"] for p in self.bad_plans):
                        self.bad_plans.append(bp)
            except Exception as e:
                import logging
                logging.getLogger("three_tier_memory").warning(f"Không thể đọc persisted memory plans: {e}")

    def _save_persisted_plans(self) -> None:
        """Ghi danh sách good_plans và bad_plans vào đĩa."""
        if hasattr(self, "storage_file"):
            try:
                self.storage_file.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "good_plans": self.good_plans,
                    "bad_plans": self.bad_plans
                }
                tmp_file = self.storage_file.with_suffix(".tmp")
                tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp_file.replace(self.storage_file)
            except Exception as e:
                import logging
                logging.getLogger("three_tier_memory").warning(f"Không thể lưu persisted memory plans: {e}")

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
            # Xoá khỏi bad_plans nếu câu này trước đó từng bị đánh dấu bad
            self.bad_plans = [p for p in self.bad_plans if not (p["query"] == user_query and p["sql"] == sql)]
            if not any(p["query"] == user_query and p["sql"] == sql for p in self.good_plans):
                self.good_plans.append(record)
                self._index_doc_to_qdrant(record)
        else:
            # Xoá khỏi good_plans nếu trước đó từng được coi là good plan
            self.good_plans = [p for p in self.good_plans if not (p["query"] == user_query and p["sql"] == sql)]
            if not any(p["query"] == user_query and p["sql"] == sql for p in self.bad_plans):
                self.bad_plans.append(record)

        self._save_persisted_plans()
        self._sync_to_duckdb(record, is_successful=is_successful)


    def get_relevant_bad_plans(
        self,
        query: str,
        domain_id: str,
        top_k: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các câu SQL từng bị người dùng đánh giá sai hoặc thất bại tương tự
        để đưa vào prompt làm Negative Examples (In-Context Learning), giúp LLM tránh lặp lại lỗi.
        """
        candidates = [p for p in self.bad_plans if p.get("domain_id") in (domain_id, "default")]
        if not candidates:
            return []

        query_tokens = set(query.lower().split())
        scored_candidates = []
        for cand in candidates:
            cand_tokens = set(cand["query"].lower().split())
            overlap = len(query_tokens & cand_tokens)
            union = len(query_tokens | cand_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            if jaccard > 0.15:
                scored_candidates.append((jaccard, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_candidates[:top_k]]

    def get_relevant_few_shots(
        self,
        query: str,
        domain_id: str,
        top_k: int = 2,
        target_tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm Top-K ví dụ mẫu tương đồng nhất (Dynamic Few-Shot Retrieval theo DAIL-SQL).
        Ưu tiên đối sánh ngữ nghĩa qua LlamaIndex + Qdrant Cosine Similarity kết hợp lọc domain và đối sánh bảng.
        Tự động fallback về Jaccard keyword matching nếu vector retrieval chưa khởi tạo.
        """
        # 1. Thử Vector Retrieval qua LlamaIndex + Qdrant
        if self.vector_index:
            try:
                retriever = self.vector_index.as_retriever(similarity_top_k=top_k * 3)
                nodes = retriever.retrieve(query)
                target_tables_set = set(t.lower() for t in (target_tables or []))
                vector_scored = []

                for node in nodes:
                    m = node.node.metadata
                    if m.get("domain_id") != domain_id:
                        continue

                    score = float(node.score or 0.0) * 10.0
                    cand_tables = set(t.lower() for t in m.get("tables_used", []))
                    if target_tables_set and cand_tables:
                        overlap = len(target_tables_set & cand_tables)
                        score += overlap * 3.0

                    cand_record = {
                        "query": m.get("query", ""),
                        "domain_id": m.get("domain_id", domain_id),
                        "sql": m.get("sql", ""),
                        "tables_used": m.get("tables_used", []),
                        "metadata": {"description": m.get("description", "")}
                    }
                    vector_scored.append((score, cand_record))

                if vector_scored:
                    vector_scored.sort(key=lambda x: x[0], reverse=True)
                    seen_sqls = set()
                    final_results = []
                    for _, c in vector_scored:
                        if c["sql"] not in seen_sqls:
                            seen_sqls.add(c["sql"])
                            final_results.append(c)
                            if len(final_results) >= top_k:
                                break
                    if final_results:
                        return final_results
            except Exception:
                pass

        # 2. Fallback: Jaccard keyword matching
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

    def __init__(
        self,
        vector_backend: Optional[str] = None,
        qdrant_client: Optional[Any] = None,
        in_memory: bool = False,
        embedding_function: Optional[Any] = None,
        seed_defaults: bool = True
    ):
        self.short_term = ShortTermMemory()
        self.temporary = TemporaryMemory()
        self.long_term = LongTermMemory(
            seed_defaults=seed_defaults,
            vector_backend=vector_backend,
            qdrant_client=qdrant_client,
            in_memory=in_memory,
            embedding_function=embedding_function
        )
