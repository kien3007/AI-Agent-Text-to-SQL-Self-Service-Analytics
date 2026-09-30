"""
Bilingual Data Profiling Graph (Đồ thị hồ sơ dữ liệu song ngữ & Schema Linking Đa Domain).
Sử dụng BAAI/bge-m3 + LlamaIndex + Qdrant + NetworkX để liên kết ngữ nghĩa câu hỏi người dùng
với CSDL DuckDB Data Warehouse, hỗ trợ đa bảng và tự động suy luận phép nối JOIN qua thuật toán Minimum Steiner Tree.
"""

import os
import sys
import re
from typing import Dict, Any, List, Set, Optional, Tuple
import networkx as nx
from llama_index.core import VectorStoreIndex, Document, StorageContext
from app.rag.llamaindex_embedding import LlamaIndexBGEM3Embedding
from app.rag.qdrant_provider import get_qdrant_client, get_qdrant_vector_store

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import app khi chạy độc lập
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.glossary import VietnameseBusinessGlossary
from app.core.domain_manager import DomainManager
from app.core.config import settings
from app.rag.embeddings import BGEM3EmbeddingFunction
from app.schemas.domain import DomainConfig, TableProfile, ColumnProfile, RelationshipProfile, MetricProfile
from app.schemas.schema_context import SchemaContext, ColumnContext, MetricContext


