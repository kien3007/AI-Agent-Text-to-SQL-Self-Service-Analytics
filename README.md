# AI-Agent Text-to-SQL Self-Service Analytics

> **Hệ thống trợ lý phân tích dữ liệu thông minh** — chuyển câu hỏi ngôn ngữ tự nhiên (Tiếng Việt / English) thành truy vấn SQL, thực thi trên **DuckDB OLAP Engine** và trả về kết quả kèm biểu đồ trực quan.
> Kiến trúc **Data Mesh** · **Multi-Agent LangGraph** · **Three-Tier Memory** · **HITL Gate** · **ELT Pipeline** · **Airflow Orchestration**

---

## 📌 Tính năng nổi bật

| Tính năng | Mô tả |
|-----------|-------|
| **Natural Language → SQL** | Chuyển câu hỏi Việt/Anh thành SQL chuẩn, thực thi trên DuckDB hoặc bất kỳ CSDL nào |
| **Multi-Domain Data Mesh** | 19+ domain nghiệp vụ (E-commerce, Banking, Healthcare, Logistics, CRM, FMCG…) cấu hình qua YAML |
| **7-Node LangGraph Agent** | Pipeline AI rõ ràng: `Intent → Schema Linking → SQL Gen → Validator → HITL → Executor → Formatter` |
| **Dual-Model LLM** | Qwen2.5-72B (suy luận) + Qwen2.5-Coder-32B (sinh SQL, temp=0) |
| **Three-Tier Memory** | Short-term (phân loại lỗi) · Temporary (Bellman pruning) · Long-term (DAIL-SQL few-shot) |
| **Self-Correction Loop** | Tự phát hiện và sửa lỗi SQL tối đa 3 lần qua 5-layer validator |
| **HITL Gate** | Chặn truy vấn chi phí lớn (>1M rows, >500 MB), yêu cầu Admin duyệt |
| **SSE Streaming UI** | Nhật ký suy nghĩ Agent phát trực tiếp lên giao diện qua Server-Sent Events |
| **ELT Pipeline** | Nạp dữ liệu Full-refresh / Incremental từ MSSQL, PostgreSQL, MySQL, SQLite vào DuckDB |
| **Airflow Orchestration** | DAG `@daily`: Ingest → dbt Run → dbt Test → Qdrant Sync → SLA Audit |
| **Data Lineage** | Đồ thị nguồn gốc dữ liệu: Raw → Staging → Mart → Metrics → Consumers |
| **Data Quality** | Tự động kiểm định không null, unique, FK, range qua dbt test |
| **RBAC Auth** | JWT + Supabase, phân quyền `admin` / `analyst`, ẩn cột sensitive |
| **Auto-Bootstrap** | Tự động crawl schema CSDL bất kỳ → sinh YAML config + dbt models + Qdrant index |
| **Benchmark Suite** | Đánh giá Exact Match, Execution Match qua 22 test cases tự động |

---

## 🏗️ Kiến trúc tổng thể

```
Browser / User
     │  HTTPS / SSE
     ▼
┌─────────────────────────────────────────────────┐
│         FRONTEND  (Next.js 16 · React 19)        │
│  Chat · Catalog · Lineage · Benchmark · HITL UI  │
└──────────────────────┬──────────────────────────┘
                       │ REST API / SSE  :8000
                       ▼
┌─────────────────────────────────────────────────┐
│          WEB API  (FastAPI + Uvicorn)            │
│  /api/chat   /api/domains   /api/health          │
└──────────┬────────────────────────┬─────────────┘
           │                        │ Domain mgmt
           ▼                        ▼
┌──────────────────┐   ┌───────────────────────────┐
│   AI AGENT        │   │      CORE SERVICES        │
│  (LangGraph)      │   │  DomainManager (YAML)     │
│                   │   │  DatabaseIntrospector     │
│  intent_node      │   │  AutoDbtGenerator         │
│  schema_linking   │   │  LineageService           │
│  sql_generator    │   │  DataQualityChecker       │
│  plan_validator   │   │  DataIngestionService     │
│  hitl_gate        │   │  normalizer / glossary    │
│  executor         │   └───────────────────────────┘
│  resp_formatter   │
└────────┬──────────┘
         ▼
┌─────────────────────────────────────────────────┐
│       DATA WAREHOUSE  (DuckDB – embedded)        │
│  Raw → stg_* (dbt staging) → mart_* (dbt marts) │
│  _ingestion_sync_log  (audit & freshness)        │
└────────────────────┬────────────────────────────┘
                     │ embeddings
                     ▼
┌─────────────────────────────────────────────────┐
│      SEMANTIC LAYER  (Qdrant Vector DB)          │
│  schema_<domain> · metrics_<domain>              │
│  categories_<domain> · few_shot_sql_plans        │
│  Model: BAAI/bge-m3  (multilingual, 1024-dim)   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│      ORCHESTRATION  (Apache Airflow)             │
│  DAG mssql_to_duckdb_pipeline  (@daily)         │
│  DAG duckdb_maintenance        (weekly)         │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Khởi động nhanh (Quick Start)

### Yêu cầu

| Công cụ | Phiên bản |
|---------|-----------|
| Python | 3.11+ |
| Node.js | 18+ |
| Docker Desktop | latest |

### 1. Docker Compose (Recommended)

```bash
# Sao chép biến môi trường
cp .env.example .env
# Chỉnh sửa .env: LLM API keys, Qdrant, Supabase...

