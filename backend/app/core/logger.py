"""
Audit Logger.
Ghi log kiểm toán lưu trữ tập trung, phục vụ truy vết theo User ID, Domain, Query.
"""
import os
import json
import logging
from datetime import datetime
from app.core.config import settings

# Đảm bảo thư mục log tồn tại
os.makedirs("logs", exist_ok=True)

# Cấu hình file log
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("logs/audit.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(message)s'))
audit_logger.addHandler(file_handler)

def log_audit_event(
    user_id: str,
    action: str,
    domain_id: str = None,
    sql_query: str = None,
    details: dict = None,
    status: str = "SUCCESS"
):
    """
    Ghi log sự kiện kiểm toán dạng JSON.
    action: e.g., 'EXECUTE_QUERY', 'HITL_APPROVE', 'HITL_REJECT'
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id or "system",
        "action": action,
        "domain_id": domain_id,
        "sql_query": sql_query,
        "status": status,
        "details": details or {}
    }
    audit_logger.info(json.dumps(log_entry, ensure_ascii=False))
