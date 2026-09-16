"""
Build Profiling Index Script
Trích xuất toàn bộ metadata từ Apache Doris (3.4M bản ghi) và xây dựng chỉ mục ngữ nghĩa
Bilingual Data Profiling Graph vào ChromaDB sử dụng BAAI/bge-m3.
"""

import os
import sys
import time

# Đảm bảo UTF-8 và nhận diện thư mục backend
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.doris_client import DorisClient
from app.rag.profiling_graph import BilingualDataProfilingGraph

def main():
    print("=" * 70)
    print("XÂY DỰNG BILINGUAL DATA PROFILING GRAPH (bge-m3 + ChromaDB + Doris)")
    print("=" * 70)

    start_time = time.time()
    
    # 1. Trích xuất metadata danh mục từ Apache Doris
    print("\n[1/3] Đang kết nối Apache Doris và trích xuất danh mục thực tế...")
    doris = DorisClient()
    try:
        categories = doris.get_distinct_categories()
        print(f" -> Loại hình BĐS: {len(categories['property_types'])} loại hình")
        print(f" -> Tỉnh / Thành phố: {len(categories['provinces'])} tỉnh thành")
        print(f" -> Quận / Huyện: {len(categories['districts'])} quận huyện")
        print(f" -> Hướng nhà chuẩn: {len(categories['directions'])} hướng ({', '.join(categories['directions'])})")
        print(f" -> Top Dự án phổ biến: {len(categories['top_projects'])} dự án")
    except Exception as e:
        print(f" -> Cảnh báo lỗi kết nối Doris: {e}. Sử dụng danh mục tĩnh dự phòng.")
        categories = None
    finally:
        doris.close()

    # 2. Khởi tạo BilingualDataProfilingGraph và lập chỉ mục ChromaDB
    print("\n[2/3] Đang khởi tạo ChromaDB Vector Store & mô hình BAAI/bge-m3...")
    chroma_dir = os.path.join(root_dir, "data", "chroma_db")
    profiler = BilingualDataProfilingGraph(chroma_dir=chroma_dir)

    print("\n[3/3] Bắt đầu lập chỉ mục toàn bộ Metadata, Columns, Categories & Metrics...")
    profiler.index_all(distinct_categories=categories, force=True)

    elapsed = time.time() - start_time
    print(f"\n Hoàn tất xây dựng Index trong {elapsed:.2f} giây!")
    print(f"Index lưu trữ tại: {chroma_dir}")

    # 4. Kiểm thử nhanh Schema Linking
    print("\n" + "=" * 70)
    print("KIỂM THỬ THỰC TẾ HYBRID SCHEMA LINKING")
    print("=" * 70)

    test_queries = [
        "chung cư 2PN Cầu Giấy dưới 3 tỷ",
        "đất thổ cư Thủ Đức giá rẻ",
        "giá trung bình m2 tại Đà Nẵng tháng trước",
        "biệt thự liền kề hướng đông nam trên 15 tỷ tại Hà Nội"
    ]

    for q in test_queries:
        print(f"\n>>> CÂU HỎI: \"{q}\"")
        ctx = profiler.link_schema(q)
        print(f" -> Cột liên kết: {[c.name for c in ctx.relevant_columns]}")
        print(f" -> Bộ lọc WHERE gợi ý: {ctx.suggested_filters}")
        if ctx.suggested_metrics:
            print(f" -> Chỉ số gợi ý: {[m.name + ': ' + m.sql_expression for m in ctx.suggested_metrics]}")
        if ctx.order_by_clause:
            print(f" -> ORDER BY: {ctx.order_by_clause}")
        if ctx.limit_clause:
            print(f" -> LIMIT: {ctx.limit_clause}")

if __name__ == "__main__":
    main()
