# AI-Agent Text-to-SQL & Heterogeneous Analytics Assistant
##### Tài liệu Kiến trúc Hệ thống, Tech Stack & Thiết kế Kỹ thuật Toàn diện (Phiên bản Cập nhật AgenticData & Tối ưu Tiếng Việt)

**Hệ thống trợ lý phân tích dữ liệu tự phục vụ (Self-Service Analytics) thế hệ mới chuyên biệt cho ngành Bất động sản Việt Nam, vận hành trên bộ dữ liệu thực tế 3,5 triệu bản ghi (Tinix Vietnam Real Estates), kết hợp mô hình Dual-Model LLM (Qwen 3 + Qwen 2.5-Coder), điều phối đa tác tử LangGraph trên nền Apache Doris, dbt Semantic Layer, tích hợp bộ xử lý ngữ nghĩa Tiếng Việt chuyên sâu và các cơ chế tiên tiến từ bài báo AgenticData (Data Profiling Graph, Plan Validator Agent 3 Tầng, Bộ nhớ 3 Tầng và Complex Query Decomposition).**

---

## 1. Phân tích Đề bài & Nghiệp vụ Business Bất động sản

### 1.1. Bối cảnh & Điểm nghẽn Doanh nghiệp
*   **Đối tượng sử dụng**: Chuyên viên kinh doanh, quản lý phân phối dự án, chuyên viên nghiên cứu thị trường, ban giám đốc tại các doanh nghiệp Bất động sản (BĐS).
*   **Thực trạng**: Khi cần các số liệu vận hành ad-hoc như:
    *   *Thị trường & Phân khúc*: Biến động đơn giá trung bình/m² theo từng quận/huyện, tỷ lệ tin rao bán theo loại hình (chung cư, nhà phố, đất nền, biệt thự).
    *   *Dự án & Tồn kho*: Số lượng căn hộ còn trống theo số phòng ngủ/tầng/hướng ban công, phân tích nguồn cung theo chủ đầu tư/dự án.
    *   *Thời gian & Xu hướng*: Tốc độ thanh khoản, thời gian tin đăng tồn tại trung bình trước khi chốt giao dịch.
    Người dùng nghiệp vụ không biết viết SQL nên buộc phải gửi ticket chờ phòng Data/BI xử lý.
*   **Hậu quả**: Thời gian phản hồi kéo dài từ 1 đến vài ngày, gây trễ cơ hội kinh doanh. Đội ngũ Data tiêu tốn 60–70% thời gian chỉ để xử lý các câu hỏi lặp đi lặp lại.

### 1.2. Nguồn Dữ liệu Thực nghiệm (Ground-Truth Dataset)
Hệ thống sử dụng bộ dữ liệu thực tế quy mô lớn **`tinixai/vietnam-real-estates`** đã được tải sẵn tại `data/vietnam-real-estates/`:
*   **Quy mô**: **3.500.744 tin đăng bất động sản** (tháng 06/2025 – 03/2026 trên toàn quốc).
*   **Cấu trúc bảng chính (`real_estate_listings`)**:
    *   *Định danh & Mô tả*: `name`, `description`, `property_type_name` (Chung cư, Nhà riêng, Đất, Biệt thự, Shophouse...).
    *   *Địa lý hành chính*: `province_name`, `district_name`, `ward_name`, `street_name`, `project_name`.
    *   *Thuộc tính định lượng*: `price` (giá chào bán VNĐ), `area` (diện tích m²), `floor_count` (số tầng), `frontage_width` (mặt tiền m), `house_depth` (chiều sâu m), `road_width` (độ rộng đường trước nhà m).
    *   *Thuộc tính công năng & phong thủy*: `bedroom_count`, `bathroom_count`, `house_direction`, `balcony_direction`.
    *   *Thời gian*: `published_at` (thời điểm đăng tin).

