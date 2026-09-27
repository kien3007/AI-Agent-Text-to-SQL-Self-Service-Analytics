"""
RBAC Authentication Module.
Phase 1: Static token map.
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

security = HTTPBearer(auto_error=False)

class UserContext(BaseModel):
    user_id: str
    role: str  # "analyst" | "admin"
    display_name: str

_TOKEN_MAP: Dict[str, UserContext] = {
    os.getenv("ANALYST_TOKEN", "analyst-dev-token"): UserContext(
        user_id="analyst-01", role="analyst", display_name="Analyst"
    ),
    os.getenv("ADMIN_TOKEN", "admin-dev-token"): UserContext(
        user_id="admin-01", role="admin", display_name="Administrator"
    ),
}

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserContext:
    if credentials is None:
        # Dev mode allow fallback to Analyst if no token provided, to not break existing tests initially, 
        # but spec says require it. Let's strictly require it.
        raise HTTPException(status_code=401, detail="Yêu cầu xác thực. Cung cấp Bearer token.")
        
    user = _TOKEN_MAP.get(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Token không hợp lệ hoặc đã hết hạn.")
    return user

def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Thao tác này yêu cầu quyền Admin.")
    return user

_BUDGET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "query_budgets.json")
_DAILY_BUDGET_LIMIT = int(os.getenv("DAILY_QUERY_BUDGET", "100"))

def _load_budgets() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(_BUDGET_FILE):
        return {}
    try:
        with open(_BUDGET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_budgets(data: Dict[str, Dict[str, Any]]):
    os.makedirs(os.path.dirname(_BUDGET_FILE), exist_ok=True)
    with open(_BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_and_deduct_budget(user_id: str):
    """Giới hạn số lượng truy vấn mỗi ngày trên từng user."""
    # Trả về luôn nếu là system hoặc admin
    if user_id in ("system", "admin-01"):
        return
        
    budgets = _load_budgets()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    user_record = budgets.get(user_id, {"date": today_str, "count": 0})
    
    # Reset nếu sang ngày mới
    if user_record.get("date") != today_str:
        user_record = {"date": today_str, "count": 0}
        
    current = user_record.get("count", 0)
    
    if current >= _DAILY_BUDGET_LIMIT:
        raise HTTPException(
            status_code=429, 
            detail=f"Quá hạn mức truy vấn ({_DAILY_BUDGET_LIMIT}/ngày). Vui lòng thử lại vào ngày mai."
        )
        
    user_record["count"] = current + 1
    budgets[user_id] = user_record
    _save_budgets(budgets)
