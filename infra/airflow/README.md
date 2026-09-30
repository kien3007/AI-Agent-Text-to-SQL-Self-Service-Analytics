# 🚀 Apache Airflow Orchestration (Lightweight Edition)

Thư mục này chứa cấu hình và DAGs của **Apache Airflow tinh gọn** dùng để điều phối (orchestrate) toàn bộ luồng **ELT & Data Quality**:
`CSDL Nguồn (MSSQL / Postgres / MySQL) ➡️ Nạp vào DuckDB ➡️ dbt Transform ➡️ dbt Test ➡️ AI Agent Analytics`.

---

## 🌟 1. Điểm nổi bật & Tối ưu tinh gọn (< 1GB RAM)

- **LocalExecutor**: Chạy trực tiếp các task dạng sub-process bên trong container scheduler, **hoàn toàn loại bỏ Celery Worker & Redis**, tiết kiệm ~2GB - 3GB RAM so với cụm Airflow tiêu chuẩn.
- **Dedicated Alpine Postgres (Port 54323)**: Container PostgreSQL 15 Alpine chuyên biệt lưu metadata của Airflow, cô lập hoàn toàn với Supabase (54322) và chỉ chiếm ~30MB RAM.
- **Resource Limits**: Mỗi container (`webserver`, `scheduler`) đều bị giới hạn trần 384MB RAM, đảm bảo máy trạm phát triển không bao giờ bị giật lag.
- **Tích hợp sẵn DuckDB & dbt**: Docker image đã cài sẵn `duckdb`, `dbt-core`, `dbt-duckdb`, `pymssql`, `psycopg2-binary`, và `sqlalchemy`.

---

## 📂 2. Cấu trúc thư mục

```
infra/airflow/
├── Dockerfile                      # Image Airflow tùy biến (DuckDB, dbt, SQL drivers)
├── docker-compose.airflow.yml      # Cụm container Airflow (Webserver, Scheduler, Postgres, Init)
├── start-airflow.ps1               # Script 1-click khởi động Airflow
├── stop-airflow.ps1                # Script 1-click tắt Airflow an toàn
├── README.md                       # Hướng dẫn sử dụng chi tiết
├── dags/
│   ├── dag_mssql_to_duckdb_pipeline.py  # DAG chính: Ingest -> dbt run -> dbt test -> Summary
│   └── dag_duckdb_maintenance.py        # DAG bảo trì: Checkpoint, Vacuum, Analyze, Clean log
├── logs/                           # Logs thực thi các task của Airflow
└── plugins/                        # Custom plugins mở rộng (nếu cần)
```

---

## 🚀 3. Cách khởi động và truy cập

### Khởi động Airflow:
Mở PowerShell tại thư mục gốc của dự án và chạy:
```powershell
.\infra\airflow\start-airflow.ps1
```
*(Lần đầu chạy, Docker sẽ tự động build image và khởi tạo tài khoản Admin trong ~1-2 phút)*

### Truy cập Web UI:
- **URL**: [http://localhost:8080](http://localhost:8080)
- **Tài khoản**: `admin`
- **Mật khẩu**: `admin`

### Dừng Airflow:
```powershell
.\infra\airflow\stop-airflow.ps1
```

---

## 🔄 4. Chi tiết các DAGs điều phối

### 1. `mssql_to_duckdb_pipeline`
- **Mục đích**: Tự động đồng bộ dữ liệu từ CSDL bên ngoài vào DuckDB cục bộ (`data/warehouse.duckdb`), chuyển đổi thành Data Marts, lập chỉ mục Vector DB cho AI Agent và cập nhật Freshness SLA.
- **Lập lịch**: Chạy hàng ngày (`@daily`) hoặc kích hoạt thủ công (Trigger DAG w/ config).
- **Chuỗi Task**:
  1. `check_db_connectivity`: Kiểm tra CSDL nguồn có online hay không.
  2. `ingest_source_to_duckdb`: Trích xuất dữ liệu theo batch stream nạp vào DuckDB (hỗ trợ `full_refresh` và `incremental`).
  3. `dbt_run_marts`: Dựng view staging và bảng aggregated marts trong DuckDB.
  4. `dbt_test_quality`: Kiểm tra ràng buộc chất lượng dữ liệu (`unique`, `not_null`, foreign keys).
  5. `sync_semantic_index`: Tự động đồng bộ schema, metadata cột và business metrics vào Vector Store Qdrant (cho AI Agent).
  6. `update_data_freshness`: Tính toán và cập nhật thời gian trễ dữ liệu thực tế và SLA Freshness.
  7. `pipeline_summary`: Tổng hợp toàn bộ số liệu nạp, transform, và độ sẵn sàng của AI Agent.

- **Tham số tùy biến khi Trigger thủ công (JSON config)**:
  ```json
  {
    "source_connection_url": "mssql+pymssql://user:pass@host:1433/db",
    "domain_id": "vietnam_ecommerce",
    "sync_mode": "incremental",
    "tables": "orders,customers"
  }
  ```

### 2. `duckdb_maintenance`
- **Mục đích**: Bảo trì định kỳ kho dữ liệu DuckDB để giữ tốc độ truy vấn tối ưu cho AI Agent.
- **Lập lịch**: Hàng tuần (`@weekly`).
- **Chuỗi Task**:
  1. `checkpoint_and_vacuum`: Ép flush Write-Ahead Log (WAL) và thu hồi dung lượng đĩa trống.
  2. `analyze_statistics`: Cập nhật thống kê phân phối dữ liệu cho Query Optimizer của DuckDB.
  3. `clean_old_logs`: Tự động xóa các bản ghi log trong `_ingestion_sync_log` cũ hơn 30 ngày.

---

## 🛠️ 5. Các phương thức kích hoạt Ingestion khác

Ngoài việc để Airflow chạy theo lịch, bạn có thể chủ động nạp dữ liệu vào DuckDB bất cứ lúc nào bằng 2 cách:

### Cách A: Qua CLI Script
```powershell
.venv\Scripts\python.exe backend/scripts/ingest_to_duckdb.py `
  --source "postgresql://user:pass@localhost:5432/mydb" `
  --domain ecommerce `
  --mode full_refresh
```

### Cách B: Qua REST API của Backend
```http
POST /api/v1/domains/vietnam_ecommerce/ingest
Content-Type: application/json

{
  "sync_mode": "incremental",
  "tables": ["orders", "customers"]
}
```
Xem lịch sử đồng bộ:
```http
GET /api/v1/domains/vietnam_ecommerce/ingest/history?limit=20
```
