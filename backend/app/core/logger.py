"""
Audit Logger.
Ghi log kiểm toán lưu trữ tập trung, phục vụ truy vết theo User ID, Domain, Query.
Sử dụng đường dẫn tuyệt đối từ cấu hình để đảm bảo hoạt động đúng trong Docker.
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# Tính đường dẫn tuyệt đối tới thư mục logs/ ở root workspace
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_LOG_DIR_ENV = os.getenv("LOG_DIR", "")

if _LOG_DIR_ENV:
    LOG_DIR = Path(_LOG_DIR_ENV)
else:
    # Ưu tiên: backend/../logs/ (root project), fallback: backend/logs/
    _root_logs = _BACKEND_DIR.parent / "logs"
    LOG_DIR = _root_logs if _root_logs.parent.exists() else _BACKEND_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_PATH = str(LOG_DIR / "audit.log")

# Cấu hình file log
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Tránh thêm handler trùng lặp nếu module được import nhiều lần
if not audit_logger.handlers:
    file_handler = logging.FileHandler(AUDIT_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(file_handler)


def log_audit_event(
    user_id: str,
    action: str,
    domain_id: str = None,
    sql_query: str = None,
    details: dict = None,
    status: str = "SUCCESS",
):
    """
    Ghi log sự kiện kiểm toán dạng JSON.
    action: e.g., 'EXECUTE_QUERY', 'HITL_APPROVE', 'HITL_REJECT', 'LOGIN'
    """
    log_entry = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "user_id":    user_id or "system",
        "action":     action,
        "domain_id":  domain_id,
        "sql_query":  sql_query,
        "status":     status,
        "details":    details or {},
    }
    audit_logger.info(json.dumps(log_entry, ensure_ascii=False))