### 1.3. Mục tiêu Cốt lõi của Hệ thống (Core Capabilities)
1.  **Hiểu tiếng Việt tự nhiên & Ngữ cảnh chuyên ngành BĐS**: Xử lý ngữ nghĩa Tiếng Việt tự nhiên và từ lóng/viết tắt (*"căn 2PN tháp A", "căn duplex", "shophouse mặt tiền", "đất thổ cư sổ đỏ", "hướng Đông Nam"*).
2.  **Chuẩn hóa Ngữ nghĩa & Từ điển Doanh nghiệp (Vietnamese Business Glossary)**: Tự động chuyển đổi từ viết tắt và các mốc thời gian tiếng Việt (*"quý này", "tháng trước", "năm ngoái"*) thành tham số truy vấn chuẩn xác.
3.  **Lập kế hoạch Semantic & Phân rã câu hỏi**: Tự động xác định bảng, chỉ số (đơn giá/m², YoY, MoM) và phân rã các câu hỏi phức tạp Mức 3 thành các tác vụ con (sub-tasks).
4.  **Đồ thị Hồ sơ Dữ liệu Song ngữ (Bilingual Data Profiling Graph)**: Tự động liên kết câu hỏi tiếng Việt với tên bảng/cột tiếng Anh trong Apache Doris bằng Hybrid Search và mô tả song ngữ.
5.  **Sinh SQL chuẩn xác & Tự kiểm định (Plan Validator Agent)**: Kiểm tra cú pháp qua Pseudo-execution giả lập, kiểm tra logic ngữ nghĩa và phát hiện thiếu dữ liệu trước khi thực thi.
6.  **Hỏi lại khi câu hỏi mơ hồ (Clarification Loop)**: Tự động dừng sớm để xác nhận với người dùng khi thiếu thông tin điều kiện, tiết kiệm 80% chi phí API.
7.  **Quản lý bộ nhớ 3 tầng & Dịch lỗi Tiếng Việt (3-Tier Memory & Error Translator)**: Phân loại lỗi ngắn hạn, dịch lỗi Database sang tiếng Việt, chấm điểm Bellman cắt tỉa nhánh lặp trong phiên, và lưu trữ tri thức dài hạn (Good Plans / Bad Plans / Common Knowledge).
8.  **Đa dạng hóa đầu ra định dạng Việt Nam (VN Formatted Output)**: Bảng dữ liệu tương tác, biểu đồ động (Recharts) với nhãn tiếng Việt có dấu, định dạng tiền tệ VNĐ (`1,2 tỷ VNĐ`) và tóm tắt Business Insights bằng tiếng Việt.

---

## 2. Ràng buộc Nghiêm ngặt & Cơ chế Quản trị (Governance & Guardrails)

| Ràng buộc | Yêu cầu nghiệp vụ | Giải pháp Kỹ thuật |
| :--- | :--- | :--- |
| **1. Human-In-The-Loop (HITL)** | Bắt buộc xem trước câu lệnh SQL và bấm xác nhận trước khi thực thi truy vấn lớn trên 3,5 triệu dòng. | Sử dụng cơ chế `interrupt` của **LangGraph**. Graph phát event qua SSE về Next.js modal preview SQL + bytes scan estimate. |
| **2. Phân quyền vai trò (RBAC)** | Analyst chỉ đọc kết quả; Admin quản lý schema, semantic layer và vector store. | **Supabase Auth (JWT)** tích hợp Middleware trên FastAPI. Tầng Database áp dụng `GRANT SELECT` cho analyst và `GRANT ALL` cho admin trên Doris. |
| **3. Giới hạn chi phí quét dữ liệu (Bytes Scanned)** | Ước tính dung lượng quét dữ liệu, cảnh báo hoặc chặn thực thi khi vượt ngưỡng. | Gọi `EXPLAIN VERBOSE <SQL>` trên **Apache Doris** phân tích Tablets/Partitions. Cảnh báo khi $> 100\text{ MB}$, bắt buộc duyệt HITL khi $> 500\text{ MB}$. |
| **4. Độ chính xác đo lường được (Metrics)** | Đo lường hiệu năng định lượng và định kỳ qua bộ benchmark nội bộ. | Bộ test benchmark 50 câu hỏi tiếng Việt chuyên ngành BĐS. Đo lường **Execution Accuracy (EX)** ($\ge 85\%$), **Valid SQL Rate** ($\ge 95\%$), **Self-Correction** ($\ge 75\%$), và **Latency P95** ($< 4.5\text{s}$). |

---

