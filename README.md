# AI-Agent Text-to-SQL Self-Service Analytics

> Hệ thống trợ lý ảo thông minh chuyển đổi ngôn ngữ tự nhiên (Tiếng Việt) thành truy vấn SQL phục vụ phân tích dữ liệu tự phục vụ (Self-Service Analytics). Hỗ trợ kiến trúc Data Mesh, Data Governance, và Data Lineage với khả năng chạy trên Apache Doris OLAP.

---

## 📌 Các tính năng chính

* **Kiến trúc Data Mesh**: Hỗ trợ nhiều Domain (e.g. Bất động sản, E-commerce, Healthcare) với Metadata phân loại (Owner, Data Steward, Slack Channel) và Data Contracts qua `domain.yaml`.
* **Multi-Agent với LangGraph**: Workflow AI chặt chẽ: `Intent $\rightarrow$ Schema RAG $\rightarrow$ SQL Gen $\rightarrow$ HITL Gate $\rightarrow$ Execution $\rightarrow$ Visualizer`.
* **Mô hình kép (Dual Model)**: 
  * Qwen-2.5-Coder: Chuyên sinh mã SQL chính xác, tối ưu cho DAIL-SQL.
  * Qwen-3: Suy luận ngữ cảnh, tư duy phân tích (CoT) và diễn giải kết quả bằng Tiếng Việt.
* **Human-In-The-Loop (HITL) Gate**: Dừng truy vấn có chi phí lớn, cảnh báo rủi ro quét dữ liệu và yêu cầu người dùng (Admin) phê duyệt trước khi thực thi.
* **Data Governance & Audit**: Quản lý hạn mức (Query Budget), gắn nhãn dữ liệu nhạy cảm (PII), và Audit log chi tiết (lưu trữ JSONL/Doris).
* **Data Lineage**: Theo dõi luồng dữ liệu thông qua dbt `manifest.json` và log nạp dữ liệu (Ingestion Log).
* **Self-Healing API**: Agent có khả năng tự sửa lỗi khi truy vấn thất bại (Retry logic qua Validator).

---

## 🚀 Cài đặt & Khởi động nhanh (Quick Start)

### 1. Khởi động bằng Docker Compose
Dự án được cấu hình đầy đủ qua Docker Compose (FastAPI Backend, Qdrant Vector DB, Apache Doris FE/BE, Next.js Frontend):
```bash
# Build và chạy ngầm toàn bộ dịch vụ
make up

# Xem logs backend
make logs
```

### 2. Phát triển cục bộ (Local Development)
```bash
# 1. Cài đặt Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Hoặc .venv\Scripts\activate trên Windows
pip install -r requirements.txt

# 2. Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa file .env với API Key (Qwen-3, Qwen-2.5-Coder), Qdrant URL và Doris connection

# 3. Chạy Vector DB (Qdrant)
docker compose up -d qdrant

# 4. Chạy Backend server (FastAPI trên port 8000)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Chạy Frontend (Next.js 15 trên port 3000)
cd ../frontend
npm install
npm run dev
```
> **Endpoints truy cập:**
> - Frontend UI: `http://localhost:3000`
> - Backend REST / OpenAPI Swagger: `http://localhost:8000/docs`
> - Qdrant Vector Dashboard: `http://localhost:6333/dashboard`

---

## 🏗️ Kiến trúc & Tổ chức thư mục

* `/backend/app/agent/`: Chứa các node LangGraph (Intent, Schema Linking, SQL Gen, Validator, HITL Gate, Executor, Formatter).
* `/backend/app/rag/`: LlamaIndex + Qdrant Vector Store, BAAI/bge-m3 Embedding và NetworkX Minimum Steiner Tree.
* `/backend/app/api/routers/`: FastAPI Endpoints (Chat SSE, Domains, Health Benchmark, Auth RBAC).
* `/backend/domains/`: Định nghĩa Data Mesh Config (`domain.yaml`, `schema.yaml`, `metrics.yaml`) cho từng nghiệp vụ.
* `/frontend/`: Giao diện Next.js 15 (React 19, TypeScript, Recharts, SSE streaming, Auth Context).
* `/infra/dbt/`: Dự án dbt (Data marts, semantic models, data lineage qua `manifest.json`).
* `/scripts/`: Script tiện ích (Nạp Parquet vào Doris, Benchmark, System Health Check).

---

## 📊 Benchmark Hệ thống

Chạy script benchmark hệ thống tự động đánh giá độ chính xác (Accuracy), thời gian trễ (Latency), và độ phủ của các truy vấn:
```bash
make benchmark
```
Hoặc xem trực tiếp qua nút **Benchmark** trên giao diện Frontend Web.

---

## 🛡️ Data Governance & SLA

Hệ thống cung cấp API cho phép Data Stewards kiểm soát chất lượng dữ liệu:
* `/api/domains/{id}/contract`: Xem cấu trúc cam kết bảng/metric và thông tin Owner.
* `/api/domains/{id}/freshness`: Theo dõi trạng thái nạp dữ liệu mới nhất (Ingestion Lineage).
* **Schema Filter**: Tự động lọc các cột nhạy cảm (`is_sensitive: true`) nếu role người dùng không phải admin.

## 📌 Tài liệu Chi tiết
Xem toàn bộ phân tích về bài toán, kiến trúc, tech stack: 👉 **[ANALYSIS_AND_TECH_STACK.md](./ANALYSIS_AND_TECH_STACK.md)**