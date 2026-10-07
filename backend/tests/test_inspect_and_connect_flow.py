"""
Kiểm thử trực tiếp vào HTTP server đang chạy trên cổng 8000.
"""
import json
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def post(url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(f"{BASE_URL}{url}", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def get(url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{url}", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 70)
    print("KIỂM THỬ TRỰC TIẾP API INSPECT & CONNECT TRÊN SERVER LIVE (PORT 8000)")
    print("=" * 70)

    # 1. Login
    print("\n[1] Đăng nhập tài khoản admin...")
    status, res = post("/api/auth/token", {"username": "admin", "password": "admin123"})
    assert status == 200, f"Đăng nhập thất bại: {res}"
    token = res["access_token"]
    print(f" -> Đăng nhập thành công! Token: {token[:25]}...")

    # 2. Inspect DuckDB
    print("\n[2] Gọi /api/domains/inspect-connection với DuckDB...")
    status, duck_res = post("/api/domains/inspect-connection", {"connection_url": "./data/warehouse.duckdb"}, token=token)
    assert status == 200, f"Inspect DuckDB thất bại: {duck_res}"
    print(f" -> Dialect: {duck_res['dialect']}")
    print(f" -> Current DB: {duck_res['current_database']}")
    print(f" -> Danh sách Databases: {duck_res['databases']}")
    print(f" -> Danh sách Schemas: {duck_res['schemas']}")
    assert "main" in duck_res["schemas"]

    # 3. Inspect SQLite
    print("\n[3] Gọi /api/domains/inspect-connection với SQLite...")
    status, sqlite_res = post("/api/domains/inspect-connection", {"connection_url": "./data/test_onboarding_sample.db"}, token=token)
    assert status == 200, f"Inspect SQLite thất bại: {sqlite_res}"
    print(f" -> Dialect: {sqlite_res['dialect']}")
    print(f" -> Current DB: {sqlite_res['current_database']}")
    print(f" -> Danh sách Databases: {sqlite_res['databases']}")
    print(f" -> Danh sách Schemas: {sqlite_res['schemas']}")

    # 4. Connect sau khi chọn Database & Schema
    target_db = sqlite_res["databases"][0]
    target_schema = sqlite_res["schemas"][0]
    print(f"\n[4] Gọi /api/domains/connect với Database='{target_db}' & Schema='{target_schema}'...")
    status, conn_res = post("/api/domains/connect", {
        "connection_url": "./data/test_onboarding_sample.db",
        "db_name": target_db,
        "schema_name": target_schema,
        "domain_id": "test_onboarding_verified",
        "display_name": "CSDL Thử Nghiệm Onboarding Live",
        "save_yaml": False
    }, token=token)
    assert status == 200, f"Connect thất bại: {conn_res}"
    print(f" -> Trạng thái: {conn_res['status']}")
    print(f" -> Domain ID: {conn_res['domain_id']}")
    print(f" -> Database: {conn_res['database_name']}")
    print(f" -> Schema: {conn_res['schema_name']}")
    print(f" -> Số bảng đã crawl: {conn_res['tables_count']}")
    print(f" -> Danh sách bảng: {conn_res['tables']}")

    # 5. Xác minh qua /api/domains
    print("\n[5] Kiểm tra domain mới tạo qua GET /api/domains/test_onboarding_verified...")
    status, detail_res = get("/api/domains/test_onboarding_verified", token=token)
    assert status == 200, f"Lấy domain thất bại: {detail_res}"
    print(f" -> Domain tồn tại thành công với {len(detail_res['tables'])} bảng!")

    print("\n" + "=" * 70)
    print(">>> KẾT QUẢ: TÍNH NĂNG CHỌN DATABASE & SCHEMA ĐÃ HOẠT ĐỘNG HOÀN HẢO! <<<")
    print("=" * 70)

if __name__ == "__main__":
    main()
