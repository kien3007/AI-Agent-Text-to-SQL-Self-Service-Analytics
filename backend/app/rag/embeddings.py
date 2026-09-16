"""
Bilingual Embedding Engine using BAAI/bge-m3 for Cross-Lingual Real Estate Schema Linking.
Tương thích hoàn toàn với ChromaDB EmbeddingFunction.
"""

import os
import sys
from typing import List, Union
import numpy as np

# Đảm bảo UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

class BGEM3EmbeddingFunction(EmbeddingFunction[Documents]):
    """
    ChromaDB Custom Embedding Function sử dụng BAAI/bge-m3.
    Hỗ trợ đối sánh ngữ nghĩa chéo (Cross-lingual Semantic Alignment):
    Câu hỏi Tiếng Việt -> Metadata Tiếng Anh/SQL -> Giá trị danh mục thực tế.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    @property
    def model(self):
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
        """Sinh vector embedding cho danh sách documents (ChromaDB interface)."""
        if not input:
            return []
        
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
        import torch
        with torch.inference_mode():
            emb = self.model.encode(
                [query],
                normalize_embeddings=True,
                show_progress_bar=False
            )
        return emb[0].tolist()
