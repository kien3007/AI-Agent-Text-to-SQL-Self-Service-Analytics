"""
Bilingual Data Profiling Graph (Đồ thị hồ sơ dữ liệu song ngữ & Schema Linking).
Sử dụng BAAI/bge-m3 + ChromaDB + NetworkX để liên kết ngữ nghĩa câu hỏi người dùng
với CSDL Apache Doris real_estate_listings.
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
from app.rag.embeddings import BGEM3EmbeddingFunction
from app.rag.bilingual_dictionary import COLUMN_PROFILES, BUSINESS_METRICS, PRICE_SEGMENTS
from app.schemas.schema_context import SchemaContext, ColumnContext, MetricContext

class BilingualDataProfilingGraph:
    """
    Đồ thị hồ sơ dữ liệu song ngữ kết hợp Vector Store ChromaDB và Graph Network:
    1. Quản lý biểu đồ quan hệ giữa Bảng, Cột, Danh mục phân loại và Chỉ số nghiệp vụ.
    2. Chỉ mục ngữ nghĩa đa ngôn ngữ (Tiếng Việt <-> English <-> SQL) với bge-m3.
    3. Thực hiện Schema Linking thông minh (giảm 80% token DDL dư thừa khi cấp cho LLM).
    """

    def __init__(
        self,
        chroma_dir: Optional[str] = None,
        embedding_function: Optional[Any] = None
    ):
        base_dir = os.getcwd()
        self.chroma_dir = chroma_dir or os.path.join(base_dir, "data", "chroma_db")
        os.makedirs(self.chroma_dir, exist_ok=True)

        self.glossary = VietnameseBusinessGlossary()
        self.embedding_fn = embedding_function or BGEM3EmbeddingFunction()
        
        # Khởi tạo persistent Chroma client
        self.client = chromadb.PersistentClient(path=self.chroma_dir)
        
        # In-memory Knowledge Graph
        self.graph = nx.DiGraph()

        # Collections
        self.col_schema = None
        self.col_categories = None
        self.col_metrics = None

        self._init_collections()
        self._build_in_memory_graph()

    def _init_collections(self):
        """Khởi tạo hoặc lấy các collection trong ChromaDB."""
        self.col_schema = self.client.get_or_create_collection(
            name="real_estate_schema_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": "Hồ sơ ngữ nghĩa 19 cột của bảng real_estate_listings"}
        )

        self.col_categories = self.client.get_or_create_collection(
            name="real_estate_category_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": "Danh mục phân loại thực tế: Tỉnh thành, Quận huyện, Loại hình, Hướng nhà"}
        )

        self.col_metrics = self.client.get_or_create_collection(
            name="real_estate_metrics_profiles",
            embedding_function=self.embedding_fn,
            metadata={"description": "Các chỉ số phân tích BĐS và phân khúc giá"}
        )

    def _build_in_memory_graph(self):
        """Xây dựng đồ thị tri thức quan hệ Schema & Domain trong NetworkX."""
        self.graph.clear()
        
        # 1. Node Bảng
        table_node = "Table:real_estate_listings"
        self.graph.add_node(table_node, type="table", label="real_estate_listings")

        # 2. Nodes Cột
        for col_name, prof in COLUMN_PROFILES.items():
            col_node = f"Col:{col_name}"
            self.graph.add_node(
                col_node,
                type="column",
                name=col_name,
                data_type=prof["data_type"],
                vn_name=prof["vn_name"],
                description=prof["description"],
                is_partition=prof.get("is_partition_or_dist", False)
            )
            self.graph.add_edge(table_node, col_node, relation="HAS_COLUMN")

        # 3. Quan hệ thứ bậc địa lý (District -> Province)
        self.graph.add_edge("Col:district_name", "Col:province_name", relation="CHILD_OF")
        self.graph.add_edge("Col:ward_name", "Col:district_name", relation="CHILD_OF")
        self.graph.add_edge("Col:street_name", "Col:district_name", relation="LOCATED_IN")

        # 4. Quan hệ thuộc tính theo Loại hình BĐS
        # Chung cư thường gắn liền với số PN, WC, ban công
        self.graph.add_edge("Col:property_type_name", "Col:bedroom_count", relation="RELEVANT_FOR_APARTMENT")
        self.graph.add_edge("Col:property_type_name", "Col:bathroom_count", relation="RELEVANT_FOR_APARTMENT")
        self.graph.add_edge("Col:property_type_name", "Col:balcony_direction", relation="RELEVANT_FOR_APARTMENT")
        # Nhà phố / Đất gắn liền với mặt tiền, độ rộng hẻm, chiều sâu, số tầng
        self.graph.add_edge("Col:property_type_name", "Col:frontage_width", relation="RELEVANT_FOR_LAND_HOUSE")
        self.graph.add_edge("Col:property_type_name", "Col:road_width", relation="RELEVANT_FOR_LAND_HOUSE")
        self.graph.add_edge("Col:property_type_name", "Col:floor_count", relation="RELEVANT_FOR_HOUSE")

        # 5. Quan hệ Chỉ số nghiệp vụ -> Cột cần thiết
        for metric_id, m_data in BUSINESS_METRICS.items():
            m_node = f"Metric:{metric_id}"
            self.graph.add_node(
                m_node,
                type="metric",
                id=metric_id,
                sql_expression=m_data["sql_expression"],
                description=m_data["description"]
            )
            # Link metric với các cột phụ thuộc
            if "price" in m_data["sql_expression"]:
                self.graph.add_edge(m_node, "Col:price", relation="DEPENDS_ON")
            if "area" in m_data["sql_expression"]:
                self.graph.add_edge(m_node, "Col:area", relation="DEPENDS_ON")

    def index_all(self, distinct_categories: Optional[Dict[str, Any]] = None, force: bool = False):
        """
        Lập chỉ mục toàn bộ Metadata, Danh mục và Chỉ số vào ChromaDB.
        Chạy 1 lần (Offline Indexing) để lưu persistent trên ổ đĩa.
        """
        existing_schema_count = self.col_schema.count()
        if existing_schema_count > 0 and not force:
            print(f"[ProfilingGraph] Index đã tồn tại ({existing_schema_count} columns). Bỏ qua lập chỉ mục lại.")
            return

        print("[ProfilingGraph] Bắt đầu lập chỉ mục ngữ nghĩa với bge-m3...")

        # 1. Lập chỉ mục Schema Profiles
        schema_docs = []
        schema_ids = []
        schema_metadatas = []
        for col_name, prof in COLUMN_PROFILES.items():
            doc_text = (
                f"Tên cột CSDL: {col_name}\n"
                f"Tên Tiếng Việt: {prof['vn_name']}\n"
                f"Tên Tiếng Anh: {prof['en_name']}\n"
                f"Kiểu dữ liệu: {prof['data_type']}\n"
                f"Mô tả nghiệp vụ: {prof['description']}\n"
                f"Từ đồng nghĩa / Tìm kiếm: {', '.join(prof['synonyms'])}\n"
                f"Ví dụ giá trị mẫu: {', '.join(str(v) for v in prof.get('sample_values', []))}"
            )
            schema_docs.append(doc_text)
            schema_ids.append(f"col_{col_name}")
            schema_metadatas.append({
                "column_name": col_name,
                "data_type": prof["data_type"],
                "vn_name": prof["vn_name"],
                "is_partition": prof.get("is_partition_or_dist", False)
            })

        print(f"[ProfilingGraph] Đang nạp {len(schema_docs)} cột vào schema collection...")
        self.col_schema.add(
            documents=schema_docs,
            ids=schema_ids,
            metadatas=schema_metadatas
        )

        # 2. Lập chỉ mục Chỉ số nghiệp vụ
        metric_docs = []
        metric_ids = []
        metric_metadatas = []
        for metric_id, m_data in BUSINESS_METRICS.items():
            doc_text = (
                f"Chỉ số phân tích: {metric_id}\n"
                f"Thuật ngữ Tiếng Việt: {', '.join(m_data['vn_terms'])}\n"
                f"Thuật ngữ Tiếng Anh: {', '.join(m_data['en_terms'])}\n"
                f"Công thức SQL: {m_data['sql_expression']}\n"
                f"Ý nghĩa: {m_data['description']}"
            )
            metric_docs.append(doc_text)
            metric_ids.append(f"metric_{metric_id}")
            metric_metadatas.append({
                "metric_id": metric_id,
                "sql_expression": m_data["sql_expression"]
            })

        print(f"[ProfilingGraph] Đang nạp {len(metric_docs)} chỉ số nghiệp vụ...")
        self.col_metrics.add(
            documents=metric_docs,
            ids=metric_ids,
            metadatas=metric_metadatas
        )

        # 3. Lập chỉ mục Danh mục phân loại (Categories)
        cat_docs = []
        cat_ids = []
        cat_metadatas = []

        # A. Loại hình BĐS
        prop_types = ["Căn hộ chung cư", "Nhà", "Đất", "Biệt thự/Nhà liền kề", "Shophouse"]
        for pt in prop_types:
            doc_text = f"Loại hình bất động sản chuẩn trong CSDL: {pt}. property_type_name = '{pt}'"
            cat_docs.append(doc_text)
            cat_ids.append(f"prop_{pt}")
            cat_metadatas.append({"category_type": "property_type", "value": pt})

        # B. Tỉnh thành & Quận huyện (Nếu có từ Doris, nạp toàn bộ)
        if distinct_categories:
            provinces = distinct_categories.get("provinces", [])
            for p in provinces:
                doc_text = f"Tỉnh / Thành phố: {p}. province_name = '{p}'"
                cat_docs.append(doc_text)
                cat_ids.append(f"prov_{p}")
                cat_metadatas.append({"category_type": "province", "value": p})

            dist_map = distinct_categories.get("district_to_province", {})
            for d, p in dist_map.items():
                doc_text = f"Quận / Huyện: {d} thuộc Tỉnh / Thành phố {p}. district_name = '{d}' AND province_name = '{p}'"
                cat_docs.append(doc_text)
                cat_ids.append(f"dist_{d}_{p}")
                cat_metadatas.append({"category_type": "district", "value": d, "parent_province": p})

            # Hướng nhà
            directions = distinct_categories.get("directions", [])
            for dir_val in directions:
                doc_text = f"Hướng nhà phong thủy: {dir_val}. house_direction LIKE '%{dir_val}%'"
                cat_docs.append(doc_text)
                cat_ids.append(f"dir_{dir_val}")
                cat_metadatas.append({"category_type": "direction", "value": dir_val})

        print(f"[ProfilingGraph] Đang nạp {len(cat_docs)} danh mục phân loại thực tế...")
        # Nạp theo batch 200 để tối ưu bộ nhớ
        batch_size = 200
        for i in range(0, len(cat_docs), batch_size):
            self.col_categories.add(
                documents=cat_docs[i:i+batch_size],
                ids=cat_ids[i:i+batch_size],
                metadatas=cat_metadatas[i:i+batch_size]
            )

        print("[ProfilingGraph] Hoàn thành lập chỉ mục toàn diện vào ChromaDB!")

    def link_schema(self, user_query: str, top_k_cols: int = 6) -> SchemaContext:
        """
        Thực hiện Schema Linking kết hợp Glossary + Vector Retrieval + Graph Traversal.
        Trả về đối tượng SchemaContext tối ưu cho LLM.
        """
        # Bước 1: Tiền xử lý với VietnameseBusinessGlossary
        glossary_res = self.glossary.normalize(user_query)
        intent = glossary_res.intent

        matched_column_names: Set[str] = set()
        suggested_filters: List[str] = []
        suggested_metrics: List[MetricContext] = []

        # Ánh xạ từ các entity đã trích xuất chắc chắn từ Glossary
        if intent.property_type:
            matched_column_names.add("property_type_name")
            suggested_filters.append(f"property_type_name = '{intent.property_type}'")
            # Graph traversal: Căn hộ cần thêm phòng ngủ, phòng vệ sinh; Đất cần diện tích
            if intent.property_type == "Căn hộ chung cư":
                matched_column_names.update(["bedroom_count", "bathroom_count"])
            elif intent.property_type in ["Nhà", "Đất"]:
                matched_column_names.update(["area", "road_width", "frontage_width"])

        if intent.province:
            matched_column_names.add("province_name")
            suggested_filters.append(f"province_name = '{intent.province}'")

        if intent.district:
            matched_column_names.add("district_name")
            suggested_filters.append(f"district_name = '{intent.district}'")
            # Graph traversal: nếu có district thì bắt buộc có province_name
            matched_column_names.add("province_name")

        if intent.bedroom_count is not None:
            matched_column_names.add("bedroom_count")
            suggested_filters.append(f"bedroom_count = {intent.bedroom_count}")

        if intent.bathroom_count is not None:
            matched_column_names.add("bathroom_count")
            suggested_filters.append(f"bathroom_count = {intent.bathroom_count}")

        if intent.direction:
            matched_column_names.add("house_direction")
            suggested_filters.append(f"house_direction LIKE '%{intent.direction}%'")

        if intent.min_price is not None and intent.max_price is not None:
            matched_column_names.add("price")
            suggested_filters.append(f"price BETWEEN {intent.min_price} AND {intent.max_price}")
        elif intent.max_price is not None:
            matched_column_names.add("price")
            suggested_filters.append(f"price <= {intent.max_price}")
        elif intent.min_price is not None:
            matched_column_names.add("price")
            suggested_filters.append(f"price >= {intent.min_price}")

        if intent.min_area is not None and intent.max_area is not None:
            matched_column_names.add("area")
            suggested_filters.append(f"area BETWEEN {intent.min_area} AND {intent.max_area}")
        elif intent.max_area is not None:
            matched_column_names.add("area")
            suggested_filters.append(f"area <= {intent.max_area}")
        elif intent.min_area is not None:
            matched_column_names.add("area")
            suggested_filters.append(f"area >= {intent.min_area}")

        if intent.time_range:
            matched_column_names.add("published_at")
            suggested_filters.append(f"published_at BETWEEN '{intent.time_range[1]}' AND '{intent.time_range[2]}'")

        # Bước 2: Tìm kiếm ngữ nghĩa trong ChromaDB cho Cột và Chỉ số
        # A. Tìm kiếm cột liên quan (nếu chưa đủ)
        try:
            schema_results = self.col_schema.query(
                query_texts=[user_query],
                n_results=top_k_cols
            )
            if schema_results and schema_results.get("metadatas"):
                for m in schema_results["metadatas"][0]:
                    col = m["column_name"]
                    matched_column_names.add(col)
        except Exception as e:
            print(f"[ProfilingGraph] Warning vector query schema: {e}")

        # B. Tìm kiếm Chỉ số nghiệp vụ (Metrics)
        try:
            metric_results = self.col_metrics.query(
                query_texts=[user_query],
                n_results=2
            )
            if metric_results and metric_results.get("metadatas"):
                for m in metric_results["metadatas"][0]:
                    m_id = m["metric_id"]
                    if m_id in BUSINESS_METRICS:
                        b_info = BUSINESS_METRICS[m_id]
                        # Kiểm tra xem từ khóa có thực sự xuất hiện hoặc có độ tương đồng cao
                        suggested_metrics.append(MetricContext(
                            name=m_id,
                            vn_terms=b_info["vn_terms"],
                            sql_expression=b_info["sql_expression"],
                            description=b_info["description"]
                        ))
                        # Graph traversal: bổ sung các cột phụ thuộc của metric
                        m_node = f"Metric:{m_id}"
                        if self.graph.has_node(m_node):
                            for neighbor in self.graph.neighbors(m_node):
                                if neighbor.startswith("Col:"):
                                    matched_column_names.add(neighbor.replace("Col:", ""))
        except Exception as e:
            print(f"[ProfilingGraph] Warning vector query metrics: {e}")

        # Luôn luôn đảm bảo có published_at (Partition Key) và price (định giá)
        matched_column_names.add("published_at")
        matched_column_names.add("price")

        # Bước 3: Đóng gói ColumnContext từ COLUMN_PROFILES
        relevant_columns: List[ColumnContext] = []
        for c in sorted(list(matched_column_names)):
            if c in COLUMN_PROFILES:
                p = COLUMN_PROFILES[c]
                relevant_columns.append(ColumnContext(
                    name=c,
                    data_type=p["data_type"],
                    vn_name=p["vn_name"],
                    description=p["description"],
                    is_partition_or_dist=p.get("is_partition_or_dist", False),
                    sample_values=p.get("sample_values", [])
                ))

        # Bước 4: Tạo Prompt Context Markdown sẵn sàng cho LLM
        prompt_lines = [
            "### SCHEMA LIÊN KẾT (Bảng: real_estate_listings):",
            "| Cột | Kiểu | Tiếng Việt | Ghi chú & Giá trị mẫu |",
            "|---|---|---|---|"
        ]
        for rc in relevant_columns:
            samples_str = ", ".join(str(s) for s in rc.sample_values[:3])
            prompt_lines.append(f"| `{rc.name}` | `{rc.data_type}` | {rc.vn_name} | {rc.description} (Ví dụ: {samples_str}) |")

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

        prompt_lines.append(
            "\n> **LƯU Ý HIỆU NĂNG TỐI ƯU DORIS:** Bảng phân vùng `PARTITION BY RANGE(published_at)`. "
            "Nếu người dùng hỏi mốc thời gian (tháng trước, quý này...), luôn thêm điều kiện `published_at BETWEEN ...`."
        )

        prompt_context = "\n".join(prompt_lines)

        return SchemaContext(
            table_name="real_estate_listings",
            relevant_columns=relevant_columns,
            suggested_filters=suggested_filters,
            suggested_metrics=suggested_metrics,
            order_by_clause=intent.order_by,
            limit_clause=f"LIMIT {intent.limit}" if intent.limit else None,
            prompt_context=prompt_context
        )