# Khởi động toàn bộ stack (Backend + Qdrant)
make up

# Xem logs backend
make logs
```

### 2. Phát triển cục bộ (Local Development)

```powershell
# ── Backend ──────────────────────────────────
python -m venv .venv
.venv\Scripts\activate
cd backend
pip install -r requirements.txt

# Chạy Qdrant Vector DB
docker run -p 6333:6333 -v ./data/qdrant_db:/qdrant/storage qdrant/qdrant

# Khởi động FastAPI server
python run_server.py
# → http://localhost:8000/docs

# ── Frontend ─────────────────────────────────
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 3. Seed dữ liệu ban đầu

```powershell
# Index semantic layer vào Qdrant
python backend/scripts/sync_qdrant_semantic_index.py --domain vietnam_ecommerce

# Nạp dữ liệu mẫu vào DuckDB
python backend/scripts/ingest_to_duckdb.py --source "mssql://..." --domain vietnam_ecommerce

# Chạy dbt để tạo staging/marts
cd infra/dbt && dbt run --target dev && dbt test --target dev
```

### 4. Airflow

```powershell
cd infra/airflow
.\start-airflow.ps1
# → http://localhost:8080  (admin / admin)
```

> **Endpoints truy cập:**
> - 🌐 Frontend UI: `http://localhost:3000`
> - 🔌 Backend REST / Swagger: `http://localhost:8000/docs`
> - 🗄️ Qdrant Dashboard: `http://localhost:6333/dashboard`
> - ✈️ Airflow UI: `http://localhost:8080`

---

## 📁 Cấu trúc thư mục

