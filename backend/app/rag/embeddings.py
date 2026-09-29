"""
Bilingual Embedding Engine using BAAI/bge-m3 for Cross-Lingual Real Estate Schema Linking.
Cung cấp vector embedding đa ngôn ngữ 1024 chiều chuẩn hóa phục vụ LlamaIndex + Qdrant.
"""

import os
import sys
from typing import List, Union, Optional
import numpy as np

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


Documents = List[str]
Embeddings = List[List[float]]


class BGEM3EmbeddingFunction:
    """
    Embedding Function sử dụng BAAI/bge-m3 (1024 chiều).
    Hỗ trợ đối sánh ngữ nghĩa chéo (Cross-lingual Semantic Alignment):
    Câu hỏi Tiếng Việt -> Metadata Tiếng Anh/SQL -> Giá trị danh mục thực tế.
    Hỗ trợ chế độ 'mock' cho Unit Tests và CI/CD để không phải tải mô hình nặng.
    """

    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        if model_name is None:
            model_name = os.getenv("EMBEDDING_MODEL")
            if not model_name:
                try:
                    from app.core.config import settings
                    model_name = settings.EMBEDDING_MODEL
                except Exception:
                    model_name = "BAAI/bge-m3"
        self.model_name = model_name or "BAAI/bge-m3"
        self.device = device
        self._model = None
        self._is_mock = self.model_name.lower() in ("mock", "none", "dummy")

    def name(self) -> str:
        return "mock_embedding" if self._is_mock else self.model_name

    @property
    def model(self):
        if self._is_mock:
            return None
        if self._model is None:
            print(f"[EmbeddingEngine] Đang khởi tạo mô hình đa ngôn ngữ {self.model_name} trên {self.device}...")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                print(f"[EmbeddingEngine] Khởi tạo thành công {self.model_name}!")
            except Exception as e:
                print(f"[EmbeddingEngine] Cảnh báo lỗi tải {self.model_name}: {e}. Thử fallback sang multilingual model...")
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device=self.device)
                print("[EmbeddingEngine] Fallback model khởi tạo thành công!")
        return self._model

    def __call__(self, input: Documents) -> Embeddings:
        """Sinh vector embedding cho danh sách documents (Callable interface)."""
        if not input:
            return []
        
        if self._is_mock:
            return [[0.0] * 1024 for _ in input]

        # Chuyển đổi embedding sang float list chuẩn với inference_mode
        import torch
        with torch.inference_mode():
            embeddings = self.model.encode(
                input,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False
            )
        return [emb.tolist() for emb in embeddings]

    def encode_query(self, query: str) -> List[float]:
        """Sinh vector cho một câu truy vấn."""
        if self._is_mock:
            return [0.0] * 1024

        import torch
        with torch.inference_mode():
            emb = self.model.encode(
                [query],
                normalize_embeddings=True,
                show_progress_bar=False
            )
        return emb[0].tolist()

