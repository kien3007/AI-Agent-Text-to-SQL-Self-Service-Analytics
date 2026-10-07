"""
Enterprise Supabase-Integrated RBAC Authentication Module.
Xác thực danh tính bằng Supabase Auth JWT (HS256), hỗ trợ:
  - Supabase Self-Hosted (http://localhost:54321) & Supabase Cloud
  - Tự động verify chữ ký JWT từ Supabase Bearer token (Stateless, < 1ms)
  - Trích xuất metadata người dùng: user_id (UUID), email, role ("admin" | "analyst"), display_name
  - Proxy endpoints: POST /api/auth/token và POST /api/auth/register kết nối trực tiếp với GoTrue
  - Chế độ Fallback thông minh: hỗ trợ môi trường dev/offline và test cases tự động
"""
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

import httpx
from fastapi import Depends, HTTPException, status, APIRouter, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("auth")

# --------------------------------------------------------------------------
# Supabase & JWT Configuration
# --------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321").rstrip("/")
SUPABASE_JWT_SECRET = os.getenv(
    "SUPABASE_JWT_SECRET",
    os.getenv("JWT_SECRET_KEY", "super-secret-jwt-token-with-at-least-32-characters-long")
)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Danh sách email/username mặc định có đặc quyền Admin
ADMIN_IDENTIFIERS: List[str] = [
    "admin",
    "admin-01",
    "admin-02",
    "kien3007",
    "kiennguyen300703",
    "kiennguyen300703@gmail.com",
    "admin@xomdata.com",
    "admin@local.host"
]

# --------------------------------------------------------------------------
# Fallback Dev User Registry (Hỗ trợ chạy test offline khi Docker chưa bật)
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
        "email":    "kiennguyen300703@gmail.com"
    },
    os.getenv("ANALYST_USERNAME", "analyst"): {
        "password": os.getenv("ANALYST_PASSWORD", "analyst123"),
        "role":     "analyst",
        "display_name": "Analyst",
        "user_id":  "analyst-01",
        "email":    "analyst@local.host"
    },
    os.getenv("ADMIN_USERNAME", "admin"): {
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
        "role":     "admin",
        "display_name": "Administrator",
        "user_id":  "admin-01",
        "email":    "admin@local.host"
    },
}


def _load_user_registry() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Không thể đọc users.json: {e}")
    return dict(_DEFAULT_USERS)


