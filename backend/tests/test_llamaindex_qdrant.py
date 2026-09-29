"""
Test Suite for LlamaIndex + Qdrant On-prem Integration:
1. LlamaIndex BGEM3 BaseEmbedding Adapter
2. Qdrant Vector Store Provider (Server fallback & in-memory)
3. BilingualDataProfilingGraph Schema Linking via VectorStoreIndex
4. LongTermMemory Dynamic Few-Shot Retrieval via Qdrant Cosine Similarity
"""

import unittest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.rag.llamaindex_embedding import LlamaIndexBGEM3Embedding
from app.rag.qdrant_provider import get_qdrant_client, ensure_collection_exists, get_qdrant_vector_store
from app.rag.profiling_graph import BilingualDataProfilingGraph
from app.agent.memory.three_tier_memory import LongTermMemory, ThreeTierMemory


class TestLlamaIndexQdrantIntegration(unittest.TestCase):
    """Kiểm thử tích hợp toàn diện LlamaIndex và Qdrant."""

    @classmethod
    def setUpClass(cls):
        cls.qdrant_client = get_qdrant_client(in_memory=True)
        cls.embed_model = LlamaIndexBGEM3Embedding()

    def test_01_llamaindex_embedding_adapter(self):
        """Kiểm tra adapter BaseEmbedding sinh vector chuẩn 1024 chiều."""
        query = "Thống kê giá chung cư Cầu Giấy"
        query_emb = self.embed_model.get_query_embedding(query)
        self.assertIsInstance(query_emb, list)
        self.assertEqual(len(query_emb), 1024)

        text = "Bảng real_estate_listings chứa cột price và area"
        text_emb = self.embed_model.get_text_embedding(text)
        self.assertIsInstance(text_emb, list)
        self.assertEqual(len(text_emb), 1024)

    def test_02_qdrant_provider_in_memory(self):
        """Kiểm tra Qdrant Provider tạo collection và vector store thành công."""
        col_name = "test_col_prov"
        ensure_collection_exists(self.qdrant_client, col_name, vector_dim=1024)
        info = self.qdrant_client.get_collection(col_name)
        self.assertIsNotNone(info)
        self.assertEqual(info.points_count, 0)

        store = get_qdrant_vector_store(self.qdrant_client, col_name)
        self.assertIsNotNone(store)

    def test_03_profiling_graph_with_llamaindex_qdrant(self):
        """Kiểm tra BilingualDataProfilingGraph lập chỉ mục và liên kết schema qua LlamaIndex + Qdrant."""
        graph = BilingualDataProfilingGraph(
            domain_id="real_estate",
            vector_backend="qdrant",
            qdrant_client=self.qdrant_client,
            in_memory=True
        )
        # Lập chỉ mục
        graph.index_all(force=True)

        # Kiểm tra collection có dữ liệu
        schema_count = self.qdrant_client.get_collection(graph.schema_store.collection_name).points_count
        self.assertGreater(schema_count, 0)

        # Schema Linking câu hỏi tiếng Việt
        query = "Cho tôi xem căn hộ 2 phòng ngủ giá dưới 5 tỷ tại Cầu Giấy"
        ctx = graph.link_schema(query)

        col_names = [c.name for c in ctx.relevant_columns]
        self.assertIn("property_type_name", col_names)
        self.assertIn("district_name", col_names)
        self.assertIn("bedroom_count", col_names)
        self.assertIn("price", col_names)
        self.assertTrue(len(ctx.suggested_filters) > 0)

    def test_04_long_term_memory_dynamic_few_shots_qdrant(self):
        """Kiểm tra LongTermMemory sử dụng LlamaIndex + Qdrant cosine similarity để tìm few-shots."""
        memory = LongTermMemory(
            seed_defaults=True,
            vector_backend="qdrant",
            qdrant_client=self.qdrant_client,
            in_memory=True
        )

        # Lưu thêm 1 plan mẫu mới
        memory.save_plan(
            user_query="Tìm biệt thự liền kề diện tích trên 200m2 tại Tây Hồ",
            domain_id="real_estate",
            sql="SELECT listing_title, price, area FROM real_estate_listings WHERE district_name = 'Tây Hồ' AND property_type_name = 'Biệt thự/Nhà liền kề' AND area >= 200 LIMIT 10;",
            is_successful=True,
            tables_used=["real_estate_listings"],
            metadata={"description": "Mẫu lọc biệt thự diện tích lớn"}
        )

        # Tìm kiếm bằng câu hỏi đồng nghĩa ngữ nghĩa
        query = "Biến động giá chung cư Cầu Giấy theo các tháng"
        few_shots = memory.get_relevant_few_shots(query=query, domain_id="real_estate", top_k=2)

        self.assertGreater(len(few_shots), 0)
        top_shot = few_shots[0]
        self.assertIn("fct_district_monthly_summary", top_shot["sql"])


if __name__ == "__main__":
    unittest.main()