## 3. Kiến trúc Kỹ thuật & Tech Stack (Dual-Model + AgenticData + VN NLP Updates)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14+ / React)                  │
│   • Next.js App Router, Tailwind CSS, Lucide Icons                     │
│   • Dynamic Charts (Recharts / Tremor) - VN Currency & Date Format     │
│   • Interactive Chat, SQL Preview & HITL Approval Modal                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SSE / REST API (Supabase JWT Bearer)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        BACKEND API (FastAPI)                           │
│   • Async Python 3.10+, Server-Sent Events (SSE) Streaming Agent Logs │
│   • RBAC Middleware, Session Management, Doris Connection Pool         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│              AGENT ORCHESTRATOR (LangGraph Stateful Machine)           │
│                                                                        │
│   [UPDATE 1: Vietnamese Business Glossary & Normalizer]                │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │ 0. Chuẩn hóa Từ lóng, Từ viết tắt BĐS & Mốc thời gian Tiếng Việt │
│   └───────────────────────────────┬───────────────────────────────┘    │
│                                   ▼                                    │
│   [Model 1: Qwen 3 (Hybrid MoE / Deep Thinking)]                      │
│   ┌────────────────────────────────┐     ┌────────────────────────┐    │
│   │ 1. Phân tích Ý định & Mơ hồ    ├────►│ 2. Bilingual Profiling │    │
│   │    (Intent & Clarification)    │     │    Graph & Query Plan  │    │
│   └────────────────────────────────┘     └───────────┬────────────┘    │
│                                                      │ Query Plan      │
│   [Model 2: Qwen 2.5-Coder (32B / 14B)]              ▼                 │
│   ┌────────────────────────────────┐     ┌────────────────────────┐    │
│   │ 4. Plan Validator Agent        │◄────┤ 3. Sinh SQL Chuẩn Xác  │    │
│   │    (Grammar/Semantic/Data)     │     │    (MySQL / Doris DDL) │    │
│   └───────────────┬────────────────┘     └────────────────────────┘    │
│                   │ SQL hợp lệ & Dry-run OK                            │
│                   ▼                                                    │
│   ┌────────────────────────────────┐     ┌────────────────────────┐    │
│   │ 5. HITL Gate (Interrupt)       ├────►│ 6. Thực thi Doris      │    │
│   │    Xem trước SQL & Bytes Scan  │     │    (MySQL Connection)  │    │
│   └────────────────────────────────┘     └───────────┬────────────┘    │
│                                                      │                 │
│   [UPDATE 5: VN Formatter & Chart Rendering]         ▼                 │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │ 7. Formatter: Trích xuất Bảng + Recharts + Định dạng VNĐ      │    │
│   └───────────────────────────────────────────────────────────────┘    │
└──────────────┬────────────────────┬─────────────────────┬──────────────┘
               │                    │                     │
               ▼                    ▼                     ▼
      ┌────────────────┐   ┌─────────────────┐   ┌────────────────┐
      │  3-Tier Memory │   │  dbt Semantic   │   │ Real-Time DW   │
      │ Multilingual   │   │      Model      │   │ (Apache Doris  │
      │ (ChromaDB +    │   │  (`dbt-doris`)  │   │ 3.5M Listings) │
      │  bge-m3 Model) │   │  Bilingual Meta │   │                │
      └────────────────┘   └─────────────────┘   └────────────────┘
