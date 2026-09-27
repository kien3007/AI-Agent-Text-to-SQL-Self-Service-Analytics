"""
JWT-Based RBAC Authentication Module.
Enterprise-grade: JWT HS256 tokens với expiry, multi-user registry, phân quyền theo role.
Hỗ trợ 2 flow:
  - POST /api/auth/token    -> Đổi username+password lấy JWT access_token
  - Bearer <token>          -> Xác thực mọi endpoint bảo mật
"""
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("auth")

# --------------------------------------------------------------------------
# Config lấy từ env (production: dùng key dài random 64 bytes)
# --------------------------------------------------------------------------
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-random-64-char-secret-in-production")
JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# --------------------------------------------------------------------------
# User Registry — đọc từ file data/users.json nếu có, fallback sang env defaults
# --------------------------------------------------------------------------
_USERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "users.json"
)

_DEFAULT_USERS: Dict[str, Dict[str, Any]] = {
    "kien3007": {
        "password": "password123",
        "role":     "admin",
        "display_name": "Kien Nguyen",
        "user_id":  "admin-02",
    },
    os.getenv("ANALYST_USERNAME", "analyst"): {
        "password": os.getenv("ANALYST_PASSWORD", "analyst123"),
        "role":     "analyst",
        "display_name": "Analyst",
        "user_id":  "analyst-01",
    },
    os.getenv("ADMIN_USERNAME", "admin"): {
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
        "role":     "admin",
        "display_name": "Administrator",
        "user_id":  "admin-01",
    },
}


def _load_user_registry() -> Dict[str, Dict[str, Any]]:
    """Load user registry từ file JSON (nếu có), fallback sang defaults."""
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Không thể đọc users.json: {e}. Dùng default users.")
    return _DEFAULT_USERS


# --------------------------------------------------------------------------
# Pydantic Models
# --------------------------------------------------------------------------
class UserContext(BaseModel):
    user_id:      str
    role:         str       # "analyst" | "admin"
    display_name: str


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int          # seconds
    user_id:      str
    role:         str


# --------------------------------------------------------------------------
# JWT Helpers — sử dụng PyJWT (pip install PyJWT)
# --------------------------------------------------------------------------
def _create_access_token(payload: Dict[str, Any]) -> str:
    try:
        import jwt as _jwt
    except ImportError:
        raise RuntimeError("Cần cài đặt 'PyJWT': pip install PyJWT")

    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    data = {**payload, "exp": expire, "iat": datetime.now(timezone.utc)}
    return _jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        import jwt as _jwt
        from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
    except ImportError:
        raise RuntimeError("Cần cài đặt 'PyJWT': pip install PyJWT")

    try:
        return _jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn. Vui lòng đăng nhập lại.")
    except InvalidTokenError:
        raise HTTPException(status_code=403, detail="Token không hợp lệ.")


# --------------------------------------------------------------------------
# FastAPI Dependencies
# --------------------------------------------------------------------------
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Yêu cầu xác thực. Cung cấp 'Authorization: Bearer <token>'."
        )

    payload = _decode_access_token(credentials.credentials)

    user_id      = payload.get("user_id")
    role         = payload.get("role")
    display_name = payload.get("display_name", "User")

    if not user_id or not role:
        raise HTTPException(status_code=403, detail="Token không chứa thông tin người dùng hợp lệ.")

    return UserContext(user_id=user_id, role=role, display_name=display_name)


def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Thao tác này yêu cầu quyền Admin.")
    return user


# --------------------------------------------------------------------------
# Auth Router — POST /api/auth/token
# --------------------------------------------------------------------------
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/token", response_model=TokenResponse)
def login(req: TokenRequest):
    """
    Đăng nhập bằng username + password, nhận JWT access_token.
    Token có hiệu lực trong JWT_EXPIRE_HOURS giờ (mặc định 24h).
    """
    registry = _load_user_registry()
    user_data = registry.get(req.username)

    if not user_data or user_data.get("password") != req.password:
        raise HTTPException(
            status_code=401,
            detail="Tên đăng nhập hoặc mật khẩu không đúng."
        )

    payload = {
        "user_id":      user_data["user_id"],
        "role":         user_data["role"],
        "display_name": user_data.get("display_name", req.username),
        "username":     req.username,
    }
    token = _create_access_token(payload)

    logger.info(f"[AUTH] Login success: user={req.username} role={user_data['role']}")

    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRE_HOURS * 3600,
        user_id=user_data["user_id"],
        role=user_data["role"],
    )


@auth_router.get("/me", response_model=UserContext)
def get_me(user: UserContext = Depends(get_current_user)):
    """Trả về thông tin người dùng hiện tại từ JWT token."""
    return user


# --------------------------------------------------------------------------
# Query Budget (giữ nguyên, persist JSON)
# --------------------------------------------------------------------------
_BUDGET_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "query_budgets.json"
)
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
    if user_id in ("system", "admin-01"):
        return

    budgets    = _load_budgets()
    today_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    budgets[user_id]     = user_record
    _save_budgets(budgets)
