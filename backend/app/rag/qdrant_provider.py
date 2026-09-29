"""
Qdrant Vector Database Provider Module.
Quản lý kết nối tới Qdrant On-premise (Docker/Server) với cơ chế tự động fallback:
1. Qdrant Server (HTTP/gRPC) trên cổng 6333 (Docker, on-prem container)
2. Local Embedded Disk Qdrant (./data/qdrant_db) nếu server chưa khởi động hoặc offline
3. In-memory Qdrant (":memory:") phục vụ unit tests và kiểm thử nhanh
"""

import os
import socket
from typing import Optional, Union
import qdrant_client
from qdrant_client import QdrantClient
from qdrant_client.http import models
from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.core.config import settings


_CLIENT_CACHE = {}


def is_qdrant_server_available(host: str = "localhost", port: int = 6333, timeout_sec: float = 0.5) -> bool:
    """Kiểm tra máy chủ Qdrant server có đang hoạt động trên cổng host:port không."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_sec):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def get_qdrant_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    storage_path: Optional[str] = None,
    in_memory: bool = False
) -> QdrantClient:
    """
    Khởi tạo QdrantClient tối ưu theo môi trường:
    - in_memory=True: Chạy RAM siêu nhẹ cho unit test
    - Nếu Server 6333 khả dụng: Kết nối HTTP client
    - Nếu Server không khả dụng: Tự động fallback sang embedded disk storage on-premise với singleton caching
    - Nếu thư mục bị khóa bởi tiến trình khác: Tự động fallback sang in-memory client
    """
    if in_memory:
        return QdrantClient(":memory:")

    target_host = host or settings.QDRANT_HOST
    target_port = port or settings.QDRANT_PORT

    if is_qdrant_server_available(target_host, target_port):
        server_url = f"http://{target_host}:{target_port}"
        if server_url in _CLIENT_CACHE:
            return _CLIENT_CACHE[server_url]
        try:
            client = QdrantClient(url=server_url)
            client.get_collections()
            _CLIENT_CACHE[server_url] = client
            return client
        except Exception:
            pass

    # Fallback sang embedded on-prem disk storage với singleton process cache
    persist_dir = os.path.abspath(storage_path or settings.QDRANT_STORAGE_DIR)
    os.makedirs(persist_dir, exist_ok=True)
    if persist_dir in _CLIENT_CACHE:
        return _CLIENT_CACHE[persist_dir]

    try:
        client = QdrantClient(path=persist_dir)
        _CLIENT_CACHE[persist_dir] = client
        return client
    except Exception as e:
        print(f"[QdrantProvider] Không thể khóa {persist_dir} ({e}). Tạm thời dùng in-memory fallback client.")
        return QdrantClient(":memory:")


def ensure_collection_exists(
    client: QdrantClient,
    collection_name: str,
    vector_dim: int = 1024,
    distance: models.Distance = models.Distance.COSINE
) -> None:
    """Đảm bảo Collection Qdrant đã được tạo với số chiều và độ đo khoảng cách phù hợp."""
    try:
        collections_info = client.get_collections().collections
        existing_names = [c.name for c in collections_info]
        if collection_name in existing_names:
            coll_info = client.get_collection(collection_name)
            curr_size = getattr(getattr(coll_info.config.params, "vectors", None), "size", None)
            if curr_size is not None and curr_size != vector_dim:
                client.delete_collection(collection_name)
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=vector_dim, distance=distance)
                )
        else:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_dim, distance=distance)
            )
    except Exception as e:
        print(f"[QdrantProvider] Cảnh báo kiểm tra collection {collection_name}: {e}")


def get_qdrant_vector_store(
    client: QdrantClient,
    collection_name: str,
    vector_dim: int = 1024
) -> QdrantVectorStore:
    """Khởi tạo LlamaIndex QdrantVectorStore tương thích."""
    ensure_collection_exists(client, collection_name, vector_dim=vector_dim)
    return QdrantVectorStore(client=client, collection_name=collection_name)