class BilingualDataProfilingGraph:
    """
    Đồ thị hồ sơ dữ liệu song ngữ kết hợp LlamaIndex + Qdrant Vector Store và Graph Network:
    1. Quản lý biểu đồ quan hệ giữa Bảng, Cột, Danh mục phân loại và Chỉ số nghiệp vụ.
    2. Nạp cấu hình động theo Domain (BĐS, E-commerce, Y tế...).
    3. Tự động suy luận đường dẫn JOIN tối ưu qua giải thuật Minimum Steiner Tree trên NetworkX.
    4. Cung cấp cơ chế phòng vệ Fan-Trap khi thực hiện JOIN đa bảng.
    """

    def __init__(
        self,
        domain_id: Optional[str] = None,
        domain_config: Optional[DomainConfig] = None,
        embedding_function: Optional[Any] = None,
        vector_backend: Optional[str] = None,
        qdrant_client: Optional[Any] = None,
        in_memory: bool = False,
        **kwargs: Any
    ):
        self.in_memory = in_memory
        self.qdrant_client = qdrant_client

        self.domain_manager = DomainManager()
        if domain_config:
            self.domain = domain_config
        elif domain_id:
            found = self.domain_manager.get_domain(domain_id)
            if not found:
                found = self.domain_manager.get_active_domain_config()
            self.domain = found
        else:
            self.domain = self.domain_manager.get_active_domain_config()

        self.domain_id = self.domain.domain_id
        self.glossary = VietnameseBusinessGlossary(domain_manager=self.domain_manager)
        self.embedding_fn = embedding_function or BGEM3EmbeddingFunction()
        self.llama_embed = LlamaIndexBGEM3Embedding(embedding_function=self.embedding_fn)

        # LlamaIndex / Qdrant stores & indexes
        self.schema_store = None
        self.metrics_store = None
        self.cat_store = None
        self.schema_index = None
        self.metrics_index = None
        self.cat_index = None

        # In-memory Knowledge Graph cho Columns & Tables
        self.graph = nx.DiGraph()
        # Đồ thị vô hướng giữa các bảng để giải thuật Steiner Tree
        self.table_graph = nx.Graph()

        self._init_collections()
        self._build_in_memory_graph()

    def _init_collections(self):
        """Khởi tạo collection trong Qdrant On-premise (LlamaIndex) phân tách theo domain."""
        prefix = self.domain_id

        if self.qdrant_client is None:
            self.qdrant_client = get_qdrant_client(in_memory=self.in_memory)

        # Tự động phát hiện vector dimension (1024 cho bge-m3 hoặc 128 cho MockEmbedding trong unit test)
        try:
            probe_vec = self.llama_embed.get_text_embedding("probe")
            vector_dim = len(probe_vec) if probe_vec else 1024
        except Exception:
            vector_dim = 1024

        schema_col = f"{prefix}_schema_profiles"
        metrics_col = f"{prefix}_metrics_profiles"
        cat_col = f"{prefix}_category_profiles"

        self.col_schema_name = schema_col
        self.col_metrics_name = metrics_col
        self.col_categories_name = cat_col

        self.schema_store = get_qdrant_vector_store(self.qdrant_client, schema_col, vector_dim=vector_dim)
        self.metrics_store = get_qdrant_vector_store(self.qdrant_client, metrics_col, vector_dim=vector_dim)
        self.cat_store = get_qdrant_vector_store(self.qdrant_client, cat_col, vector_dim=vector_dim)

        self.schema_index = VectorStoreIndex.from_vector_store(self.schema_store, embed_model=self.llama_embed)
        self.metrics_index = VectorStoreIndex.from_vector_store(self.metrics_store, embed_model=self.llama_embed)
        self.cat_index = VectorStoreIndex.from_vector_store(self.cat_store, embed_model=self.llama_embed)

    def _build_in_memory_graph(self):
        """Xây dựng đồ thị tri thức quan hệ Schema & Domain trong NetworkX từ DomainConfig."""
        self.graph.clear()
        self.table_graph.clear()

        # 1. Thêm các Node Bảng và Cột
        for t_name, table in self.domain.tables.items():
            t_node = f"Table:{t_name}"
            self.graph.add_node(
                t_node,
                type="table",
                table_name=t_name,
                vn_name=table.vn_name,
                description=table.description,
                primary_key=table.primary_key
            )
            # Thêm vào table_graph
            self.table_graph.add_node(t_name, vn_name=table.vn_name, description=table.description)

            for col_name, col in table.columns.items():
                col_node = f"Col:{t_name}.{col_name}"
                self.graph.add_node(
                    col_node,
                    type="column",
                    table_name=t_name,
                    name=col_name,
                    data_type=col.data_type,
                    vn_name=col.vn_name,
                    en_name=col.en_name,
                    description=col.description,
                    is_partition=col.is_partition_or_dist,
                    sample_values=col.sample_values
                )
                self.graph.add_edge(t_node, col_node, relation="HAS_COLUMN")

                # Alias node Col:<col_name> để hỗ trợ tra cứu nhanh trong 1 bảng
                alias_node = f"Col:{col_name}"
                if not self.graph.has_node(alias_node):
                    self.graph.add_node(alias_node, real_node=col_node, name=col_name)

        # 2. Thêm các Mối quan hệ Khóa ngoại (Relationships)
        for rel in self.domain.relationships:
            from_t = rel.from_table
            to_t = rel.to_table
            from_col = f"Col:{from_t}.{rel.from_column}"
            to_col = f"Col:{to_t}.{rel.to_column}"

            if self.graph.has_node(from_col) and self.graph.has_node(to_col):
                self.graph.add_edge(from_col, to_col, relation="FOREIGN_KEY", cardinality=rel.cardinality)

            # Thêm cạnh vào table_graph cho Steiner Tree
            self.table_graph.add_edge(
                from_t,
                to_t,
                weight=rel.weight,
                relationship=rel,
                join_clause=rel.join_clause,
                cardinality=rel.cardinality
            )

        # 3. Thêm Chỉ số nghiệp vụ (Metrics)
        for metric_id, m_data in self.domain.metrics.items():
            m_node = f"Metric:{metric_id}"
            self.graph.add_node(
                m_node,
                type="metric",
                id=metric_id,
                sql_expression=m_data.sql_expression,
                description=m_data.description
            )
            for c_dep in m_data.depends_on_columns:
                self.graph.add_edge(m_node, f"Col:{c_dep}", relation="DEPENDS_ON")

    def infer_join_paths(self, target_tables: Set[str]) -> Tuple[List[str], List[str], List[str]]:
        """
        Sử dụng Minimum Steiner Tree trên self.table_graph để tìm cây khung con kết nối tối ưu nhất
        giữa các target_tables, tự động chèn bảng trung gian và sinh mệnh đề JOIN ... ON ... chuẩn xác.
        Trả về: (ordered_tables, join_clauses, cardinality_warnings)
        """
        if not target_tables:
            default_t = next(iter(self.domain.tables.keys())) if self.domain.tables else ""
            return [default_t], [], [] if default_t else ([], [], [])

        if len(target_tables) == 1:
            return list(target_tables), [], []

        valid_targets = [t for t in target_tables if self.table_graph.has_node(t)]
        if len(valid_targets) <= 1:
            return list(target_tables), [], []

        # 1. Tìm cây khung kết nối tối ưu (Steiner Tree)
        try:
            import networkx.algorithms.approximation as appx
            steiner_tree = appx.steiner_tree(self.table_graph, terminal_nodes=valid_targets, weight="weight")
        except Exception:
            steiner_tree = nx.Graph()
            target_list = list(valid_targets)
            root = target_list[0]
            for other in target_list[1:]:
                if nx.has_path(self.table_graph, root, other):
                    path = nx.shortest_path(self.table_graph, root, other, weight="weight")
                    nx.add_path(steiner_tree, path)
                else:
                    steiner_tree.add_node(other)

        if not steiner_tree.nodes():
            return list(target_tables), [], []

        # 2. Chọn root table (bảng có bậc kết nối cao nhất)
        root_table = max(steiner_tree.nodes(), key=lambda n: steiner_tree.degree(n))

        # 3. Duyệt BFS để sinh mệnh đề JOIN theo đúng thứ tự
        ordered_tables = [root_table]
        join_clauses = []
        cardinality_warnings = []
        visited = {root_table}
        queue = [root_table]

        while queue:
            curr = queue.pop(0)
            for neighbor in steiner_tree.neighbors(curr):
                if neighbor not in visited:
                    visited.add(neighbor)
                    ordered_tables.append(neighbor)
                    queue.append(neighbor)

                    edge_data = self.table_graph.get_edge_data(curr, neighbor) or {}
                    rel: Optional[RelationshipProfile] = edge_data.get("relationship")
                    if rel:
                        if rel.from_table == curr and rel.to_table == neighbor:
                            join_clauses.append(
                                f"{rel.join_type} JOIN {neighbor} ON {curr}.{rel.from_column} = {neighbor}.{rel.to_column}"
                            )
                            if rel.cardinality in ["1:N", "N:N"]:
                                cardinality_warnings.append(
                                    f"Quan hệ 1-N giữa '{curr}' và '{neighbor}' có thể gây nhân đôi bản ghi (Fan Trap) khi thực hiện SUM/COUNT."
                                )
                        elif rel.from_table == neighbor and rel.to_table == curr:
                            join_clauses.append(
                                f"{rel.join_type} JOIN {neighbor} ON {neighbor}.{rel.from_column} = {curr}.{rel.to_column}"
                            )
                            if rel.cardinality in ["N:1", "N:N"]:
                                cardinality_warnings.append(
                                    f"Quan hệ N-1 giữa '{curr}' và '{neighbor}': hãy chú ý kiểm tra mệnh đề GROUP BY nếu gộp số liệu."
                                )
                        else:
                            join_clauses.append(f"LEFT JOIN {neighbor} ON {rel.join_clause}")
                    else:
                        clause = edge_data.get("join_clause", "")
                        if clause:
                            join_clauses.append(f"LEFT JOIN {neighbor} ON {clause}")

        return ordered_tables, join_clauses, cardinality_warnings

    def index_all(self, distinct_categories: Optional[Dict[str, Any]] = None, force: bool = False):
        """
        Lập chỉ mục toàn bộ Metadata, Danh mục và Chỉ số của Domain vào Qdrant qua LlamaIndex.
        """
        try:
            coll_info = self.qdrant_client.get_collection(self.schema_store.collection_name)
            existing_schema_count = coll_info.points_count
        except Exception:
            existing_schema_count = 0

        if existing_schema_count > 0 and not force:
            print(f"[ProfilingGraph] Index của domain '{self.domain_id}' đã tồn tại ({existing_schema_count} items). Bỏ qua.")
            return

        print(f"[ProfilingGraph] Bắt đầu lập chỉ mục ngữ nghĩa cho domain '{self.domain_id}' với bge-m3...")

        # 1. Lập chỉ mục Schema Profiles (Cột và Bảng)
        schema_docs = []
        schema_ids = []
        schema_metadatas = []

        for t_name, table in self.domain.tables.items():
            for col_name, col in table.columns.items():
                doc_text = (
                    f"Bảng CSDL: {t_name}\n"
                    f"Tên cột CSDL: {col_name}\n"
                    f"Tên Tiếng Việt: {col.vn_name}\n"
                    f"Tên Tiếng Anh: {col.en_name or ''}\n"
                    f"Kiểu dữ liệu: {col.data_type}\n"
                    f"Mô tả nghiệp vụ: {col.description}\n"
                    f"Từ đồng nghĩa / Tìm kiếm: {', '.join(col.synonyms)}\n"
                    f"Ví dụ giá trị mẫu: {', '.join(str(v) for v in col.sample_values)}"
                )
                schema_docs.append(doc_text)
                schema_ids.append(f"{t_name}_{col_name}")
                schema_metadatas.append({
                    "table_name": t_name,
                    "column_name": col_name,
                    "data_type": col.data_type,
                    "vn_name": col.vn_name,
                    "is_partition": col.is_partition_or_dist
                })

        if schema_docs:
            print(f"[ProfilingGraph] Đang nạp {len(schema_docs)} cột vào schema collection...")
            schema_llama_docs = [
                Document(text=doc, id_=did, metadata=m)
                for doc, did, m in zip(schema_docs, schema_ids, schema_metadatas)
            ]
            storage_ctx = StorageContext.from_defaults(vector_store=self.schema_store)
            self.schema_index = VectorStoreIndex.from_documents(
                schema_llama_docs, storage_context=storage_ctx, embed_model=self.llama_embed
            )

        # 2. Lập chỉ mục Chỉ số nghiệp vụ
        metric_docs = []
        metric_ids = []
        metric_metadatas = []
        for metric_id, m_data in self.domain.metrics.items():
            doc_text = (
                f"Chỉ số phân tích: {metric_id}\n"
                f"Thuật ngữ Tiếng Việt: {', '.join(m_data.vn_terms)}\n"
                f"Thuật ngữ Tiếng Anh: {', '.join(m_data.en_terms)}\n"
                f"Công thức SQL: {m_data.sql_expression}\n"
                f"Ý nghĩa: {m_data.description}"
            )
            metric_docs.append(doc_text)
            metric_ids.append(f"metric_{metric_id}")
            metric_metadatas.append({
                "metric_id": metric_id,
                "sql_expression": m_data.sql_expression
            })

        if metric_docs:
            print(f"[ProfilingGraph] Đang nạp {len(metric_docs)} chỉ số nghiệp vụ...")
            metric_llama_docs = [
                Document(text=doc, id_=did, metadata=m)
                for doc, did, m in zip(metric_docs, metric_ids, metric_metadatas)
            ]
            storage_ctx = StorageContext.from_defaults(vector_store=self.metrics_store)
            self.metrics_index = VectorStoreIndex.from_documents(
                metric_llama_docs, storage_context=storage_ctx, embed_model=self.llama_embed
            )

        # 3. Lập chỉ mục Danh mục phân loại nếu có
        cat_docs = []
        cat_ids = []
        cat_metadatas = []

        # 3. Lập chỉ mục Danh mục phân loại động (Generic / Multi-Domain)
        cat_docs = []
        cat_ids = []
        cat_metadatas = []

        if distinct_categories:
            for key, val in distinct_categories.items():
                if isinstance(val, list):
                    for item in val[:50]:
                        col_clean = key.split(".")[-1]
                        doc_text = f"Giá trị phân loại chuẩn của cột '{col_clean}': {item}. {col_clean} = '{item}'"
                        cat_docs.append(doc_text)
                        safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', f"cat_{key}_{item}")[:60]
                        cat_ids.append(safe_id)
                        cat_metadatas.append({"category_type": col_clean, "value": item, "column": key})

        if cat_docs:
            print(f"[ProfilingGraph] Đang nạp {len(cat_docs)} danh mục phân loại thực tế...")
            cat_llama_docs = [
                Document(text=doc, id_=did, metadata=m)
                for doc, did, m in zip(cat_docs, cat_ids, cat_metadatas)
            ]
            storage_ctx = StorageContext.from_defaults(vector_store=self.cat_store)
            self.cat_index = VectorStoreIndex.from_documents(
                cat_llama_docs, storage_context=storage_ctx, embed_model=self.llama_embed
            )

        print(f"[ProfilingGraph] Hoàn thành lập chỉ mục cho domain '{self.domain_id}'!")

    def link_schema(self, user_query: str, top_k_cols: int = 6) -> SchemaContext:
        """
        Thực hiện Schema Linking kết hợp Glossary + Vector Retrieval + Graph Traversal + Steiner Tree Join Inference.
        Trả về đối tượng SchemaContext tối ưu cho LLM.
        """
        glossary_res = self.glossary.normalize(user_query)
        intent = glossary_res.intent

        matched_column_tuples: Set[Tuple[str, str]] = set() # (table_name, column_name)
        suggested_filters: List[str] = []
        suggested_metrics: List[MetricContext] = []
        needed_tables: Set[str] = set()

        default_table = next(iter(self.domain.tables.keys())) if self.domain.tables else "data"

        # 1. Trích xuất các entity từ Glossary và Schema CSDL
        if default_table in self.domain.tables:
            table_cols = self.domain.tables[default_table].columns
            num_cols = [c for c, p in table_cols.items() if any(nt in (p.data_type or "").upper() for nt in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "REAL"))]
            date_cols = [c for c, p in table_cols.items() if any(dt in (p.data_type or "").upper() or any(w in c.lower() for w in ("date", "time", "published", "created", "at", "year", "month")) for dt in ("DATE", "TIME", "TIMESTAMP"))]

            if getattr(intent, "min_price", None) is not None or getattr(intent, "max_price", None) is not None:
                price_col = next((c for c in num_cols if any(k in c.lower() for k in ("price", "amount", "revenue", "cost", "total", "fee", "val", "tien", "gia"))), num_cols[0] if num_cols else None)
                if price_col:
                    matched_column_tuples.add((default_table, price_col))
                    needed_tables.add(default_table)
                    if intent.min_price is not None and intent.max_price is not None:
                        suggested_filters.append(f"{price_col} BETWEEN {intent.min_price} AND {intent.max_price}")
                    elif intent.max_price is not None:
                        suggested_filters.append(f"{price_col} <= {intent.max_price}")
                    elif intent.min_price is not None:
                        suggested_filters.append(f"{price_col} >= {intent.min_price}")

            if getattr(intent, "min_area", None) is not None or getattr(intent, "max_area", None) is not None:
                area_col = next((c for c in num_cols if any(k in c.lower() for k in ("area", "size", "sqm", "m2", "dientich"))), None)
                if area_col:
                    matched_column_tuples.add((default_table, area_col))
                    needed_tables.add(default_table)
                    if intent.min_area is not None and intent.max_area is not None:
                        suggested_filters.append(f"{area_col} BETWEEN {intent.min_area} AND {intent.max_area}")
                    elif intent.max_area is not None:
                        suggested_filters.append(f"{area_col} <= {intent.max_area}")
                    elif intent.min_area is not None:
                        suggested_filters.append(f"{area_col} >= {intent.min_area}")

            if getattr(intent, "time_range", None) and date_cols:
                d_col = date_cols[0]
                matched_column_tuples.add((default_table, d_col))
                needed_tables.add(default_table)
                suggested_filters.append(f"{d_col} BETWEEN '{intent.time_range[1]}' AND '{intent.time_range[2]}'")

        # 2. Vector Search qua LlamaIndex (Qdrant) cho Cột
        try:
            if self.schema_index:
                retriever = self.schema_index.as_retriever(similarity_top_k=top_k_cols)
                nodes = retriever.retrieve(user_query)
                for node in nodes:
                    m = node.node.metadata
                    col = m.get("column_name")
                    tbl = m.get("table_name", default_table)
                    if col:
                        matched_column_tuples.add((tbl, col))
                        needed_tables.add(tbl)
        except Exception as e:
            print(f"[ProfilingGraph] Warning vector query schema: {e}")

        # 2.1 Keyword / Lexical matching fallback cho Columns
        user_query_clean = user_query.lower()
        for tbl_name, tbl_prof in self.domain.tables.items():
            for col_name, col_prof in tbl_prof.columns.items():
                col_terms = [col_name.lower(), col_name.replace("_", " ").lower()]
                if col_prof.vn_name:
                    col_terms.append(col_prof.vn_name.lower())
                col_terms.extend([s.lower() for s in (col_prof.synonyms or [])])
                if any(t in user_query_clean for t in col_terms if len(t) > 2):
                    matched_column_tuples.add((tbl_name, col_name))
                    needed_tables.add(tbl_name)

        # 3. Vector Search qua LlamaIndex (Qdrant) cho Chỉ số (Metrics)
        try:
            if self.metrics_index:
                retriever = self.metrics_index.as_retriever(similarity_top_k=2)
                nodes = retriever.retrieve(user_query)
                for node in nodes:
                    m_id = node.node.metadata.get("metric_id")
                    if m_id and m_id in self.domain.metrics:
                        m_prof = self.domain.metrics[m_id]
                        if not any(sm.name == m_id for sm in suggested_metrics):
                            suggested_metrics.append(MetricContext(
                                name=m_id,
                                vn_terms=m_prof.vn_terms or [],
                                sql_expression=m_prof.sql_expression,
                                description=m_prof.description or ""
                            ))
                            for dep_col in m_prof.depends_on_columns:
                                matched_column_tuples.add((default_table, dep_col))
                            for dep_tbl in m_prof.depends_on_tables:
                                needed_tables.add(dep_tbl)
        except Exception as e:
            pass

        # 3.1 Keyword matching fallback cho domain metrics (Zero-dependency matching)
        for m_id, m_prof in self.domain.metrics.items():
            all_terms = (m_prof.vn_terms or []) + (m_prof.en_terms or [])
            if any(term.lower() in user_query_clean for term in all_terms if term):
                if not any(sm.name == m_id for sm in suggested_metrics):
                    suggested_metrics.append(MetricContext(
                        name=m_id,
                        vn_terms=m_prof.vn_terms or [],
                        sql_expression=m_prof.sql_expression,
                        description=m_prof.description or ""
                    ))
                    for dep_col in m_prof.depends_on_columns:
                        matched_column_tuples.add((default_table, dep_col))
                    for dep_tbl in m_prof.depends_on_tables:
                        needed_tables.add(dep_tbl)

        # Đảm bảo toàn bộ các cột phụ thuộc của metrics gợi ý đều được liên kết vào schema
        for sm in suggested_metrics:
            if sm.name in self.domain.metrics:
                m_prof = self.domain.metrics[sm.name]
                for dep_col in m_prof.depends_on_columns:
                    matched_column_tuples.add((default_table, dep_col))
                for dep_tbl in m_prof.depends_on_tables:
                    needed_tables.add(dep_tbl)

        # 4. Giải thuật Steiner Tree suy luận phép nối JOIN giữa các bảng
        if not needed_tables:
            needed_tables.add(default_table)

        selected_tables, join_paths, cardinality_warnings = self.infer_join_paths(needed_tables)

        # 5. Đóng gói danh sách ColumnContext
        relevant_columns: List[ColumnContext] = []
        for tbl, col in sorted(list(matched_column_tuples)):
            if tbl in self.domain.tables and col in self.domain.tables[tbl].columns:
                p = self.domain.tables[tbl].columns[col]
                relevant_columns.append(ColumnContext(
                    name=col,
                    table_name=tbl,
                    data_type=p.data_type,
                    vn_name=p.vn_name or col,
                    description=p.description or "",
                    is_partition_or_dist=p.is_partition_or_dist,
                    sample_values=p.sample_values
                ))

        # 6. Tạo đoạn ngữ cảnh Markdown sẵn sàng cho LLM
        prompt_lines = []
        if len(selected_tables) <= 1:
            primary_tbl = selected_tables[0] if selected_tables else default_table
            prompt_lines.append(f"### SCHEMA LIÊN KẾT - TÊN BẢNG: `{primary_tbl}`")
            prompt_lines.append("| Cột | Kiểu | Tiếng Việt | Ghi chú & Giá trị mẫu |")
            prompt_lines.append("|---|---|---|---|")
            for rc in relevant_columns:
                samples_str = ", ".join(str(s) for s in rc.sample_values[:3])
                prompt_lines.append(f"| `{rc.name}` | `{rc.data_type}` | {rc.vn_name} | {rc.description} (Ví dụ: {samples_str}) |")
        else:
            prompt_lines.append(f"### SCHEMA LIÊN KẾT ĐA BẢNG ({', '.join(selected_tables)}):")
            prompt_lines.append("| Bảng | Cột | Kiểu | Tiếng Việt | Ghi chú & Giá trị mẫu |")
            prompt_lines.append("|---|---|---|---|---|")
            for rc in relevant_columns:
                samples_str = ", ".join(str(s) for s in rc.sample_values[:3])
                prompt_lines.append(f"| `{rc.table_name}` | `{rc.name}` | `{rc.data_type}` | {rc.vn_name} | {rc.description} (Ví dụ: {samples_str}) |")

            if join_paths:
                prompt_lines.append("\n### MỆNH ĐỀ LIÊN KẾT BẢNG (GỢI Ý JOIN - STEINER TREE):")
                for jp in join_paths:
                    prompt_lines.append(f"- `{jp}`")

            if cardinality_warnings:
                prompt_lines.append("\n### CẢNH BÁO TOÀN VẸN DỮ LIỆU (FAN-TRAP GUARDRAIL):")
                for cw in cardinality_warnings:
                    prompt_lines.append(f"- ⚠️ {cw}")

        if suggested_filters:
            prompt_lines.append("\n### CÁC MỆNH ĐỀ ĐIỀU KIỆN ĐÃ ĐƯỢC CHUẨN HÓA (Gợi ý WHERE):")
            for sf in suggested_filters:
                prompt_lines.append(f"- `{sf}`")

        if suggested_metrics:
            prompt_lines.append("\n### CHỈ SỐ NGHIỆP VỤ ĐƯỢC GỢI Ý (SELECT Expression):")
            for sm in suggested_metrics:
                prompt_lines.append(f"- **{sm.name}**: `{sm.sql_expression}` ({sm.description})")

        if intent.order_by:
            prompt_lines.append(f"\n### GỢI Ý SẮP XẾP: `ORDER BY {intent.order_by}`")

        if intent.limit:
            prompt_lines.append(f"\n### GỢI Ý GIỚI HẠN: `LIMIT {intent.limit}`")

        partition_hint = None
        for t_name, tbl in self.domain.tables.items():
            if getattr(tbl, "partition_key", None):
                partition_hint = (
                    f"Bảng `{t_name}` được PARTITION theo cột `{tbl.partition_key}`. "
                    f"Khi người dùng hỏi theo mốc thời gian, hãy thêm điều kiện `{tbl.partition_key}` để tối ưu hiệu năng quét."
                )
                prompt_lines.append(f"\n> **LƯU Ý HIỆU NĂNG TỐI ƯU TRUY VẤN:** {partition_hint}")
                break

        prompt_context = "\n".join(prompt_lines)

        return SchemaContext(
            selected_tables=selected_tables,
            table_name=selected_tables[0] if selected_tables else default_table,
            join_paths=join_paths,
            cardinality_warnings=cardinality_warnings,
            relevant_columns=relevant_columns,
            suggested_filters=suggested_filters,
            suggested_metrics=suggested_metrics,
            order_by_clause=intent.order_by,
            limit_clause=f"LIMIT {intent.limit}" if intent.limit else None,
            partition_pruning_hint=partition_hint,
            prompt_context=prompt_context
        )