```
project-root/
│
├── backend/                           # FastAPI Python Backend
│   ├── app/
│   │   ├── agent/                     # AI Agent (LangGraph)
│   │   │   ├── graph.py               # AgentOrchestrator + StateGraph
│   │   │   ├── state.py               # AgentState (Pydantic)
│   │   │   ├── llm_client.py          # DualModelLLM gateway (OpenAI-compat.)
│   │   │   ├── nodes/                 # 7 Agent Nodes
│   │   │   │   ├── intent_node.py
│   │   │   │   ├── schema_linking_node.py
│   │   │   │   ├── sql_generator.py
│   │   │   │   ├── plan_validator.py
│   │   │   │   ├── hitl_node.py
│   │   │   │   ├── executor_node.py
│   │   │   │   └── response_formatter.py
│   │   │   └── memory/
│   │   │       └── three_tier_memory.py   # Short/Temp/Long-term memory
│   │   │
│   │   ├── api/routers/
│   │   │   ├── chat.py                # Chat + SSE Streaming
│   │   │   ├── domains.py             # Domain management
│   │   │   └── health.py              # Health checks
│   │   │
│   │   ├── core/
│   │   │   ├── config.py              # AppSettings (pydantic-settings)
│   │   │   ├── auth.py                # JWT + RBAC + Supabase
│   │   │   ├── ingestion_service.py   # ELT DataIngestionService
│   │   │   ├── domain_manager.py      # Domain registry (singleton)
│   │   │   ├── introspection.py       # DB schema reflection
│   │   │   ├── dbt_generator.py       # Auto dbt model codegen
│   │   │   ├── dbt_loader.py          # dbt manifest.json loader
│   │   │   ├── lineage_service.py     # Data lineage graph
│   │   │   ├── dq_checker.py          # Data quality rules
│   │   │   ├── normalizer.py          # Vietnamese NLP normalizer
│   │   │   ├── glossary.py            # Business glossary
│   │   │   └── logger.py
│   │   │
│   │   ├── db/
│   │   │   ├── duckdb_client.py       # DuckDB embedded client
│   │   │   ├── sqlalchemy_client.py   # SQLAlchemy multi-DB
│   │   │   └── warehouse_client.py    # MultiDBWarehouseRouter
│   │   │
│   │   ├── rag/
│   │   │   ├── profiling_graph.py     # BilingualDataProfilingGraph
│   │   │   ├── embeddings.py          # BGEM3EmbeddingFunction
│   │   │   └── qdrant_provider.py     # Qdrant client factory
│   │   │
│   │   ├── schemas/api.py             # Pydantic Request/Response schemas
│   │   └── main.py                    # FastAPI entrypoint
│   │
│   ├── domains/                       # 19 Domain YAML Configs
│   │   ├── vietnam_ecommerce/         # domain.yaml · schema.yaml · metrics.yaml
│   │   ├── banking/  ├── crm_analytics/  ├── logistics/
│   │   ├── fmcg_sales/  ├── education/  ├── adventure_works/
│   │   ├── coffee_shop/  ├── employees_churn/  ├── hospital_survey/
│   │   ├── mobile_games/  ├── nyc_green_taxi/  ├── pixar_legacy/
│   │   ├── retails/  ├── skytrax/  ├── social_media/  └── web_analytics/
│   │
│   ├── data/
│   │   └── long_term_memory.json      # Persisted Good/Bad Plans
│   │
│   └── tests/                         # 22 test files (pytest)
│       ├── test_agent_graph.py
│       ├── test_api_endpoints.py
│       ├── test_plan_validator.py
│       ├── test_steiner_tree_join.py
│       ├── test_multi_domain.py
│       └── ...
│
├── frontend/                          # Next.js 16 · React 19 · TypeScript
│   └── src/
│       ├── components/                # ChatViewport, AssistantMessage, HitlModal...
│       ├── hooks/                     # useChatStream
│       ├── context/                   # AuthContext (Supabase)
│       └── types/
│
├── infra/
│   ├── airflow/                       # Apache Airflow (LocalExecutor)
│   │   └── dags/
│   │       ├── dag_mssql_to_duckdb_pipeline.py   # @daily ELT
│   │       └── dag_duckdb_maintenance.py          # weekly VACUUM
│   │
│   ├── dbt/                           # dbt Core project
│   │   ├── models/staging/            # stg_* views
│   │   └── models/marts/              # mart_* / fct_* tables
│   │
│   └── supabase/                      # Self-hosted Supabase (Auth)
│
├── data/
│   ├── warehouse.duckdb               # Main analytics warehouse (embedded)
│   └── qdrant_db/                     # Qdrant local storage
│
├── evaluation/                        # Benchmark & Evaluation
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## 🤖 AI Agent Pipeline (LangGraph)

### Luồng 7 Node

```
[1] intent_node         — DDL block · Domain routing · NLP normalize · Complexity (EASY/MEDIUM/COMPLEX)
[2] schema_linking_node — Qdrant semantic search · NetworkX graph · Minimum Steiner Tree · Fan-trap detect
[3] sql_generator       — DAIL-SQL few-shot · CTE decomposition · Long-term memory reuse
[4] plan_validator  ◄── self-correction loop (max 3 retries)
    Layer 1: Grammar & Read-Only
    Layer 2: Cartesian Product
    Layer 3: Fan-Trap (SUM/COUNT trên 1-N join)
    Layer 4: Column Existence
    Layer 5: EXPLAIN dry-run cost
