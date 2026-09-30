"""
Script khởi tạo và seed dữ liệu chuẩn xác cho DuckDB Data Warehouse (data/warehouse.duckdb).
Đảm bảo tất cả các bảng và cột phục vụ benchmark và production analytics đều tồn tại và nhất quán.
"""

import os
from pathlib import Path
import duckdb

def seed_database():
    db_path = Path(__file__).resolve().parent.parent.parent / "data" / "warehouse.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Connecting to DuckDB: {db_path}")
    conn = duckdb.connect(str(db_path))

    # 1. Bảng customers
    conn.execute("DROP TABLE IF EXISTS customers;")
    conn.execute("""
        CREATE TABLE customers (
            id BIGINT PRIMARY KEY,
            customer_id BIGINT,
            name VARCHAR(100),
            customer_name VARCHAR(100),
            registration_date DATE,
            province VARCHAR(100),
            city VARCHAR(100)
        );
    """)
    conn.execute("""
        INSERT INTO customers VALUES
        (1, 1, 'Nguyễn Văn An', 'Nguyễn Văn An', '2026-01-15', 'Hà Nội', 'Hà Nội'),
        (2, 2, 'Trần Thị Bình', 'Trần Thị Bình', '2026-02-10', 'Hồ Chí Minh', 'Hồ Chí Minh'),
        (3, 3, 'Lê Hoàng Cường', 'Lê Hoàng Cường', '2025-11-20', 'Đà Nẵng', 'Đà Nẵng'),
        (4, 4, 'Phạm Minh Đức', 'Phạm Minh Đức', '2026-03-01', 'Hải Phòng', 'Hải Phòng'),
        (5, 5, 'Vũ Thị Hoa', 'Vũ Thị Hoa', '2025-08-14', 'Cần Thơ', 'Cần Thơ'),
        (6, 6, 'Đặng Quốc Khánh', 'Đặng Quốc Khánh', '2026-01-22', 'Hà Nội', 'Hà Nội'),
        (7, 7, 'Bùi Thúy Linh', 'Bùi Thúy Linh', '2026-02-18', 'Hồ Chí Minh', 'Hồ Chí Minh');
    """)

    # 2. Bảng products
    conn.execute("DROP TABLE IF EXISTS products;")
    conn.execute("""
        CREATE TABLE products (
            id BIGINT PRIMARY KEY,
            product_id BIGINT,
            product_name VARCHAR(255),
            category VARCHAR(100),
            category_name VARCHAR(100),
            price DOUBLE
        );
    """)
    conn.execute("""
        INSERT INTO products VALUES
        (101, 101, 'iPhone 15 Pro Max', 'Điện tử', 'Điện tử', 32000000),
        (102, 102, 'Samsung Galaxy S24', 'Điện tử', 'Điện tử', 24000000),
        (103, 103, 'Áo Thun Polo Nam', 'Thời trang', 'Thời trang', 350000),
        (104, 104, 'Váy Dạ Hội Nữ', 'Thời trang', 'Thời trang', 1200000),
        (105, 105, 'Nồi Chiên Không Dầu Philips', 'Gia dụng', 'Gia dụng', 2800000),
        (106, 106, 'Máy Hút Bụi Robot Xiaomi', 'Gia dụng', 'Gia dụng', 6500000),
        (107, 107, 'Tai nghe Sony WH-1000XM5', 'Điện tử', 'Điện tử', 7900000);
    """)

    # 3. Bảng orders
    conn.execute("DROP TABLE IF EXISTS orders;")
    conn.execute("""
        CREATE TABLE orders (
            order_id BIGINT PRIMARY KEY,
            customer_id BIGINT DEFAULT 1,
            customer_name VARCHAR(100),
            total_amount DOUBLE,
            area DOUBLE DEFAULT 0,
            price DOUBLE DEFAULT 0,
            order_status VARCHAR(50) DEFAULT 'COMPLETED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            id BIGINT GENERATED ALWAYS AS (order_id),
            status VARCHAR(50) GENERATED ALWAYS AS (order_status)
        );
    """)
    conn.execute("""
        INSERT INTO orders (order_id, customer_id, customer_name, total_amount, area, price, order_status, created_at) VALUES
        (1001, 1, 'Nguyễn Văn An', 32000000, 50.0, 32000000, 'COMPLETED', '2026-01-16 10:30:00'),
        (1002, 1, 'Nguyễn Văn An', 700000, 20.0, 700000, 'COMPLETED', '2026-01-20 14:15:00'),
        (1003, 1, 'Nguyễn Văn An', 2800000, 30.0, 2800000, 'COMPLETED', '2026-02-05 09:00:00'),
        (1004, 1, 'Nguyễn Văn An', 6500000, 45.0, 6500000, 'COMPLETED', '2026-02-12 16:45:00'),
        (1005, 2, 'Trần Thị Bình', 24000000, 60.0, 24000000, 'COMPLETED', '2026-02-11 11:20:00'),
        (1006, 2, 'Trần Thị Bình', 1200000, 15.0, 1200000, 'CANCELLED', '2026-02-15 15:30:00'),
        (1007, 3, 'Lê Hoàng Cường', 7900000, 35.0, 7900000, 'COMPLETED', '2026-01-10 18:00:00'),
        (1008, 3, 'Lê Hoàng Cường', 350000, 10.0, 350000, 'COMPLETED', '2026-01-28 08:30:00'),
        (1009, 4, 'Phạm Minh Đức', 5500000, 40.0, 5500000, 'PENDING', '2026-03-02 12:10:00'),
        (1010, 5, 'Vũ Thị Hoa', 2800000, 25.0, 2800000, 'COMPLETED', '2026-01-05 13:00:00');
    """)

    # 4. Bảng order_items
    conn.execute("DROP TABLE IF EXISTS order_items;")
    conn.execute("""
        CREATE TABLE order_items (
            id BIGINT PRIMARY KEY,
            order_id BIGINT,
            product_id BIGINT,
            quantity INT,
            unit_price DOUBLE
        );
    """)
    conn.execute("""
        INSERT INTO order_items VALUES
        (1, 1001, 101, 1, 32000000),
        (2, 1002, 103, 2, 350000),
        (3, 1003, 105, 1, 2800000),
        (4, 1004, 106, 1, 6500000),
        (5, 1005, 102, 1, 24000000),
        (6, 1006, 104, 1, 1200000),
        (7, 1007, 107, 1, 7900000),
        (8, 1008, 103, 1, 350000),
        (9, 1009, 104, 2, 1200000),
        (10, 1010, 105, 1, 2800000);
    """)

    # 5. Bảng payments
    conn.execute("DROP TABLE IF EXISTS payments;")
    conn.execute("""
        CREATE TABLE payments (
            id BIGINT PRIMARY KEY,
            order_id BIGINT,
            payment_method VARCHAR(50),
            amount DOUBLE
        );
    """)
    conn.execute("""
        INSERT INTO payments VALUES
        (1, 1001, 'VNPAY', 32000000),
        (2, 1002, 'COD', 700000),
        (3, 1003, 'MOMO', 2800000),
        (4, 1004, 'CREDIT_CARD', 6500000),
        (5, 1005, 'VNPAY', 24000000),
        (6, 1006, 'MOMO', 1200000),
        (7, 1007, 'CREDIT_CARD', 7900000),
        (8, 1008, 'COD', 350000),
        (9, 1009, 'VNPAY', 5500000),
        (10, 1010, 'COD', 2800000);
    """)

    # 6. Bảng fct_orders_monthly_summary
    conn.execute("DROP TABLE IF EXISTS fct_orders_monthly_summary;")
    conn.execute("""
        CREATE TABLE fct_orders_monthly_summary (
            report_month VARCHAR(7),
            status VARCHAR(50),
            total_records BIGINT,
            total_gross_revenue DOUBLE,
            avg_total_amount DOUBLE
        );
    """)
    conn.execute("""
        INSERT INTO fct_orders_monthly_summary VALUES
        ('2026-01', 'COMPLETED', 5, 43750000, 8750000),
        ('2026-01', 'CANCELLED', 1, 1500000, 1500000),
        ('2026-02', 'COMPLETED', 4, 34500000, 8625000),
        ('2026-02', 'CANCELLED', 1, 1200000, 1200000),
        ('2026-03', 'COMPLETED', 2, 11000000, 5500000),
        ('2026-03', 'PENDING', 1, 5500000, 5500000);
    """)

    # 7. Bảng stg_shopee_orders
    conn.execute("DROP TABLE IF EXISTS stg_shopee_orders;")
    conn.execute("""
        CREATE TABLE stg_shopee_orders (
            order_id BIGINT PRIMARY KEY,
            shop_name VARCHAR(100),
            order_status VARCHAR(50),
            status VARCHAR(50),
            total_amount DOUBLE,
            created_at TIMESTAMP
        );
    """)
    conn.execute("""
        INSERT INTO stg_shopee_orders VALUES
        (5001, 'Anker Official Mall', 'COMPLETED', 'COMPLETED', 1500000, '2026-02-01 10:00:00'),
        (5002, 'Anker Official Mall', 'COMPLETED', 'COMPLETED', 2200000, '2026-02-05 14:20:00'),
        (5003, 'Coolmate Store', 'COMPLETED', 'COMPLETED', 450000, '2026-02-10 11:00:00'),
        (5004, 'Coolmate Store', 'CANCELLED', 'CANCELLED', 350000, '2026-02-12 16:30:00'),
        (5005, 'Lock&Lock Vietnam', 'COMPLETED', 'COMPLETED', 1850000, '2026-02-15 09:15:00'),
        (5006, 'Lock&Lock Vietnam', 'RETURNED', 'RETURNED', 890000, '2026-02-18 17:00:00'),
        (5007, 'Xiaomi Authorized Shop', 'COMPLETED', 'COMPLETED', 4500000, '2026-02-20 13:40:00'),
        (5008, 'Xiaomi Authorized Shop', 'COMPLETED', 'COMPLETED', 6800000, '2026-02-22 19:10:00'),
        (5009, 'Sunhouse Gia Dụng', 'COMPLETED', 'COMPLETED', 950000, '2026-02-25 15:50:00'),
        (5010, 'Sunhouse Gia Dụng', 'CANCELLED', 'CANCELLED', 1200000, '2026-02-28 08:45:00');
    """)

    # 8. Bảng stg_tiktok_orders
    conn.execute("DROP TABLE IF EXISTS stg_tiktok_orders;")
    conn.execute("""
        CREATE TABLE stg_tiktok_orders (
            order_id BIGINT PRIMARY KEY,
            shop_name VARCHAR(100),
            order_status VARCHAR(50),
            status VARCHAR(50),
            total_amount DOUBLE,
            created_at TIMESTAMP
        );
    """)
    conn.execute("""
        INSERT INTO stg_tiktok_orders VALUES
        (7001, 'GenZ Trends Vietnam', 'COMPLETED', 'COMPLETED', 250000, '2026-02-02 21:00:00'),
        (7002, 'GenZ Trends Vietnam', 'COMPLETED', 'COMPLETED', 380000, '2026-02-04 22:30:00'),
        (7003, 'Cosmetics Korea Shop', 'COMPLETED', 'COMPLETED', 650000, '2026-02-08 19:15:00'),
        (7004, 'Cosmetics Korea Shop', 'COMPLETED', 'COMPLETED', 890000, '2026-02-14 20:00:00'),
        (7005, 'Digital Smart World', 'COMPLETED', 'COMPLETED', 1200000, '2026-02-19 14:00:00'),
        (7006, 'Digital Smart World', 'CANCELLED', 'CANCELLED', 450000, '2026-02-23 16:45:00');
    """)

    tables = conn.execute("SHOW TABLES;").fetchall()
    print("Warehouse seed completed! Tables present:")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t[0]};").fetchone()[0]
        print(f" - {t[0]}: {count} rows")

    conn.close()

if __name__ == "__main__":
    seed_database()
