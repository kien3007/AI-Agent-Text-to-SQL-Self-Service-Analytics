"""
FastAPI Main Application Entrypoint.
Cung cấp toàn bộ hệ thống REST API và SSE Streaming cho AI-Agent Text-to-SQL.
"""

import os
import sys

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.auth import auth_router
from app.api.routers.health import router as health_router
from app.api.routers.domains import router as domains_router
from app.api.routers.chat import router as chat_router

app = FastAPI(
    title="AI-Agent Text-to-SQL Self-Service Analytics API",
    description="Hệ thống trợ lý phân tích dữ liệu tự phục vụ thông minh, điều phối mô hình kép Qwen 3 & Qwen 2.5-Coder qua LangGraph.",
    version="2.0.0"
)

# Cấu hình CORS cho phép Frontend (Next.js / React) gọi API thuận tiện
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tích hợp các Routers API
app.include_router(auth_router, prefix="/api")        # POST /api/auth/token
app.include_router(health_router, prefix="/api")
app.include_router(domains_router, prefix="/api")
app.include_router(chat_router, prefix="/api")

# Gắn thư mục Frontend tĩnh nếu đã được build (static export)
frontend_out_dir = Path(backend_dir).parent / "frontend" / "out"
if frontend_out_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_out_dir), html=True), name="frontend")


@app.get("/")
def root(request: Request):
    """Điểm chạm gốc cung cấp thông tin hệ thống và tài liệu OpenAPI hoặc chuyển hướng đến UI."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and frontend_out_dir.exists():
        return RedirectResponse(url="/app/")
    return {
        "message": "Chào mừng đến với AI-Agent Text-to-SQL Self-Service Analytics API!",
        "version": "2.0.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "status": "ready"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

