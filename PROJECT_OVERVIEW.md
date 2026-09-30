# AI-Agent Text-to-SQL Self-Service Analytics

> **Tài liệu Kiến trúc & Quy trình Tổng thể**  
> Phiên bản: 2.0.0 | Cập nhật: 2026-09

---

## Mục lục

1. [Tổng quan Dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc Tổng thể](#2-kiến-trúc-tổng-thể)
3. [Luồng Dữ liệu – ELT Pipeline](#3-luồng-dữ-liệu--elt-pipeline)
4. [Luồng Truy vấn – AI Agent](#4-luồng-truy-vấn--ai-agent)
5. [Các Thành phần Chi tiết](#5-các-thành-phần-chi-tiết)
6. [Hệ thống Domain](#6-hệ-thống-domain)
7. [Bộ Nhớ Ba Tầng](#7-bộ-nhớ-ba-tầng-three-tier-memory)
8. [Bảo mật & Guardrails](#8-bảo-mật--guardrails)
9. [Cấu trúc Thư mục](#9-cấu-trúc-thư-mục)
10. [Cấu hình Môi trường](#10-cấu-hình-môi-trường)
11. [Hướng dẫn Khởi chạy](#11-hướng-dẫn-khởi-chạy)
12. [Monitoring & Observability](#12-monitoring--observability)
13. [Lý do Lựa chọn Kiến trúc](#13-lý-do-lựa-chọn-kiến-trúc)

---

## 1. Tổng quan Dự án

**AI-Agent Text-to-SQL Self-Service Analytics** là hệ thống trợ lý phân tích dữ liệu thông minh, cho phép người dùng nghiệp vụ đặt câu hỏi bằng ngôn ngữ tự nhiên (tiếng Việt và tiếng Anh) và nhận kết quả phân tích, biểu đồ trực quan từ kho dữ liệu — **không cần viết SQL**.

### Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| **Natural Language → SQL** | Chuyển câu hỏi tiếng Việt/Anh thành SQL chuẩn, thực thi trên DuckDB |
| **Multi-Domain** | Hỗ trợ nhiều lĩnh vực (E-commerce, BĐS, Y tế...) qua cấu hình YAML |
| **Self-Correction Loop** | Tự phát hiện lỗi và sửa SQL tối đa 3 lần trước khi dừng |
| **Streaming UI** | Truyền nhật ký suy nghĩ thời gian thực (SSE) lên giao diện |
| **Data Lineage** | Theo dõi nguồn gốc dữ liệu từ bảng gốc → staging → mart |
| **HITL Gate** | Chặn và yêu cầu duyệt thủ công với truy vấn nguy hiểm |
| **ELT Pipeline** | Tự động nạp dữ liệu từ SQL Server / Postgres / MySQL vào DuckDB |
| **Semantic Indexing** | Đồng bộ schema, metrics vào Vector DB để cải thiện Schema Linking |
| **Data Quality** | Kiểm tra chất lượng dữ liệu tự động qua dbt test |
| **Benchmark** | Đánh giá độ chính xác SQL (Exact Match, Execution Match) |

---

## 2. Kiến trúc Tổng thể

```
┌──────────────────────────────────────────────────────────────┐
│                       USER / BROWSER                         │
└──────────────────────────┬───────────────────────────────────┘
                           │  HTTPS / SSE
                           ▼
┌──────────────────────────────────────────────────────────────┐
│             FRONTEND  (Next.js 14 – Port 3000)               │
│                                                              │
│  Chat View  |  Catalog View  |  Lineage View  |  Benchmark  │
└──────────────────────────┬───────────────────────────────────┘
                           │  REST API / SSE  (Port 8000)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│               WEB API  (FastAPI + Uvicorn)                   │
│  /api/chat      /api/domains      /api/health   /api/auth    │
└──────────┬─────────────────────────────┬─────────────────────┘
           │ invoke / stream              │  domain mgmt
           ▼                             ▼
┌────────────────────┐       ┌───────────────────────────────┐
│    AI AGENT        │       │       CORE SERVICES           │
│  (LangGraph 0.x)   │       │                               │
│                    │       │  DomainManager  (YAML reg)    │
│  intent_clarifier  │       │  DatabaseIntrospector         │
│  schema_linking    │       │  AutoDbtGenerator             │
│  sql_generator     │       │  LineageService               │
│  plan_validator    │       │  DataQualityChecker           │
│  hitl_gate         │       │  DataIngestionService         │
│  executor          │       │  normalizer / glossary        │
│  resp_formatter    │       └───────────────────────────────┘
└─────────┬──────────┘
          │ query
          ▼
┌──────────────────────────────────────────────────────────────┐
│              DATA WAREHOUSE  (DuckDB – embedded)             │
│                                                              │
│  Raw Tables (ingested) → Staging (dbt stg_) → Marts (mart_) │
│  _ingestion_sync_log  (audit & freshness)                    │
└──────────────────────────────┬───────────────────────────────┘
                               │ reads metadata
                               ▼
┌──────────────────────────────────────────────────────────────┐
│             SEMANTIC / VECTOR LAYER  (Qdrant)                │
│                                                              │
│  schema_<domain>      – table/column embeddings             │
│  metrics_<domain>     – business metric vectors             │
│  categories_<domain>  – categorical value index             │
│  Model: BAAI/bge-m3  (multilingual, 1024-dim)               │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│         ORCHESTRATION  (Apache Airflow – LocalExecutor)      │
│                                                              │
│  DAG: mssql_to_duckdb_pipeline  (@daily)                    │
│    1. check_db_connectivity                                  │
│    2. ingest_source_to_duckdb   (DataIngestionService)      │
│    3. dbt_run_marts             (BashOperator)              │
│    4. dbt_test_quality          (BashOperator)              │
│    5. sync_semantic_index       (Qdrant embeddings)         │
│    6. update_data_freshness     (SLA audit log)             │
│    7. pipeline_summary                                       │
│                                                              │
│  DAG: duckdb_maintenance  (weekly / on-demand)              │
│    CHECKPOINT, VACUUM ANALYZE, PRAGMA optimize              │
│                                                              │
│  UI: http://localhost:8080  |  Metadata DB: Postgres :54323 │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│        EXTERNAL DATABASE  (Source of Truth)                  │
│   SQL Server / PostgreSQL / MySQL / SQLite / ClickHouse...  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Luồng Dữ liệu – ELT Pipeline

```
External DB          Airflow DAG (@daily)             DuckDB Warehouse
(MSSQL/PG/MySQL)
     │
     │  1. CHECK CONNECTIVITY (SELECT 1, timeout 10s)
     │
     │  2. INGEST (DataIngestionService)
     │     Full-refresh OR Incremental (watermark_column)  ──▶  raw tables
     │     Batch: 50,000 rows/chunk
     │     Audit: _ingestion_sync_log
     │
     │           3. DBT RUN
     │           staging/ models (stg_*)  ──▶  DuckDB views
     │           marts/   models (mart_*) ──▶  DuckDB tables
     │
     │           4. DBT TEST
     │           not_null, unique, FK checks
     │
     │           5. SYNC QDRANT
     │           Schema + Metrics → BAAI/bge-m3 → Qdrant upsert
     │
     │           6. DATA FRESHNESS
     │           Đọc _ingestion_sync_log → SLA status
     │
     │           7. PIPELINE SUMMARY (XCom aggregation)
```

### Chế độ Sync

| Mode | Mô tả | Khi nào dùng |
|------|-------|--------------|
| `full_refresh` | Xóa toàn bộ và nạp lại từ đầu | Bảng nhỏ (< 1M rows), initial load |
| `incremental` | Chỉ lấy dòng mới hơn `watermark_column` | Bảng lớn, production daily |

---

## 4. Luồng Truy vấn – AI Agent

### LangGraph StateGraph (7 Nodes)

```
START
  │
  ▼
[1] intent_clarifier
    • Pre-execution Security Guardrail (block DDL/DML)
    • Domain Detection (keyword + semantic routing)
    • Time/Currency/Limit normalization (GenericVietnameseNormalizer)
    • Vietnamese Business Glossary expansion
    • LLM phân loại: EASY / MEDIUM / COMPLEX
    • Clarification Loop: hỏi lại nếu câu hỏi mơ hồ
    Model: Qwen 2.5-72B-Instruct (Reasoner)
    │
    ├── [clarification_needed OR blocked] ──▶ END
    │
    ▼
[2] schema_linking
    • Query Qdrant: semantic search trên schema/metrics/categories
    • NetworkX Graph: xây đồ thị quan hệ bảng theo FK
    • Minimum Steiner Tree: tìm JOIN path tối ưu
    • Fan-Trap Detection: cảnh báo JOIN 1-N
    • Output: SchemaContext (tables, columns, JOIN clauses)
    │
    ▼
[3] sql_generator
    • Đọc Long-Term Memory: tìm Good Plans tương tự
    • Đọc Short-Term Memory: lấy error feedback
    • CTE decomposition cho COMPLEX queries
    • Sinh SQL dựa trên SchemaContext
    Model: Qwen 2.5-Coder-32B-Instruct (Coder, temp=0)
    │
    ▼
[4] plan_validator  ◄──────────────────────────────┐
    5-Layer Guardrails (xem mục 8)                 │
    │                                              │
    ├── [is_valid=False, retry<3, not stuck] ───────┘ (self-correction)
    ├── [stuck OR max_retries] ──▶ END
    │
    ▼
[5] hitl_gate
    • Kích hoạt nếu EXPLAIN vượt ngưỡng (tablets/rows/bytes)
    ├── [requires_hitl AND !approved] ──▶ END (PENDING)
    │
    ▼
[6] executor
    • Thực thi SQL trên DuckDB / Target DB
    • Thu thập query_result, column_names
    • Lưu Good Plan vào Long-Term Memory
    │
    ▼
[7] response_formatter
    • Tóm tắt insights bằng tiếng Việt
    • Sinh chart_config (Recharts JSON)
    • Gợi ý follow-up questions
    Model: Qwen 2.5-72B-Instruct (Reasoner)
    │
    ▼
  END → ChatResponse (SQL + Results + Chart + Summary)
```

### AgentState – State xuyên suốt pipeline

```python
class AgentState(BaseModel):
    session_id, user_query, domain_id
    normalized_query, extracted_entities
    conversation_history, user_id, user_role     # Multi-turn & RBAC
    clarification_needed, clarification_question  # Clarification Loop
    complexity_level, decomposition_plan          # DIN-SQL inspired
    schema_context                                # Steiner Tree output
    sql_query, validation_result                  # Generated & validated SQL
    retry_count, max_retries, error_history       # Self-Correction Loop
    requires_hitl, hitl_approved                  # HITL Gate
    query_result, column_names                    # Execution output
    final_response, chart_config                  # Formatted output
    execution_time_ms, steps_executed             # Observability
```

---

## 5. Các Thành phần Chi tiết

### 5.1 Frontend (Next.js)

**Tech Stack**: Next.js 14, React, TypeScript, Tailwind CSS

| Component | Chức năng |
|-----------|-----------|
| `MainApp.tsx` | Shell điều phối tabs, domain selector, auth guard |
| `ChatViewport.tsx` | Hiển thị hội thoại + SSE streaming |
| `AssistantMessage.tsx` | Render SQL, bảng kết quả, biểu đồ Recharts |
| `FloatingPrompt.tsx` | Input box người dùng |
| `SplitCanvas.tsx` | Layout 2 cột: chat + SQL viewer |
| `CatalogView.tsx` | Duyệt schema, bảng, cột của domain |
| `LineageView.tsx` | Đồ thị nguồn gốc dữ liệu |
| `BenchmarkView.tsx` | Dashboard đánh giá độ chính xác SQL |
| `HitlModal.tsx` | Duyệt thủ công khi HITL kích hoạt |
| `DomainSelector.tsx` | Chọn domain nghiệp vụ hiện hoạt |

**Hook & Context:**
- `useChatStream` – Quản lý SSE streaming, session store, message history
- `AuthContext` – Xác thực JWT với Supabase

---

### 5.2 Web API (FastAPI)

**Base URL**: `http://localhost:8000/api`

#### `/api/chat` – Chat & SSE Streaming

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/chat/query` | POST | Gửi câu hỏi, nhận response đồng bộ |
| `/chat/stream` | GET | SSE stream nhật ký suy nghĩ Agent |
| `/chat/hitl/{session_id}/decision` | POST | Gửi quyết định HITL (approve/reject) |
| `/chat/history/{session_id}` | GET | Lấy lịch sử hội thoại |
| `/chat/sessions` | GET | Danh sách sessions hiện tại |

#### `/api/domains` – Domain Management

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/domains` | GET | Liệt kê toàn bộ domains |
| `/domains/{id}` | GET | Chi tiết bảng/cột/metrics |
| `/domains/{id}/switch` | POST | Đổi domain hiện hoạt |
| `/domains/{id}/bootstrap` | POST | Kết nối DB mới, auto-generate YAML |
| `/domains/{id}/freshness` | GET | Trạng thái Data Freshness SLA |
| `/domains/{id}/lineage` | GET | Đồ thị lineage |
| `/domains/{id}/dq` | GET | Báo cáo Data Quality |
| `/domains/{id}/ingest` | POST | Kích hoạt Ingestion thủ công |

#### `/api/health` – Health Checks

| Endpoint | Mô tả |
|----------|-------|
| `/health` | Trạng thái tổng thể |
| `/health/warehouse` | Kiểm tra DuckDB |
| `/health/vector-db` | Kiểm tra Qdrant |

---

### 5.3 AI Agent (LangGraph)

**File**: `backend/app/agent/graph.py`

#### DualModelLLM

| Role | Model mặc định | Nhiệm vụ |
|------|---------------|---------|
| `reasoner` | `Qwen/Qwen2.5-72B-Instruct` | Intent, clarification, response formatting |
| `coder` | `Qwen/Qwen2.5-Coder-32B-Instruct` | SQL generation, CTE decomposition |

- Giao tiếp qua **OpenAI-compatible REST API** (vLLM, Ollama, Together AI, OpenRouter)
- `temperature=0.0` cho `coder` (deterministic), cao hơn cho `reasoner`
- Hỗ trợ **mock handler** cho unit test offline

---

### 5.4 RAG & Semantic Layer

**Files**: `backend/app/rag/`

#### Embedding Model

```
BAAI/bge-m3
- Multilingual (Tiếng Việt + English native support)
- 1024 dimensions
- Wrapper: BGEM3EmbeddingFunction
- LlamaIndex adapter: LlamaIndexBGEM3Embedding
```

#### BilingualDataProfilingGraph

**File**: `backend/app/rag/profiling_graph.py`

```
1. YAML Domain Config
   └─▶ Đọc TableProfile, ColumnProfile, RelationshipProfile

2. Qdrant Vector Search
   ├─▶ schema_<domain>      – "table.column – vn_name – description – synonyms"
   ├─▶ metrics_<domain>     – "metric_id – vn_terms – sql_expression"
   └─▶ categories_<domain>  – "table.column – categorical values"

3. NetworkX Graph
   └─▶ Node: Table | Edge: ForeignKey (weighted)

4. Minimum Steiner Tree
   └─▶ Tìm cây nối tối thiểu giữa các bảng cần thiết
       → Sinh mệnh đề JOIN chuẩn: INNER/LEFT JOIN ... ON ...
```

---

### 5.5 Data Warehouse (DuckDB + dbt)

#### DuckDB

- **File**: `data/warehouse.duckdb` (embedded, không cần server)
- **Client**: `backend/app/db/duckdb_client.py`
- **Multi-connection safe**: detect file lock, retry với backoff
- `engine.dispose()` sau mỗi ingestion (tránh file lock trên Windows)

#### MultiDBWarehouseRouter

**File**: `backend/app/db/warehouse_client.py`

```
URL Pattern → Client Type
─────────────────────────────────────────────────────────
*.duckdb / *.db (file)        → DuckDBClient
duckdb:///:memory:            → DuckDBClient (in-memory)
postgresql:// / postgres://   → SQLAlchemyClient
mysql://                      → SQLAlchemyClient
sqlite:///                    → SQLAlchemyClient
mssql:// / mssql+pymssql://   → SQLAlchemyClient
clickhouse:// / oracle://     → SQLAlchemyClient
jdbc:sqlserver://             → parse_jdbc_url → SQLAlchemyClient
jdbc:postgresql://            → parse_jdbc_url → SQLAlchemyClient
```

#### dbt Models

```
infra/dbt/models/
├── staging/
│   └── vietnam_ecommerce/     ← stg_orders, stg_products, ...
└── marts/
    └── vietnam_ecommerce/     ← mart_revenue, mart_customers, ...
```

- **Target**: `dev` (DuckDB local file)
- **Chạy qua**: `BashOperator` trong Airflow DAG

---

### 5.6 Ingestion Service

**File**: `backend/app/core/ingestion_service.py`

#### Luồng Chi tiết

```python
DataIngestionService.sync_database(
    source_connection_url,  # bất kỳ DB nào
    source_schema,
    selected_tables,        # None = tất cả bảng
    sync_mode,              # full_refresh | incremental
    domain_id
)
  ↓
sync_table():
  1. Kết nối source qua SQLAlchemy (parse_jdbc_url nếu cần)
  2. Inspect schema → lấy danh sách cột
  3. Full-refresh: DROP TABLE → CREATE & INSERT
  4. Incremental: SELECT WHERE watermark_col > last_max_value
  5. Batch stream 50,000 rows → pd.DataFrame → DuckDB
  6. Ghi audit vào _ingestion_sync_log
  7. engine.dispose() (tránh Windows file lock)
```

#### Audit Log

```sql
CREATE TABLE _ingestion_sync_log (
    sync_id       VARCHAR(64) PRIMARY KEY,
    source_key    VARCHAR(100),
    domain_id     VARCHAR(100),
    table_name    VARCHAR(100),
    sync_mode     VARCHAR(20),     -- full_refresh / incremental
    rows_ingested BIGINT,
    duration_sec  DOUBLE,
    status        VARCHAR(20),     -- SUCCESS / FAILED
    error_message VARCHAR,
    executed_at   TIMESTAMP
);
```

---

### 5.7 Orchestration (Airflow)

**Dir**: `infra/airflow/`  
**Executor**: `LocalExecutor` (không dùng Celery/Redis – tối ưu RAM)

#### Docker Stack

| Container | Port | RAM Limit | Vai trò |
|-----------|------|-----------|---------|
| airflow-postgres | 54323 | 128 MB | Metadata DB (Alpine) |
| airflow-webserver | 8080 | 384 MB | Web UI |
| airflow-scheduler | - | 384 MB | Task scheduling |

**Ước tính tổng RAM**: ~900 MB

#### Volume Mounts

```
./dags          → /opt/airflow/dags
../../data      → /opt/airflow/data       (shared DuckDB file)
../../backend   → /opt/airflow/backend    (PYTHONPATH)
../../infra/dbt → /opt/airflow/infra/dbt  (dbt project)
```

#### DAG: `mssql_to_duckdb_pipeline`

```
Schedule: @daily | Tags: ingestion, duckdb, dbt, elt, qdrant, semantic

check_db_connectivity
    → ingest_source_to_duckdb   (PythonOperator)
    → dbt_run_marts             (BashOperator)
    → dbt_test_quality          (BashOperator)
    → sync_semantic_index       (PythonOperator)
    → update_data_freshness     (PythonOperator)
    → pipeline_summary          (PythonOperator)

XCom keys: ingestion_result, semantic_sync_result, freshness_result
```

#### DAG: `duckdb_maintenance`

```
Schedule: weekly / on-demand
Tasks: CHECKPOINT → VACUUM ANALYZE → PRAGMA optimize
```

---

### 5.8 Authentication (Supabase)

**Self-hosted Supabase**: `infra/supabase/`

**RBAC Roles:**

| Role | Quyền |
|------|-------|
| `admin` | Toàn quyền, xem sensitive columns, approve HITL |
| `analyst` | Chỉ đọc, ẩn cột `is_sensitive=True` |

**JWT Flow**: `POST /api/auth/token` → Bearer token → Header `Authorization: Bearer <token>`

---

## 6. Hệ thống Domain

Mỗi **Domain** là tập cấu hình YAML mô tả một lĩnh vực nghiệp vụ.

### Cấu trúc Domain YAML

```
backend/domains/<domain_id>/
├── domain.yaml    ← Metadata (display_name, description, keywords)
├── schema.yaml    ← Tables, columns, FK relationships
└── metrics.yaml   ← Business metrics (vn_terms, sql_expression)
```

### Ví dụ Schema YAML (`vietnam_ecommerce`)

```yaml
tables:
  orders:
    vn_name: "Đơn hàng"
    columns:
      order_id:     { data_type: BIGINT, is_primary_key: true }
      customer_id:  { data_type: BIGINT, foreign_key: "customers.id" }
      total_amount: { data_type: DOUBLE, vn_name: "Giá trị đơn hàng" }
relationships:
  - from_table: orders
    from_column: customer_id
    to_table: customers
    to_column: id
    cardinality: "N:1"
    weight: 1.0          # Dùng cho Steiner Tree cost
```

### Ví dụ Metrics YAML

```yaml
metrics:
  - metric_id: gmv
    vn_terms: ["Tổng giá trị hàng hóa", "GMV", "doanh thu"]
    sql_expression: "SUM(total_amount)"
    depends_on_tables: [orders]
```

### Domain Auto-Bootstrap

```
POST /api/domains/{id}/bootstrap
  ↓
DatabaseIntrospector.reflect_schema()   → đọc cấu trúc DB thực
AutoDbtGenerator.generate_models()      → sinh staging SQL models
DomainManager.save_yaml_config()        → ghi domain.yaml + schema.yaml
BilingualDataProfilingGraph.build()     → index lên Qdrant
```

---

## 7. Bộ Nhớ Ba Tầng (Three-Tier Memory)

**File**: `backend/app/agent/memory/three_tier_memory.py`

```
┌────────────────────────────────────────────────────────────┐
│  TIER 1: SHORT-TERM MEMORY (trong phiên)                  │
│                                                            │
│  Max 3 lỗi gần nhất, phân loại 3 ngăn:                   │
│  ├─ GRAMMAR:  syntax, unknown column, table error         │
│  ├─ SEMANTIC: fan-trap, order-by, logic error             │
│  └─ DATA:     data type, value mismatch                   │
│                                                            │
│  → Sinh error feedback prompt để LLM tự sửa SQL           │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  TIER 2: TEMPORARY MEMORY (trong phiên)                   │
│                                                            │
│  Bellman Equation: v(S_t) = R_{t+1} + γ * v(S_{t+1})     │
│  γ = 0.9 (discount factor)                                │
│                                                            │
│  → Cắt tỉa nhánh bế tắc (Bellman Pruning)                │
│  → Phát hiện kẹt vòng lặp → dừng sớm (is_stuck_in_loop) │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  TIER 3: LONG-TERM MEMORY (xuyên phiên)                   │
│                                                            │
│  Lưu Good Plans / Bad Plans / Common Knowledge            │
│  Persisted, chia sẻ giữa các session                      │
│                                                            │
│  → SQL Generator reuse Good Plans thành công             │
│  → Schema Linking học pattern JOIN tương tự              │
└────────────────────────────────────────────────────────────┘
```

---

## 8. Bảo mật & Guardrails

### Pre-execution Security (Intent Node)

Kiểm tra trước bất kỳ xử lý nào:

```python
BLOCKED_PATTERNS = [
    r"\bDROP\s+TABLE\b",     r"\bDELETE\s+FROM\b",
    r"\bTRUNCATE\s+TABLE\b", r"\bALTER\s+TABLE\b",
    r"\bUPDATE\s+\w+\s+SET\b", r"\bINSERT\s+INTO\b"
]
# → risk_level = "BLOCKED", ngay lập tức trả về END
```

### 5-Layer Plan Validator

```
Layer 1  Grammar & Read-Only      → Block DDL/DML keywords
Layer 2  Cartesian Product Detect → Block JOIN thiếu ON clause
Layer 3  Fan-Trap Validator        → Warn SUM/COUNT trên 1-N joins
Layer 4  Column Existence Check   → Reject unknown columns,
                                    dịch lỗi DB → tiếng Việt
Layer 5  EXPLAIN Dry-Run          → Ước tính cost, trigger HITL
```

### HITL Thresholds

```bash
HITL_SCAN_TABLETS_THRESHOLD       = 50          # số tablets
HITL_ROW_COUNT_THRESHOLD          = 1,000,000   # số dòng
HITL_ESTIMATED_BYTES_MB_THRESHOLD = 500         # megabytes
```

### Sensitive Column Masking

Cột `is_sensitive: true` trong schema.yaml → ẩn khỏi `analyst` role.

---

## 9. Cấu trúc Thư mục

```
project-root/
│
├── backend/                          # FastAPI Python Backend
│   ├── app/
│   │   ├── agent/                    # AI Agent (LangGraph)
│   │   │   ├── graph.py              # AgentOrchestrator, StateGraph
│   │   │   ├── state.py              # AgentState (Pydantic)
│   │   │   ├── llm_client.py         # DualModelLLM gateway
│   │   │   ├── nodes/                # 7 Agent Nodes
│   │   │   │   ├── intent_node.py
│   │   │   │   ├── schema_linking_node.py
│   │   │   │   ├── sql_generator.py
│   │   │   │   ├── plan_validator.py
│   │   │   │   ├── hitl_node.py
│   │   │   │   ├── executor_node.py
│   │   │   │   └── response_formatter.py
│   │   │   └── memory/
│   │   │       └── three_tier_memory.py
│   │   ├── api/routers/
│   │   │   ├── chat.py               # Chat & SSE API
│   │   │   ├── domains.py            # Domain management
│   │   │   └── health.py             # Health check
│   │   ├── core/
│   │   │   ├── config.py             # AppSettings (pydantic-settings)
│   │   │   ├── auth.py               # JWT, RBAC, Supabase
│   │   │   ├── ingestion_service.py  # ELT DataIngestionService
│   │   │   ├── domain_manager.py     # Domain registry (singleton)
│   │   │   ├── introspection.py      # DB schema reflection
│   │   │   ├── dbt_generator.py      # Auto dbt model codegen
│   │   │   ├── lineage_service.py    # Data lineage graph
│   │   │   ├── dq_checker.py         # Data quality rules
│   │   │   ├── normalizer.py         # Vietnamese NLP normalizer
│   │   │   └── glossary.py           # Business glossary
│   │   ├── db/
│   │   │   ├── duckdb_client.py      # DuckDB embedded client
│   │   │   ├── sqlalchemy_client.py  # SQLAlchemy multi-DB client
│   │   │   └── warehouse_client.py   # MultiDBWarehouseRouter
│   │   ├── rag/
│   │   │   ├── profiling_graph.py    # BilingualDataProfilingGraph
│   │   │   ├── embeddings.py         # BGEM3EmbeddingFunction
│   │   │   └── qdrant_provider.py    # Qdrant client factory
│   │   └── main.py                   # FastAPI entrypoint
│   ├── domains/                      # Domain YAML Configs
│   │   ├── vietnam_ecommerce/
│   │   │   ├── domain.yaml
│   │   │   ├── schema.yaml
│   │   │   └── metrics.yaml
│   │   └── ecommerce/
│   └── scripts/
│       ├── ingest_to_duckdb.py
│       ├── sync_qdrant_semantic_index.py
│       └── seed_benchmark_warehouse.py
│
├── frontend/                         # Next.js 14 Frontend
│   └── src/
│       ├── components/               # React components
│       ├── hooks/                    # useChatStream, ...
│       ├── context/                  # AuthContext
│       └── types/                    # TypeScript types
│
├── infra/
│   ├── airflow/                      # Apache Airflow
│   │   ├── docker-compose.airflow.yml
│   │   ├── Dockerfile
│   │   └── dags/
│   │       ├── dag_mssql_to_duckdb_pipeline.py
│   │       └── dag_duckdb_maintenance.py
│   ├── dbt/                          # dbt Project
│   │   ├── dbt_project.yml
│   │   ├── profiles.yml
│   │   └── models/
│   │       ├── staging/
│   │       └── marts/
│   └── supabase/                     # Supabase self-hosted
│
├── data/
│   ├── warehouse.duckdb              # Main analytics warehouse
│   └── qdrant_db/                    # Qdrant local storage
│
├── evaluation/                       # Benchmark & Evaluation
├── .env                              # Environment variables
├── .env.example
├── docker-compose.yml
└── Makefile
```

---

## 10. Cấu hình Môi trường

Sao chép từ `.env.example` → `.env`:

```dotenv
# DATA WAREHOUSE
DUCKDB_PATH=./data/warehouse.duckdb
WAREHOUSE_BACKEND=duckdb

# EXTERNAL DATABASE (nguồn dữ liệu cần ingest)
EXTERNAL_DATABASE_URL=mssql+pymssql://user:pass@host/dbname
# hoặc: postgresql://user:pass@host:5432/dbname
# hoặc: mysql+pymysql://user:pass@host/dbname

# DUAL-MODEL LLM GATEWAY
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=EMPTY
MODEL_REASONER=Qwen/Qwen2.5-72B-Instruct
MODEL_CODER=Qwen/Qwen2.5-Coder-32B-Instruct

# VECTOR DB (Qdrant)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_STORAGE_DIR=./data/qdrant_db
EMBEDDING_MODEL=BAAI/bge-m3
HF_TOKEN=hf_xxx

# WEB SERVER
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000

# HITL GUARDRAILS
HITL_SCAN_TABLETS_THRESHOLD=50
HITL_ROW_COUNT_THRESHOLD=1000000
HITL_ESTIMATED_BYTES_MB_THRESHOLD=500

# AUTHENTICATION (Supabase self-hosted)
SUPABASE_URL=http://localhost:54321
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

---

## 11. Hướng dẫn Khởi chạy

### Prerequisites

```
Python 3.11+
Node.js 18+
Docker Desktop (Airflow + Supabase)
Qdrant (local hoặc Docker)
```

### 1. Backend

```powershell
python -m venv .venv
.venv\Scripts\activate
cd backend
pip install -r requirements.txt
python run_server.py
# → http://localhost:8000/docs
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 3. Qdrant

```bash
docker run -p 6333:6333 \
  -v ./data/qdrant_db:/qdrant/storage \
  qdrant/qdrant
```

### 4. Seed dữ liệu ban đầu

```powershell
# Index domain vào Qdrant
python backend/scripts/sync_qdrant_semantic_index.py --domain vietnam_ecommerce

# Nạp dữ liệu mẫu vào DuckDB
python backend/scripts/ingest_to_duckdb.py --source "mssql://..." --domain vietnam_ecommerce

# Chạy dbt
cd infra/dbt
dbt run --target dev
dbt test --target dev
```

### 5. Airflow

```powershell
cd infra/airflow
.\start-airflow.ps1
# → http://localhost:8080 (admin / admin)
```

### 6. Kết nối CSDL mới (Bootstrap)

```bash
POST /api/domains/{id}/bootstrap
{
  "connection_url": "postgresql://user:pass@host/db",
  "domain_id": "my_domain"
}
# Auto-generates: YAML config + dbt staging models + Qdrant index
```

---

## 12. Monitoring & Observability

### Health Endpoints

| Endpoint | Thông tin |
|----------|-----------|
| `GET /api/health` | Trạng thái tổng thể |
| `GET /api/health/warehouse` | DuckDB version, file size, row counts |
| `GET /api/health/vector-db` | Qdrant collections status |
| `GET /api/domains/{id}/freshness` | SLA freshness từ _ingestion_sync_log |
| `GET /api/domains/{id}/dq` | Data quality report |

### Airflow UI

```
http://localhost:8080
```
- Xem lịch sử chạy DAG và task logs
- Retry task thất bại
- Trigger manual run với `dag_run.conf`

### Data Freshness Response

```json
{
  "domain_id": "vietnam_ecommerce",
  "checked_at": "2026-09-30 00:05:12",
  "overall_status": "HEALTHY",
  "tables_freshness": [
    {
      "table": "orders",
      "last_synced": "2026-09-30 00:01:43",
      "status": "SUCCESS",
      "rows": 1250000
    }
  ]
}
```

### SSE Streaming Logs

```
GET /api/chat/stream?session_id=xxx

data: {"type":"step","node":"intent_clarifier","message":"Phân loại: MEDIUM"}
data: {"type":"step","node":"schema_linking","message":"Steiner: orders→customers (1 hop)"}
data: {"type":"step","node":"sql_generator","message":"SQL sinh xong, đang validate..."}
data: {"type":"result","sql":"SELECT ...","rows":[...],"chart":{...}}
```

---

## 13. Lý do Lựa chọn Kiến trúc

### DuckDB vs PostgreSQL / ClickHouse

| Tiêu chí | DuckDB | PostgreSQL | ClickHouse |
|----------|--------|------------|------------|
| Setup | Embedded (zero config) | Server required | Server required |
| RAM overhead | ~100 MB | 256 MB+ | 1 GB+ |
| OLAP performance | Excellent | Medium | Excellent |
| Developer experience | File-based, simple | Complex | Complex |

**Chọn DuckDB** – phù hợp single-node dev/staging, zero infrastructure overhead.

### Airflow LocalExecutor vs CeleryExecutor

```
CeleryExecutor = Redis + Celery Workers + Flower  → +500 MB RAM
LocalExecutor  = tasks chạy trong scheduler process → +0 MB RAM
```

**Chọn LocalExecutor** – đủ cho 2 DAGs, <10 concurrent tasks.

### BashOperator cho dbt vs Astronomer Cosmos

```
Cosmos     = mỗi dbt model → 1 Airflow task → overhead metadata phức tạp
BashOperator = `dbt run --project-dir ...` → đơn giản, ít dependency
```

### BAAI/bge-m3 cho Embedding

- Multilingual by design (Việt + Anh trong cùng vector space)
- 1024 dimensions – balance precision vs performance
- Open source – chạy local, không tốn API cost

### LangGraph vs LangChain Chains

- **Stateful**: Mỗi session có `AgentState` riêng, persist qua `MemorySaver`
- **Conditional routing**: Self-correction loop tự nhiên qua edge functions
- **Streaming**: SSE native qua `graph.stream()`
- **Testability**: Mỗi node là function độc lập → dễ unit test

### Dual-Model Strategy

```
Reasoner (Qwen 72B) → Suy luận nghiệp vụ sâu, NL understanding
Coder    (Qwen 32B) → Sinh SQL chính xác, deterministic (temp=0)
```

Tách biệt vai trò giảm hallucination SQL, tối ưu từng model cho đúng nhiệm vụ.

---

*Tài liệu phản ánh trạng thái codebase tháng 9/2026. Cập nhật file này khi có thay đổi kiến trúc.*