[5] hitl_gate           — Kích hoạt nếu cost > threshold → PENDING (chờ Admin)
[6] executor_node       — Thực thi SQL · Lưu Good Plan vào LongTermMemory
[7] response_formatter  — Tóm tắt tiếng Việt · Chart config (Recharts) · Follow-up
```

### Dual-Model LLM

| Role | Model | Nhiệm vụ |
|------|-------|----------|
| `reasoner` | `Qwen/Qwen2.5-72B-Instruct` | Intent, clarification, response formatting |
| `coder` | `Qwen/Qwen2.5-Coder-32B-Instruct` | SQL generation, CTE decomposition, temp=0 |

Hỗ trợ bất kỳ OpenAI-compatible API: **vLLM · Ollama · Together AI · OpenRouter**

### Three-Tier Memory

| Tầng | Cơ chế | Mục đích |
|------|--------|----------|
| **Short-Term** | 3 ngăn lỗi (GRAMMAR · SEMANTIC · DATA) | LLM tự sửa SQL theo loại lỗi |
| **Temporary** | Bellman Equation `v(St) = R + γ·v(St+1)` γ=0.9 | Cắt tỉa nhánh bế tắc |
| **Long-Term** | DAIL-SQL Good/Bad Plans + Qdrant vector index | Few-shot reuse xuyên phiên |

---

## 🌐 API Reference

### `/api/chat`

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/chat/query` | POST | Gửi câu hỏi, nhận response đồng bộ |
| `/chat/stream` | GET | SSE stream nhật ký suy nghĩ Agent |
| `/chat/hitl/{session_id}/decision` | POST | Gửi quyết định HITL (approve/reject) |
| `/chat/history/{session_id}` | GET | Lịch sử hội thoại |
| `/chat/feedback` | POST | Đánh giá chất lượng (👍/👎) → học vào LongTermMemory |

### `/api/domains`

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/domains` | GET | Liệt kê toàn bộ domains |
| `/domains/{id}` | GET | Chi tiết bảng/cột/metrics |
| `/domains/switch` | POST | Đổi domain active |
| `/domains/inspect-connection` | POST | Khám phá CSDL (list databases & schemas) |
| `/domains/connect` | POST | Kết nối CSDL mới → auto-generate DomainConfig |
| `/domains/{id}/ingest` | POST | Kích hoạt ELT ingestion thủ công |
| `/domains/{id}/ingest/history` | GET | Lịch sử đồng bộ |
| `/domains/{id}/dbt/generate` | POST | Sinh dbt models từ DomainConfig |
| `/domains/{id}/dbt/compile` | POST | `dbt compile` → cập nhật manifest.json |
| `/domains/{id}/dbt/run` | POST | `dbt run` → materialize models |
| `/domains/{id}/dbt/test` | POST | `dbt test` → data quality |
| `/domains/{id}/lineage` | GET | Đồ thị Data Lineage đa tầng |
| `/domains/{id}/lineage/impact` | GET | Impact Analysis (blast radius) |
| `/domains/{id}/quality` | GET | Báo cáo Data Quality |
| `/domains/{id}/contract` | GET | Data Contract & SLA Governance |
| `/domains/{id}/freshness` | GET | Trạng thái Data Freshness (SLA) |

### `/api/health`

| Endpoint | Mô tả |
|----------|-------|
| `GET /health` | Trạng thái tổng thể |
| `GET /health/warehouse` | DuckDB version, file size |
| `GET /health/vector-db` | Qdrant collections status |

---

## 🗄️ Data Domains (19 Domains)

| Domain ID | Lĩnh vực |
|-----------|---------|
| `vietnam_ecommerce` | Thương mại điện tử Việt Nam (Shopee, TikTok Shop) |
| `ecommerce` / `e_commerce` | E-commerce tổng quát |
| `banking` | Ngân hàng, giao dịch tài chính |
| `crm_analytics` | Quản lý khách hàng (CRM) |
| `logistics` | Vận tải, chuỗi cung ứng |
| `fmcg_sales` | Hàng tiêu dùng nhanh (FMCG) |
| `education` | Giáo dục |
| `adventure_works` | Microsoft AdventureWorks dataset |
| `coffee_shop` | Chuỗi cửa hàng cà phê |
| `employees_churn` | Phân tích nghỉ việc nhân sự |
| `hospital_survey` | Khảo sát bệnh viện |
| `mobile_games` | Game di động |
| `nyc_green_taxi` | Dữ liệu taxi NYC |
| `pixar_legacy` | Dữ liệu phim Pixar |
| `retails` | Bán lẻ |
| `skytrax` | Đánh giá hãng hàng không |
| `social_media` | Mạng xã hội |
| `web_analytics` | Phân tích web |

---

## ⚙️ Cấu hình môi trường

```dotenv
# DATA WAREHOUSE
DUCKDB_PATH=./data/warehouse.duckdb
WAREHOUSE_BACKEND=duckdb

