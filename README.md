# AI-Agent Text-to-SQL Self-Service Analytics

> Hệ thống trợ lý ảo thông minh chuyển đổi ngôn ngữ tự nhiên (Tiếng Việt) thành truy vấn SQL phục vụ phân tích dữ liệu tự phục vụ (Self-Service Analytics) cho doanh nghiệp Bất động sản / Xe hơi.

---

## 📌 Tài liệu Kiến trúc & Phân tích Chi tiết
Xem toàn bộ phân tích chi tiết về bài toán, kiến trúc hệ thống, tech stack và luồng Agent tại:
👉 **[Tài liệu Phân tích Đề bài & Tech Stack (ANALYSIS_AND_TECH_STACK.md)](./ANALYSIS_AND_TECH_STACK.md)**

---

## 🚀 Các Tính năng Nổi bật
* **Tiếng Việt tự nhiên & Ngữ cảnh**: Tự động nhận diện thuật ngữ ngành Bất động sản/Ô tô, xử lý câu hỏi nhiều bước (multi-turn context).
* **LangGraph Stateful Workflow**: Điều phối Agent theo luồng khép kín (*Planner $\rightarrow$ Schema RAG $\rightarrow$ SQL Generator $\rightarrow$ Validator & Dry-run $\rightarrow$ HITL Gate $\rightarrow$ Executor $\rightarrow$ Visualizer*).
* **Human-In-The-Loop (HITL)**: Người dùng xem trước SQL và dự toán chi phí quét dữ liệu (Bytes Scanned) trước khi phê duyệt chạy truy vấn trên bảng lớn.
* **Semantic Layer**: Tích hợp dbt semantic model làm chuẩn mực thống nhất cho các chỉ số kinh doanh.
* **Trực quan hóa Đa dạng**: Xuất bảng dữ liệu chi tiết, biểu đồ trực quan (Recharts) và báo cáo diễn giải tự động.
* **Bảo mật & Phân quyền**: Supabase Auth hỗ trợ RBAC (Role-based Access Control) giữa Analyst và Data Admin.