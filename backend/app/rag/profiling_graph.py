"""
Bilingual Data Profiling Graph (Đồ thị hồ sơ dữ liệu song ngữ & Schema Linking Đa Domain).
Sử dụng BAAI/bge-m3 + ChromaDB + NetworkX để liên kết ngữ nghĩa câu hỏi người dùng
với CSDL Apache Doris, hỗ trợ đa bảng và tự động suy luận phép nối JOIN qua thuật toán Minimum Steiner Tree.
"""

import os
import sys
import re
from typing import Dict, Any, List, Set, Optional, Tuple
import networkx as nx
import chromadb
from chromadb.config import Settings

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
    Đồ thị hồ sơ dữ liệu song ngữ kết hợp Vector Store ChromaDB và Graph Network:
    1. Quản lý biểu đồ quan hệ giữa Bảng, Cột, Danh mục phân loại và Chỉ số nghiệp vụ.
    2. Nạp cấu hình động theo Domain (BĐS, E-commerce, Y tế...).
    3. Tự động suy luận đường dẫn JOIN tối ưu qua giải thuật Minimum Steiner Tree trên NetworkX.
    4. Cung cấp cơ chế phòng vệ Fan-Trap khi thực hiện JOIN đa bảng.
    """

    def __init__(
        self,
        domain_id: Optional[str] = None,
        domain_config: Optional[DomainConfig] = None,
        chroma_dir: Optional[str] = None,
        embedding_function: Optional[Any] = None
    ):
        self.chroma_dir = chroma_dir or settings.CHROMA_PERSIST_DIR
        os.makedirs(self.chroma_dir, exist_ok=True)

        self.domain_manager = DomainManager()
        if domain_config:
            self.domain = domain_config
        elif domain_id:
            found = self.domain_manager.get_domain(domain_id)
            if not found:
                raise ValueError(f"Không tìm thấy domain_id: {domain_id}")
            self.domain = found
        else:
            self.domain = self.domain_manager.get_active_domain_config()

        self.domain_id = self.domain.domain_id
        self.glossary = VietnameseBusinessGlossary(domain_manager=self.domain_manager)
        self.embedding_fn = embedding_function or BGEM3EmbeddingFunction()

        # Khởi tạo persistent Chroma client
        self.client = chromadb.PersistentClient(path=self.chroma_dir)

        # In-memory Knowledge Graph cho Columns & Tables
        self.graph = nx.DiGraph()
        # Đồ thị vô hướng giữa các bảng để giải thuật Steiner Tree
        self.table_graph = nx.Graph()

        # Collections
        self.col_schema = None
        self.col_categories = None
        self.col_metrics = None

        self._init_collections()
        self._build_in_memory_graph()

    def _init_collections(self):
        """Khởi tạo hoặc lấy các collection trong ChromaDB phân tách theo domain."""
        prefix = "real_estate" if self.domain_id == "real_estate" else self.domain_id

        self.col_schema = self.client.get_or_create_collection(
            name=f"{prefix}_schema_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": f"Hồ sơ ngữ nghĩa cột của domain {self.domain_id}"}
        )

        self.col_categories = self.client.get_or_create_collection(
            name=f"{prefix}_category_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": f"Danh mục phân loại thực tế của domain {self.domain_id}"}
        )

        self.col_metrics = self.client.get_or_create_collection(
            name=f"{prefix}_metrics_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": f"Các chỉ số phân tích của domain {self.domain_id}"}
        )

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

        # 3. Quan hệ thứ bậc nội tại bảng (nếu là real_estate)
        if self.domain_id == "real_estate":
            self.graph.add_edge("Col:district_name", "Col:province_name", relation="CHILD_OF")
            self.graph.add_edge("Col:ward_name", "Col:district_name", relation="CHILD_OF")
            self.graph.add_edge("Col:street_name", "Col:district_name", relation="LOCATED_IN")
            self.graph.add_edge("Col:property_type_name", "Col:bedroom_count", relation="RELEVANT_FOR_APARTMENT")
            self.graph.add_edge("Col:property_type_name", "Col:bathroom_count", relation="RELEVANT_FOR_APARTMENT")
            self.graph.add_edge("Col:property_type_name", "Col:balcony_direction", relation="RELEVANT_FOR_APARTMENT")
            self.graph.add_edge("Col:property_type_name", "Col:frontage_width", relation="RELEVANT_FOR_LAND_HOUSE")
            self.graph.add_edge("Col:property_type_name", "Col:road_width", relation="RELEVANT_FOR_LAND_HOUSE")
            self.graph.add_edge("Col:property_type_name", "Col:floor_count", relation="RELEVANT_FOR_HOUSE")

        # 4. Thêm Chỉ số nghiệp vụ (Metrics)
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
            default_t = next(iter(self.domain.tables.keys())) if self.domain.tables else "real_estate_listings"
            return [default_t], [], []

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
        Lập chỉ mục toàn bộ Metadata, Danh mục và Chỉ số của Domain vào ChromaDB.
        """
        existing_schema_count = self.col_schema.count()
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
            self.col_schema.add(documents=schema_docs, ids=schema_ids, metadatas=schema_metadatas)

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
            self.col_metrics.add(documents=metric_docs, ids=metric_ids, metadatas=metric_metadatas)

        # 3. Lập chỉ mục Danh mục phân loại nếu có
        cat_docs = []
        cat_ids = []
        cat_metadatas = []

        if self.domain_id == "real_estate":
            prop_types = ["Căn hộ chung cư", "Nhà", "Đất", "Biệt thự/Nhà liền kề", "Shophouse"]
            for pt in prop_types:
                cat_docs.append(f"Loại hình bất động sản chuẩn trong CSDL: {pt}. property_type_name = '{pt}'")
                cat_ids.append(f"prop_{pt}")
                cat_metadatas.append({"category_type": "property_type", "value": pt})

            if distinct_categories:
                provinces = distinct_categories.get("provinces", [])
                for p in provinces:
                    cat_docs.append(f"Tỉnh / Thành phố: {p}. province_name = '{p}'")
                    cat_ids.append(f"prov_{p}")
                    cat_metadatas.append({"category_type": "province", "value": p})

                dist_map = distinct_categories.get("district_to_province", {})
                for d, p in dist_map.items():
                    cat_docs.append(f"Quận / Huyện: {d} thuộc Tỉnh / Thành phố {p}. district_name = '{d}' AND province_name = '{p}'")
                    cat_ids.append(f"dist_{d}_{p}")
                    cat_metadatas.append({"category_type": "district", "value": d, "parent_province": p})

                directions = distinct_categories.get("directions", [])
                for dir_val in directions:
                    cat_docs.append(f"Hướng nhà phong thủy: {dir_val}. house_direction LIKE '%{dir_val}%'")
                    cat_ids.append(f"dir_{dir_val}")
                    cat_metadatas.append({"category_type": "direction", "value": dir_val})

        if cat_docs:
            print(f"[ProfilingGraph] Đang nạp {len(cat_docs)} danh mục phân loại thực tế...")
            batch_size = 200
            for i in range(0, len(cat_docs), batch_size):
                self.col_categories.add(
                    documents=cat_docs[i:i+batch_size],
                    ids=cat_ids[i:i+batch_size],
                    metadatas=cat_metadatas[i:i+batch_size]
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

        default_table = next(iter(self.domain.tables.keys())) if self.domain.tables else "real_estate_listings"

        # 1. Trích xuất các entity từ Glossary (Domain BĐS)
        if self.domain_id == "real_estate":
            needed_tables.add("real_estate_listings")
            if intent.property_type:
                matched_column_tuples.add(("real_estate_listings", "property_type_name"))
                suggested_filters.append(f"property_type_name = '{intent.property_type}'")
                if intent.property_type == "Căn hộ chung cư":
                    matched_column_tuples.add(("real_estate_listings", "bedroom_count"))
                    matched_column_tuples.add(("real_estate_listings", "bathroom_count"))
                elif intent.property_type in ["Nhà", "Đất"]:
                    matched_column_tuples.add(("real_estate_listings", "area"))
                    matched_column_tuples.add(("real_estate_listings", "road_width"))
                    matched_column_tuples.add(("real_estate_listings", "frontage_width"))

            if intent.province:
                matched_column_tuples.add(("real_estate_listings", "province_name"))
                suggested_filters.append(f"province_name = '{intent.province}'")

            if intent.district:
                matched_column_tuples.add(("real_estate_listings", "district_name"))
                suggested_filters.append(f"district_name = '{intent.district}'")
                matched_column_tuples.add(("real_estate_listings", "province_name"))

            if intent.bedroom_count is not None:
                matched_column_tuples.add(("real_estate_listings", "bedroom_count"))
                suggested_filters.append(f"bedroom_count = {intent.bedroom_count}")

            if intent.bathroom_count is not None:
                matched_column_tuples.add(("real_estate_listings", "bathroom_count"))
                suggested_filters.append(f"bathroom_count = {intent.bathroom_count}")

            if intent.direction:
                matched_column_tuples.add(("real_estate_listings", "house_direction"))
                suggested_filters.append(f"house_direction LIKE '%{intent.direction}%'")

            if intent.min_price is not None and intent.max_price is not None:
                matched_column_tuples.add(("real_estate_listings", "price"))
                suggested_filters.append(f"price BETWEEN {intent.min_price} AND {intent.max_price}")
            elif intent.max_price is not None:
                matched_column_tuples.add(("real_estate_listings", "price"))
                suggested_filters.append(f"price <= {intent.max_price}")
            elif intent.min_price is not None:
                matched_column_tuples.add(("real_estate_listings", "price"))
                suggested_filters.append(f"price >= {intent.min_price}")

            if intent.min_area is not None and intent.max_area is not None:
                matched_column_tuples.add(("real_estate_listings", "area"))
                suggested_filters.append(f"area BETWEEN {intent.min_area} AND {intent.max_area}")
            elif intent.max_area is not None:
                matched_column_tuples.add(("real_estate_listings", "area"))
                suggested_filters.append(f"area <= {intent.max_area}")
            elif intent.min_area is not None:
                matched_column_tuples.add(("real_estate_listings", "area"))
                suggested_filters.append(f"area >= {intent.min_area}")

            if intent.time_range:
                matched_column_tuples.add(("real_estate_listings", "published_at"))
                suggested_filters.append(f"published_at BETWEEN '{intent.time_range[1]}' AND '{intent.time_range[2]}'")

            # Luôn bảo đảm có partition key và price cho BĐS
            matched_column_tuples.add(("real_estate_listings", "published_at"))
            matched_column_tuples.add(("real_estate_listings", "price"))

        # 2. Vector Search qua ChromaDB cho Cột
        try:
            schema_results = self.col_schema.query(query_texts=[user_query], n_results=top_k_cols)
            if schema_results and schema_results.get("metadatas"):
                for m in schema_results["metadatas"][0]:
                    col = m["column_name"]
                    tbl = m.get("table_name", default_table)
                    matched_column_tuples.add((tbl, col))
                    needed_tables.add(tbl)
        except Exception as e:
            print(f"[ProfilingGraph] Warning vector query schema: {e}")

        # 3. Vector Search qua ChromaDB cho Chỉ số (Metrics)
        try:
            metric_results = self.col_metrics.query(query_texts=[user_query], n_results=2)
            if metric_results and metric_results.get("metadatas"):
                for m in metric_results["metadatas"][0]:
                    m_id = m["metric_id"]
                    if m_id in self.domain.metrics:
                        m_prof = self.domain.metrics[m_id]
                        suggested_metrics.append(MetricContext(
                            name=m_id,
                            vn_terms=m_prof.vn_terms,
                            sql_expression=m_prof.sql_expression,
                            description=m_prof.description
                        ))
                        for dep_col in m_prof.depends_on_columns:
                            matched_column_tuples.add((default_table, dep_col))
                        for dep_tbl in m_prof.depends_on_tables:
                            needed_tables.add(dep_tbl)
        except Exception as e:
            pass

        # 3.1 Keyword matching fallback cho domain metrics (Zero-dependency matching)
        user_query_clean = user_query.lower()
        for m_id, m_prof in self.domain.metrics.items():
            all_terms = (m_prof.vn_terms or []) + (m_prof.en_terms or [])
            if any(term.lower() in user_query_clean for term in all_terms):
                if not any(sm.name == m_id for sm in suggested_metrics):
                    suggested_metrics.append(MetricContext(
                        name=m_id,
                        vn_terms=m_prof.vn_terms,
                        sql_expression=m_prof.sql_expression,
                        description=m_prof.description
                    ))
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
                    vn_name=p.vn_name,
                    description=p.description,
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
        if self.domain_id == "real_estate":
            partition_hint = (
                "Bảng được PARTITION BY RANGE(published_at) theo tháng. "
                "Nếu người dùng hỏi mốc thời gian (tháng trước, quý này...), luôn thêm điều kiện published_at BETWEEN ... để tối ưu số tablet quét."
            )
            prompt_lines.append(f"\n> **LƯU Ý HIỆU NĂNG TỐI ƯU DORIS:** {partition_hint}")

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