# EXTERNAL DB (nguồn dữ liệu để ingest)
EXTERNAL_DATABASE_URL=mssql+pymssql://user:pass@host/dbname

# DUAL-MODEL LLM (OpenAI-compatible)
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=EMPTY
MODEL_REASONER=Qwen/Qwen2.5-72B-Instruct
MODEL_CODER=Qwen/Qwen2.5-Coder-32B-Instruct

# VECTOR DB (Qdrant)
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_MODEL=BAAI/bge-m3
HF_TOKEN=hf_xxx

# WEB SERVER
APP_ENV=development
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000

# HITL GUARDRAILS
HITL_SCAN_TABLETS_THRESHOLD=50
HITL_ROW_COUNT_THRESHOLD=1000000
HITL_ESTIMATED_BYTES_MB_THRESHOLD=500

# AUTH (Supabase self-hosted)
SUPABASE_URL=http://localhost:54321
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
```

---

## 🛡️ Bảo mật & Guardrails

### Pre-execution Security
Chặn DDL/DML ngay tại `intent_node` trước bất kỳ xử lý nào:
```
DROP TABLE · DELETE FROM · TRUNCATE · ALTER TABLE · UPDATE SET · INSERT INTO
→ risk_level = "BLOCKED" → kết thúc ngay lập tức
```

### 5-Layer Plan Validator
```
Layer 1  Grammar & Read-Only       → Block DDL/DML keywords
Layer 2  Cartesian Product         → Block JOIN thiếu ON clause
Layer 3  Fan-Trap                  → Warn SUM/COUNT trên 1-N joins
Layer 4  Column Existence          → Reject unknown columns (tiếng Việt)
Layer 5  EXPLAIN Dry-Run           → Ước tính cost, trigger HITL
```

### RBAC
| Role | Quyền |
|------|-------|
| `admin` | Toàn quyền, xem sensitive columns, approve HITL, quản lý domains |
| `analyst` | Chỉ đọc, ẩn cột `is_sensitive: true` |

---

## 📊 Makefile Commands

```bash
make up            # Khởi động full stack (Docker Compose)
make down          # Dừng containers
make logs          # Xem logs backend
make build         # Build backend Docker image
make load-data     # Nạp dữ liệu Parquet vào DuckDB (3.5M records)
make benchmark     # Chạy evaluation benchmark
make test          # Chạy pytest (22 test files)
make supabase-up   # Khởi động Supabase self-hosted
make supabase-down # Dừng Supabase
```

---

## 🔬 Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| **AI Agent** | LangGraph, OpenAI-compatible LLM (Qwen2.5) |
| **Embedding** | BAAI/bge-m3 (multilingual, 1024-dim) |
| **Vector DB** | Qdrant + LlamaIndex adapter |
| **Backend** | FastAPI, Uvicorn, Pydantic v2 |
| **Data Warehouse** | DuckDB (embedded, OLAP) |
| **ELT** | SQLAlchemy, pymssql, pandas, pyarrow |
| **Data Transform** | dbt-core + dbt-duckdb |
| **Orchestration** | Apache Airflow (LocalExecutor) |
| **Frontend** | Next.js 16, React 19, TypeScript, Chart.js, @xyflow/react |
| **Auth** | Supabase self-hosted, JWT, PyJWT |
| **Graph Algorithm** | NetworkX (Minimum Steiner Tree) |
| **NLP** | Vietnamese normalizer, Business Glossary |
| **Testing** | pytest, 22 test modules |

---

## 📈 Monitoring & Observability

- **Health API**: `/api/health`, `/api/health/warehouse`, `/api/health/vector-db`
- **Data Freshness**: `/api/domains/{id}/freshness` — đọc từ `_ingestion_sync_log`
- **Airflow UI**: `http://localhost:8080` — lịch sử DAG, task logs, retry
- **SSE Streaming**: Mỗi node gửi step log theo thời gian thực qua `/api/chat/stream`

---

## 📚 Tài liệu chi tiết

| Tài liệu | Nội dung |
|----------|---------|
| [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) | Kiến trúc tổng thể, luồng dữ liệu, mô tả chi tiết từng thành phần |
| [ANALYSIS_AND_TECH_STACK.md](./ANALYSIS_AND_TECH_STACK.md) | Phân tích bài toán, lý do lựa chọn tech stack |
| [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md) | Hướng dẫn deploy lên Render.com |

---

## 📄 License

[Apache License 2.0](./LICENSE)
