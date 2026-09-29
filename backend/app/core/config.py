"""
Configuration Management Module.
Quản lý tập trung toàn bộ biến môi trường của hệ thống qua Pydantic Settings & python-dotenv.
Tự động phát hiện và nạp file .env từ thư mục gốc của project.
"""

import os
from pathlib import Path
from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Tìm đường dẫn file .env ở root của workspace hoặc backend
core_dir = Path(__file__).resolve().parent
backend_dir = core_dir.parent.parent
workspace_dir = backend_dir.parent

env_paths = [
    workspace_dir / ".env",
    backend_dir / ".env",
    Path.cwd() / ".env"
]

for p in env_paths:
    if p.exists():
        load_dotenv(dotenv_path=str(p), override=False)
        break


class AppSettings(BaseSettings):
    """Lớp cấu hình tập trung cho toàn bộ ứng dụng."""

    # 1. Warehouse OLAP Engine (DuckDB)
    WAREHOUSE_BACKEND: str = Field("duckdb", description="Động cơ Data Warehouse: 'duckdb' in-process siêu nhẹ")
    DUCKDB_PATH: str = Field("./data/warehouse.duckdb", description="Đường dẫn file DuckDB database")

    # 2. Dual-Model LLM Gateway
    LLM_BASE_URL: str = Field("", description="OpenAI-compatible API base URL (vLLM, Ollama, Together, OpenAI...)")
    LLM_API_KEY: str = Field("EMPTY", description="Khóa API xác thực LLM")
    MODEL_REASONER: str = Field("Qwen/Qwen2.5-72B-Instruct", description="Mô hình suy luận nghiệp vụ (Reasoner)")
    MODEL_CODER: str = Field("Qwen/Qwen2.5-Coder-32B-Instruct", description="Mô hình sinh mã SQL (Coder)")
    LLM_TEMPERATURE: float = Field(0.1, description="Độ biến thiên sáng tạo của LLM")
    LLM_MAX_TOKENS: int = Field(2048, description="Độ dài tối đa của phản hồi LLM")

    # 3. Semantic Embedding & Vector Store (LlamaIndex + Qdrant On-premise)
    EMBEDDING_MODEL: str = Field("BAAI/bge-m3", description="Tên mô hình multilingual embedding")
    QDRANT_HOST: str = Field("localhost", description="Địa chỉ Qdrant vector database server")
    QDRANT_PORT: int = Field(6333, description="Cổng Qdrant HTTP REST API")
    QDRANT_STORAGE_DIR: str = Field("./data/qdrant_db", description="Thư mục lưu trữ Qdrant On-premise (embedded/disk mode)")
    VECTOR_DB_BACKEND: str = Field("qdrant", description="Backend Vector DB: 'qdrant'")
    HF_TOKEN: str = Field("", description="Token Hugging Face Hub")

    # 4. Web Server & Networking
    APP_ENV: str = Field("development", description="Môi trường chạy (development, staging, production)")
    APP_HOST: str = Field("0.0.0.0", description="Địa chỉ lắng nghe của FastAPI web server")
    APP_PORT: int = Field(8000, description="Cổng dịch vụ FastAPI")
    CORS_ORIGINS: str = Field("*", description="Danh sách các domain cho phép gọi CORS")

    # 5. HITL Guardrails
    HITL_SCAN_TABLETS_THRESHOLD: int = Field(50, description="Ngưỡng cảnh báo số lượng tablets scan")
    HITL_ROW_COUNT_THRESHOLD: int = Field(1000000, description="Ngưỡng cảnh báo số dòng quét ước tính")
    HITL_ESTIMATED_BYTES_MB_THRESHOLD: int = Field(500, description="Ngưỡng cảnh báo dung lượng quét ước tính (MB)")

    model_config = SettingsConfigDict(
        env_file=str(workspace_dir / ".env") if (workspace_dir / ".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Chuyển chuỗi CORS_ORIGINS phân tách dấu phẩy thành danh sách."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Khởi tạo singleton settings dùng chung toàn ứng dụng
settings = AppSettings()
