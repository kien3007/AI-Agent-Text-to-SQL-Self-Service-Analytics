"""
Khởi chạy dịch vụ AI-Agent Text-to-SQL Self-Service Analytics Web Server.
Cung cấp đồng thời REST API, SSE Streaming và Web UI tại: http://localhost:8000
"""

import os
import sys
from pathlib import Path

# Thêm thư mục backend vào sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import uvicorn
from app.core.config import settings


def start():
    host = settings.APP_HOST
    port = settings.APP_PORT
    print("=" * 65)
    print("🚀 ĐANG KHỞI CHẠY HỆ THỐNG AI-AGENT TEXT-TO-SQL SELF-SERVICE ANALYTICS")
    print("=" * 65)
    print(f"🌐 Web Application UI : http://{host}:{port}/app")
    print(f"📚 API Documentation   : http://{host}:{port}/docs")
    print(f"🩺 Health Check API    : http://{host}:{port}/api/health")
    print(f"💬 SSE Chat Stream API : http://{host}:{port}/api/chat/stream")
    print("=" * 65)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=(settings.APP_ENV == "development"),
        log_level="info"
    )


if __name__ == "__main__":
    start()
