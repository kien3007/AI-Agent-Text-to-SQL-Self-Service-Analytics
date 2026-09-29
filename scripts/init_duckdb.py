"""
Script khởi tạo và chuẩn hóa DuckDB Data Warehouse cho dự án.
Nạp hoặc ánh xạ toàn bộ 3.5 triệu bản ghi từ dataset Parquet vào DuckDB.
Đảm bảo kiểu dữ liệu chuẩn (price, area, bedroom_count... dạng số).
"""

import os
import sys
from pathlib import Path
import duckdb

# UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "warehouse.duckdb"
PARQUET_GLOB = str((PROJECT_ROOT / "dataset" / "vietnam-real-estates" / "*.parquet")).replace("\\", "/")


def init_duckdb_warehouse():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📦 Đang kết nối DuckDB tại: {DB_PATH}")
    conn = duckdb.connect(str(DB_PATH))

    print(f"🔍 Kiểm tra nguồn dữ liệu Parquet: {PARQUET_GLOB}")
    
    # Tạo VIEW với ép kiểu số chuẩn cho price & area
    view_sql = f"""
    CREATE OR REPLACE VIEW real_estate_listings AS
    SELECT 
        name,
        description,
        property_type_name,
        province_name,
        district_name,
        ward_name,
        street_name,
        project_name,
        TRY_CAST(price AS DOUBLE) AS price,
        TRY_CAST(area AS DOUBLE) AS area,
        TRY_CAST(floor_count AS DOUBLE) AS floor_count,
        TRY_CAST(frontage_width AS DOUBLE) AS frontage_width,
        TRY_CAST(house_depth AS DOUBLE) AS house_depth,
        TRY_CAST(road_width AS DOUBLE) AS road_width,
        TRY_CAST(bedroom_count AS DOUBLE) AS bedroom_count,
        TRY_CAST(bathroom_count AS DOUBLE) AS bathroom_count,
        house_direction,
        balcony_direction,
        published_at
    FROM '{PARQUET_GLOB}';
    """
    
    conn.execute(view_sql)
    print("✅ Đã tạo VIEW real_estate_listings thành công!")

    # Test count & stats
    count = conn.execute("SELECT COUNT(*) FROM real_estate_listings").fetchone()[0]
    sample = conn.execute("""
        SELECT province_name, COUNT(*) as cnt, ROUND(AVG(price) / 1e9, 2) as avg_price_ty
        FROM real_estate_listings
        WHERE province_name IN ('Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng')
        GROUP BY province_name
        ORDER BY cnt DESC
    """).fetchall()

    print(f"📊 Tổng số bản ghi trong Warehouse: {count:,}")
    print("📈 Thống kê thử nghiệm:")
    for row in sample:
        print(f"   - {row[0]}: {row[1]:,} tin đăng, Giá trung bình: {row[2]} tỷ VNĐ")

    conn.close()
    print("🎉 Khởi tạo DuckDB Warehouse hoàn tất!")


if __name__ == "__main__":
    init_duckdb_warehouse()