```

### Bảng Phân công Nhiệm vụ & Tech Stack

| Tầng hệ thống | Công nghệ lựa chọn | Vai trò & Lý do kỹ thuật |
| :--- | :--- | :--- |
| **VN Text Preprocessor** | **Business Glossary Engine** *(Update 1)* | Chuẩn hóa từ lóng ngành BĐS (*căn 2PN, duplex, shophouse, sổ đỏ/sổ hồng, hẻm xe hơi*), quy đổi ngày tháng tiếng Việt (*tháng trước, quý này*) trước khi gửi vào LLM. |
| **Model 1: Planner & Reasoner** | **Qwen 3** *(MoE / Deep Thinking)* | Đọc câu hỏi tiếng Việt đã chuẩn hóa, nhận diện mơ hồ, kích hoạt hỏi lại người dùng, phân rã câu hỏi phức tạp (sub-tasks), lập cây kế hoạch Semantic Plan. |
| **Model 2: SQL Generator & Fixer** | **Qwen 2.5-Coder** *(32B / 14B)* | Sinh SQL chuẩn MySQL cho Apache Doris từ Query Plan và Schema nén; tự sửa lỗi cú pháp dựa trên định tuyến từ Short-Term Memory. |
| **Agent Orchestrator** | **LangGraph** | Quản lý stateful graph, tích hợp vòng lặp sửa lỗi 3-Tier Memory, ngắt interrupt cho HITL và luồng phân rã Complex Query. |
| **Data Warehouse** | **Apache Doris Standalone** | Real-time MPP OLAP DW lưu trữ dạng cột, nạp toàn bộ 3,5 triệu dòng Parquet, tương thích hoàn toàn giao thức MySQL, đáp ứng truy vấn sub-second. |
| **Bilingual Data Profiling Graph** | **`bge-m3` + ChromaDB** *(Update 2 & 3)* | Đánh chỉ mục song ngữ (Anh-Việt) cho Node Profiling và Edge Profiling bằng Hybrid Search (Vector `bge-m3` + BM25 + Jaccard) để liên kết schema. |
| **Semantic Layer** | **dbt-core + dbt-doris** | Định nghĩa các chỉ số kinh doanh BĐS (*Đơn giá/m², Tỷ lệ chênh lệch giá, Phân phối diện tích*) làm Single Source of Truth kèm chú thích song ngữ. |
| **Error Translator** | **Short-Term Memory Translator** *(Update 4)* | Tự động dịch lỗi DB bằng tiếng Anh (`Unknown column`, `Syntax error`) sang chỉ dẫn sửa lỗi bằng tiếng Việt cho LLM. |
| **Backend API** | **FastAPI + Async Python** | Cung cấp endpoint SSE stream log suy nghĩ của Agent, middleware RBAC Supabase JWT và connection pool kết nối Doris. |
| **Frontend & VN Formatter** | **Next.js 14+ / Recharts** *(Update 5)* | UI Chatbot Analytics, Data Table phân trang, Recharts render biểu đồ động với nhãn tiếng Việt, định dạng tiền tệ VNĐ (`1,2 tỷ VNĐ`) và Modal Preview SQL kèm Bytes Scan. |

---

## 4. Tối ưu hóa Tài nguyên cho Máy 16GB RAM (Low-Memory Tuning)

### 4.1. Phân bổ RAM chi tiết
*   **Windows OS & System Background**: ~ 4.0 GB
*   **IDE + Browser**: ~ 2.5 GB
*   **Apache Doris (FE + BE Standalone trong Docker)**: **~ 2.0 – 2.5 GB**
*   **Backend (FastAPI + LangGraph + Uvicorn + FastEmbed `bge-m3`)**: ~ 0.8 GB
*   **Frontend (Next.js dev server)**: ~ 0.6 GB
*   **ChromaDB / Vector Store**: ~ 0.3 GB
*   👉 **Dự phòng an toàn**: **~ 4.8 – 5.3 GB** (Giúp hệ thống vận hành mượt mà, không bị tràn RAM).

---

## 5. Tích hợp Đột phá AgenticData Core & 5 Cập nhật Tiếng Việt Chuyên sâu

### 5.1. Update 1: Vietnamese Business Glossary & Normalizer
Bộ tiền xử lý ngữ nghĩa tiếng Việt đặt trước Node 1 trong LangGraph:
*   **Từ lóng & Từ viết tắt BĐS**: Biến đổi *"căn 2PN tháp A"* $\rightarrow$ *"căn hộ 2 phòng ngủ thuộc phân khu Tháp A"*, *"shophouse chân đế"* $\rightarrow$ *"căn hộ thương mại dịch vụ khối đế"*, *"đất thổ cư"* $\rightarrow$ *"đất ở nông thôn/đô thị"*.
*   **Chuyển đổi Thời gian tiếng Việt**: Tự động nhận diện các cụm từ *"quý này"*, *"tháng trước"*, *"năm ngoái"* và quy đổi thành dải ngày cụ thể (`START_DATE`, `END_DATE`) dựa trên thời gian hệ thống hiện tại.

### 5.2. Update 2 & 3: Bilingual Data Profiling Graph & Multilingual Embedding (`bge-m3`)
*   **Bilingual Metadata**: Mỗi cột trong bảng `real_estate_listings` được gán từ điển ngữ nghĩa song ngữ Anh-Việt:
    *   Cột `price` $\rightarrow$ Mô tả: *"Giá bán bất động sản niêm yết (VNĐ)"*.
    *   Cột `area` $\rightarrow$ Mô tả: *"Diện tích mặt sàn bất động sản (m²)"*.
    *   Cột `property_type_name` $\rightarrow$ Mô tả: *"Loại hình BĐS (Chung cư, Nhà riêng, Biệt thự, Đất...)"*.
    *   Cột `project_name` $\rightarrow$ Mô tả: *"Tên dự án bất động sản hoặc khu đô thị"*.
*   **Multilingual Embedding**: Sử dụng mô hình **`bge-m3`** làm nền tảng cho ChromaDB Vector Store, giúp tìm kiếm tương đồng câu hỏi tiếng Việt không bị phân mảnh sub-token như các model Tiếng Anh.
*   **Edge Profiling Hybrid Search**:
    $$\text{Hybrid Search} = \text{Vector Similarity (bge-m3)} + \text{BM25 Text Search} + \text{Jaccard Keyword Similarity}$$

### 5.3. Plan Validator Agent & Update 4: DB Error Translator
Thực hiện kiểm định đa tầng trước khi chạy câu lệnh truy vấn thật trên Doris:
1.  **Grammar Validator**: Thực hiện *Pseudo-execution* (chạy giả lập trên Schema) để phát hiện cột/bảng không tồn tại.
2.  **Semantic Validator**: Kiểm tra logic ngữ nghĩa (ví dụ: yêu cầu Top K giá rẻ nhất nhưng thiếu `ORDER BY price ASC LIMIT K`).
3.  **Data Missing Detector**: Phát hiện thiếu các điều kiện lọc địa phương (quận/huyện, tỉnh/thành).
4.  **Error Translator**: Khi Doris trả về lỗi tiếng Anh (`Unknown column 'dien_tich' in 'field list'`), Short-Term Memory dịch thành phản hồi tiếng Việt cụ thể cho LLM: *"Cột 'dien_tich' không tồn tại trong bảng 'real_estate_listings', hãy đổi thành cột 'area'"*.

### 5.4. Cấu trúc Quản lý Bộ nhớ 3 Tầng (3-Tier Memory)
*   **Short-Term Memory**: Lưu tối đa 3 lỗi gần nhất, chia thành 3 container (*Data, Semantic, Grammar*) để định tuyến chính xác lỗi về đúng Agent xử lý.
*   **Temporary Memory**: Lưu trữ lịch sử thử nghiệm kế hoạch trong cùng phiên. Áp dụng **Phương trình Bellman**:
    $$v(S_t) = \mathbb{E}[R_{t+1} + \gamma v(S_{t+1})]$$
    để tính điểm trạng thái (*State Value*), gán nhãn *Good Plans / Bad Plans* và cắt tỉa nhánh lặp bị bế tắc.
*   **Long-Term Memory**: Bộ lưu trữ Vector DB chứa 5 bảng (*Task Groups, Common Knowledge, Good Plans, Bad Plans, Context Memory*) chia sẻ kinh nghiệm xử lý giữa các tác vụ tương tự.

### 5.5. Phân rã Câu hỏi Phức tạp (Complex Query Decomposition)
Dành riêng cho các câu hỏi Mức 3 (YoY, MoM, biến động giá, Window Functions):
1.  **Sub-task Decomposition**: Qwen 3 phân rã câu hỏi lớn thành 2–3 câu hỏi nhỏ độc lập kèm prompt ràng buộc tính toàn vẹn.
2.  **Materialization**: Kết quả các sub-task được thực thi và vật chất hóa thành các **tập dữ liệu bổ sung (Complementary Datasets)** lưu tạm.
3.  **Final Planning**: Qwen 3 sinh câu SQL cuối cùng dễ dàng kết nối trên các tập dữ liệu trung gian đã chuẩn bị.

### 5.6. Update 5: VN Formatter Engine & Chart Rendering
*   **Định dạng Tiền tệ & Diện tích**: Tự động chuyển đổi `7450000000` $\rightarrow$ `7,45 tỷ VNĐ`, `37.5` $\rightarrow$ `37,5 m²`, đơn giá `150000000` $\rightarrow$ `150 triệu/m²`.
*   **Biểu đồ Recharts Tiếng Việt**: Trục $X, Y$, Tooltip và Legend của biểu đồ Recharts được trả về với tiêu đề tiếng Việt có dấu đầy đủ.

---

## 6. Lộ trình Triển khai Chi tiết 14 Ngày (Updated 14-Day Roadmap)

### 📍 GIAI ĐOẠN 1: Hạ tầng, Schema & Nạp 3,5 Triệu Bản ghi vào Doris (Ngày 1 - Ngày 3)
*   [ ] Khởi tạo file `.wslconfig` và deploy cụm Apache Doris Standalone bằng Docker Compose.
*   [ ] Tạo bảng `real_estate_listings` trên Apache Doris tối ưu Partitioning theo `province_name` và `published_at`.
*   [ ] Nạp dữ liệu 10 file Parquet vào Apache Doris qua tính năng *Stream Load* hoặc *S3/Local Parquet Table*.
*   [ ] Tích hợp mô hình Embedding đa ngôn ngữ **`bge-m3`** cho ChromaDB Vector Store.
*   [ ] Tự động hóa **Bilingual Data Profiling Graph**: Tạo Node Profiles song ngữ và thiết lập Edge Profiles bằng Hybrid Search.

### 📍 GIAI ĐOẠN 2: Vietnamese Preprocessor, Plan Validator & Core Dual-Model (Ngày 4 - Ngày 7)
*   [ ] Xây dựng **Vietnamese Business Glossary & Normalizer** (xử lý từ lóng BĐS và quy đổi mốc thời gian).
*   [ ] Cấu hình `dbt-doris` định nghĩa các metrics BĐS cốt lõi (*Đơn giá/m², Tỷ lệ chênh lệch giá, Phân phối diện tích*) kèm chú thích tiếng Việt.
*   [ ] Lập trình các Node chính trong LangGraph (Node 0 Preprocessor, Node 1 Intent, Node 2 Data Selection, Node 3 Planning, Node 4 SQL Generation).
*   [ ] Tích hợp **Plan Validator Agent 3 Tầng** (*Grammar Pseudo-execution, Semantic Logic, Data Missing*) và bộ dịch lỗi DB sang tiếng Việt (**Error Translator**).
*   [ ] Tích hợp **Cấu trúc Bộ nhớ 3 Tầng** (*Short-term containers, Temporary Bellman scoring, Long-term Vector DB*).

### 📍 GIAI ĐOẠN 3: Complex Query Decomposition, Backend & Frontend UI (Ngày 8 - Ngày 11)
*   [ ] Thiết lập quy trình **Complex Query Decomposition** cho câu hỏi Mức 3 và cơ chế vật chất hóa bảng tạm (Materialization).
*   [ ] Xây dựng FastAPI Backend: SSE Streaming endpoint, Supabase JWT auth middleware, HITL approve/reject endpoint.
*   [ ] Dựng giao diện Next.js 14+: Chat container, Data Table phân trang, Recharts dynamic rendering kèm bộ định dạng tiếng Việt **VN Formatter Engine**.
*   [ ] Tích hợp Modal Preview SQL & Bytes Scan Estimate (EXPLAIN VERBOSE) phục vụ nút duyệt HITL.

### 📍 GIAI ĐOẠN 4: Đánh giá Benchmark, Tối ưu Dài hạn & Đóng gói (Ngày 12 - Ngày 14)
*   [ ] Thực thi bộ test benchmark 50 câu hỏi tiếng Việt BĐS trên tập dữ liệu 3,5 triệu dòng.
*   [ ] Cập nhật kết quả SQL thành công vào bảng **Good Plans** và lỗi phổ biến vào **Common Knowledge** của Long-Term Memory.
*   [ ] Đóng gói Dockerfile hoàn chỉnh cho Backend và Frontend, deploy Frontend lên Vercel và hoàn thiện tài liệu vận hành.

---

## 7. Tiêu chuẩn Nghiệm thu & KPI Đo lường (Evaluation Metrics)

*   **Execution Accuracy (EX)**: Tỷ lệ kết quả dữ liệu do SQL sinh ra trùng khớp 100% với SQL chuẩn $\ge 85\%$.
*   **Valid SQL Rate**: Tỷ lệ câu SQL không bị lỗi cú pháp trong lần chạy đầu tiên $\ge 95\%$.
*   **Self-Correction Success Rate**: Tỷ lệ tự sửa lỗi thành công qua vòng lặp bộ nhớ 3 tầng $\ge 75\%$.
*   **Latency (P95)**: Thời gian phản hồi tổng thể từ khi gửi câu hỏi đến khi bắt đầu hiển thị kết quả $< 4.5\text{ giây}$.
