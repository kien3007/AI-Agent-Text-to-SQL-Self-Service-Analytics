"""
LlamaIndex Custom BaseEmbedding Adapter using BAAI/bge-m3.
Tích hợp trực tiếp với kiến trúc LlamaIndex cho Schema Linking và Few-Shot Retrieval,
tận dụng chung trọng số mô hình BAAI/bge-m3 (1024 chiều) mà không cần nạp trùng lặp.
"""

from typing import List, Optional, Any
from pydantic import PrivateAttr
from llama_index.core.base.embeddings.base import BaseEmbedding

from app.rag.embeddings import BGEM3EmbeddingFunction


class LlamaIndexBGEM3Embedding(BaseEmbedding):
    """
    Adapter chuyển đổi BGEM3EmbeddingFunction (hoặc SentenceTransformer BAAI/bge-m3)
    sang giao diện BaseEmbedding chuẩn của LlamaIndex.
    """
    _bge_fn: Any = PrivateAttr()

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        embedding_function: Optional[BGEM3EmbeddingFunction] = None,
        **kwargs: Any
    ):
        super().__init__(model_name=model_name, **kwargs)
        self._bge_fn = embedding_function or BGEM3EmbeddingFunction(model_name=model_name)

    @classmethod
    def class_name(cls) -> str:
        return "LlamaIndexBGEM3Embedding"

    def _get_query_embedding(self, query: str) -> List[float]:
        """Sinh vector embedding cho câu truy vấn người dùng."""
        if hasattr(self._bge_fn, "encode_query"):
            res = self._bge_fn.encode_query(query)
        else:
            emb_res = self._bge_fn([query])
            res = emb_res[0] if emb_res else []
        if hasattr(res, "tolist"):
            return res.tolist()
        return [float(x) for x in res]

    def _get_text_embedding(self, text: str) -> List[float]:
        """Sinh vector embedding 1024 chiều cho một đoạn tài liệu / schema text."""
        res = self._bge_fn([text])
        if res:
            first = res[0]
            if hasattr(first, "tolist"):
                return first.tolist()
            return [float(x) for x in first]
        return [0.0] * 1024

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Sinh batch vector embedding tối ưu hóa hiệu năng."""
        if not texts:
            return []
        res = self._bge_fn(texts)
        converted = []
        for r in res:
            if hasattr(r, "tolist"):
                converted.append(r.tolist())
            else:
                converted.append([float(x) for x in r])
        return converted

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Async query embedding fallback về sync execution."""
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Async text embedding fallback về sync execution."""
        return self._get_text_embedding(text)