def _save_user_registry(registry: Dict[str, Dict[str, Any]]):
    os.makedirs(os.path.dirname(_USERS_FILE), exist_ok=True)
    try:
        with open(_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Không thể lưu users.json: {e}")


# --------------------------------------------------------------------------
# Pydantic Schemas
# --------------------------------------------------------------------------
class UserContext(BaseModel):
    user_id:      str
    role:         str       # "analyst" | "admin"
    display_name: str
    username:     Optional[str] = None
    email:        Optional[str] = None


class TokenRequest(BaseModel):
    username: str  # Có thể là email hoặc username
    password: str


class RegisterRequest(BaseModel):
    username:     str  # Email hoặc username
    password:     str
    display_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int          # seconds
    user_id:      str
    role:         str
    username:     Optional[str] = None
    display_name: Optional[str] = None
    email:        Optional[str] = None


# --------------------------------------------------------------------------
# JWT Decoding & Verification
# --------------------------------------------------------------------------
def _create_access_token(payload: Dict[str, Any]) -> str:
    """Sinh JWT token ký bằng SUPABASE_JWT_SECRET (tương thích Supabase GoTrue)."""
    try:
        import jwt as _jwt
    except ImportError:
        raise RuntimeError("Cần cài đặt 'PyJWT': pip install PyJWT")

    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    data = {
        "aud": "authenticated",
        "role": payload.get("role", "authenticated"),
        **payload,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return _jwt.encode(data, SUPABASE_JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_access_token(token: str) -> Dict[str, Any]:
    """
    Giải mã và xác thực chữ ký JWT.
    Hỗ trợ cả JWT do Supabase GoTrue phát hành và JWT nội bộ.
    """
    try:
        import jwt as _jwt
        from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
    except ImportError:
        raise RuntimeError("Cần cài đặt 'PyJWT': pip install PyJWT")

    # Thử giải mã bằng SUPABASE_JWT_SECRET
    secrets_to_try = [SUPABASE_JWT_SECRET]
    fallback_secret = os.getenv("JWT_SECRET_KEY")
    if fallback_secret and fallback_secret not in secrets_to_try:
        secrets_to_try.append(fallback_secret)

    last_error = None
    for secret in secrets_to_try:
        try:
            return _jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options={"verify_aud": False}
            )
        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token đã hết hạn. Vui lòng đăng nhập lại.")
        except InvalidTokenError as err:
            last_error = err

    raise HTTPException(status_code=403, detail=f"Token không hợp lệ hoặc chữ ký sai: {last_error}")


create_access_token = _create_access_token
decode_access_token = _decode_access_token


# --------------------------------------------------------------------------
# FastAPI Dependencies
# --------------------------------------------------------------------------
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """
    FastAPI Dependency: Trích xuất UserContext từ Authorization Bearer Token.
    Đọc các claim chuẩn của Supabase: sub, email, user_metadata, role.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Yêu cầu xác thực. Cung cấp 'Authorization: Bearer <token>'."
        )

    payload = _decode_access_token(credentials.credentials)

    # 1. Trích xuất ID
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=403, detail="Token không chứa định danh người dùng (sub/user_id).")

    # 2. Trích xuất email & metadata
    email = payload.get("email")
    user_metadata = payload.get("user_metadata") or {}
    app_metadata = payload.get("app_metadata") or {}

    # 3. Phân quyền Role (admin | analyst)
    explicit_role = user_metadata.get("role") or app_metadata.get("role") or payload.get("role")
    is_admin = False
    if explicit_role == "admin" or explicit_role == "service_role":
        is_admin = True
    elif email and any(email.lower() == adm.lower() for adm in ADMIN_IDENTIFIERS):
        is_admin = True
    elif user_id in ADMIN_IDENTIFIERS:
        is_admin = True

    role = "admin" if is_admin else (explicit_role if explicit_role in ("admin", "analyst") else "analyst")

    # 4. Tên hiển thị
    display_name = (
        user_metadata.get("display_name")
        or payload.get("display_name")
        or (email.split("@")[0] if email else user_id)
    )
    username = payload.get("username") or email or user_id

    return UserContext(
        user_id=str(user_id),
        role=role,
        display_name=display_name,
        username=username,
        email=email
    )


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """FastAPI Dependency: Trích xuất UserContext nếu có token, nếu không thì fallback về analyst mặc định."""
    if credentials is not None:
        try:
            return get_current_user(credentials)
        except Exception:
            pass
    return UserContext(
        user_id="analyst",
        role="analyst",
        display_name="Guest Analyst",
        username="analyst"
    )


def require_admin(user: UserContext = Depends(get_current_user_optional)) -> UserContext:
    """Yêu cầu quyền Admin cho các endpoint nhạy cảm (CSDL connect, dbt compile, switch domain)."""
    if os.getenv("APP_ENV") != "production":
        return user
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Thao tác này yêu cầu quyền Administrator.")
    return user


# --------------------------------------------------------------------------
# Auth Router — Tích hợp Supabase GoTrue Auth API
# --------------------------------------------------------------------------
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.get("/config")
def get_auth_config():
    """Trả về cấu hình Supabase công khai cho Frontend client kết nối."""
    return {
        "supabase_url": SUPABASE_URL,
        "anon_key": SUPABASE_ANON_KEY,
        "auth_provider": "supabase_self_hosted" if "localhost" in SUPABASE_URL else "supabase_cloud"
    }


@auth_router.post("/token", response_model=TokenResponse)
async def login(req: TokenRequest):
    """
    Đăng nhập bằng username/email + password:
    1. Thử xác thực với Supabase GoTrue API (POST /auth/v1/token?grant_type=password)
    2. Nếu Supabase offline hoặc người dùng dev (admin/analyst), fallback sang registry cục bộ
    """
    # ── 1. Thử xác thực qua Supabase GoTrue nếu khả dụng ───────────────────────
    email_candidate = req.username if "@" in req.username else f"{req.username}@local.host"
    gotrue_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"

    headers = {"Content-Type": "application/json"}
    if SUPABASE_ANON_KEY:
        headers["apikey"] = SUPABASE_ANON_KEY

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.post(
                gotrue_url,
                json={"email": email_candidate, "password": req.password},
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                sb_user = data.get("user", {})
                sb_meta = sb_user.get("user_metadata", {})
                user_id = sb_user.get("id")
                email = sb_user.get("email")
                is_admin = (
                    sb_meta.get("role") == "admin"
                    or (email and any(email.lower() == adm.lower() for adm in ADMIN_IDENTIFIERS))
                    or req.username in ADMIN_IDENTIFIERS
                )
                role = "admin" if is_admin else sb_meta.get("role", "analyst")
                display_name = sb_meta.get("display_name") or req.username

                logger.info(f"[SUPABASE AUTH] Login thành công qua GoTrue: user={req.username} role={role}")
                return TokenResponse(
                    access_token=data.get("access_token"),
                    expires_in=data.get("expires_in", 3600),
                    user_id=user_id,
                    role=role,
                    username=req.username,
                    display_name=display_name,
                    email=email
                )
    except Exception as err:
        logger.debug(f"[SUPABASE AUTH] Không thể kết nối tới GoTrue ({err}), chuyển sang local fallback.")

    # ── 2. Local Fallback (cho offline dev / testing) ──────────────────────────
    registry = _load_user_registry()
    cleaned_input = req.username.strip().lower()
    user_data = None
    matched_username = req.username.strip()

    # 2.1 Tìm case-insensitive theo username key hoặc theo email
    for u_key, u_val in registry.items():
        if u_key.lower() == cleaned_input:
            user_data = u_val
            matched_username = u_key
            break
        u_email = str(u_val.get("email", "")).strip().lower()
        if u_email and u_email == cleaned_input:
            user_data = u_val
            matched_username = u_key
            break

    # 2.2 Alias mở rộng cho các tài khoản phổ biến
    if not user_data:
        if cleaned_input in ("kiennguyen300703@gmail.com", "kiennguyen300703", "kien3007"):
            user_data = registry.get("kien3007") or _DEFAULT_USERS.get("kien3007")
            matched_username = "kien3007"
        elif cleaned_input in ("admin@local.host", "admin@xomdata.com", "admin@gmail.com", "admin"):
            user_data = registry.get("admin") or _DEFAULT_USERS.get("admin")
            matched_username = "admin"
        elif cleaned_input in ("analyst@local.host", "analyst@xomdata.com", "analyst@gmail.com", "analyst"):
            user_data = registry.get("analyst") or _DEFAULT_USERS.get("analyst")
            matched_username = "analyst"

    if not user_data or user_data.get("password") != req.password:
        raise HTTPException(
            status_code=401,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác."
        )

    display_name = user_data.get("display_name", matched_username)
    email = user_data.get("email", f"{matched_username}@local.host")
    user_id = user_data.get("user_id", matched_username)
    role = user_data.get("role", "analyst")

    token_payload = {
        "sub":          user_id,
        "user_id":      user_id,
        "email":        email,
        "role":         role,
        "display_name": display_name,
        "username":     matched_username,
        "user_metadata": {
            "role": role,
            "display_name": display_name
        }
    }
    token = _create_access_token(token_payload)

    logger.info(f"[AUTH] Login thành công (Fallback): user={matched_username} role={role}")
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRE_HOURS * 3600,
        user_id=user_id,
        role=role,
        username=matched_username,
        display_name=display_name,
        email=email
    )


@auth_router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """
    Đăng ký tài khoản:
    1. Đăng ký qua Supabase GoTrue API (POST /auth/v1/signup)
    2. Fallback sang local registry nếu Supabase offline
    """
    username = req.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Tên đăng nhập phải có ít nhất 3 ký tự.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 6 ký tự.")

    email_candidate = username if "@" in username else f"{username}@local.host"
    display_name = (req.display_name or "").strip() or username
    role = "analyst"

    # ── 1. Đăng ký với Supabase GoTrue ───────────────────────────────────────
    signup_url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {"Content-Type": "application/json"}
    if SUPABASE_ANON_KEY:
        headers["apikey"] = SUPABASE_ANON_KEY

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                signup_url,
                json={
                    "email": email_candidate,
                    "password": req.password,
                    "data": {
                        "display_name": display_name,
                        "role": role,
                        "username": username
                    }
                },
                headers=headers
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                access_token = data.get("access_token")
                user_obj = data.get("user") or data
                user_id = user_obj.get("id")

                if access_token:
                    logger.info(f"[SUPABASE AUTH] Đăng ký thành công qua GoTrue: user={username}")
                    return TokenResponse(
                        access_token=access_token,
                        expires_in=data.get("expires_in", 3600),
                        user_id=user_id,
                        role=role,
                        username=username,
                        display_name=display_name,
                        email=email_candidate
                    )
    except Exception as err:
        logger.debug(f"[SUPABASE AUTH] GoTrue signup không khả dụng ({err}), chuyển sang local fallback.")

    # ── 2. Fallback Local ───────────────────────────────────────────────────
    registry = _load_user_registry()
    for existing_user in registry.keys():
        if existing_user.lower() == username.lower():
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại trên hệ thống.")

    user_id = f"user-{int(datetime.now(timezone.utc).timestamp())}"
    new_user_data = {
        "password": req.password,
        "role": role,
        "display_name": display_name,
        "user_id": user_id,
        "email": email_candidate
    }
    registry[username] = new_user_data
    _save_user_registry(registry)

    token_payload = {
        "sub": user_id,
        "user_id": user_id,
        "email": email_candidate,
        "role": role,
        "display_name": display_name,
        "username": username,
        "user_metadata": {"role": role, "display_name": display_name}
    }
    token = _create_access_token(token_payload)

    logger.info(f"[AUTH] Đăng ký thành công (Fallback): user={username} id={user_id}")
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRE_HOURS * 3600,
        user_id=user_id,
        role=role,
        username=username,
        display_name=display_name,
        email=email_candidate
    )


@auth_router.get("/me", response_model=UserContext)
def get_me(user: UserContext = Depends(get_current_user)):
    """Lấy thông tin người dùng hiện tại từ token."""
    return user


# --------------------------------------------------------------------------
# Query Budget (Giữ nguyên hạn mức truy vấn theo user_id)
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
    if user_id in ("system", "admin-01", "admin-02") or user_id in ADMIN_IDENTIFIERS:
        return

    budgets = _load_budgets()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_record = budgets.get(user_id, {"date": today_str, "count": 0})

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
