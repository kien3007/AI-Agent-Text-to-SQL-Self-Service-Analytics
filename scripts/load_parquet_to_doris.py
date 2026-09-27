import os
import sys
import glob
import time
import argparse
import requests
import pandas as pd
import pymysql
import pyarrow.parquet as pq
from tqdm import tqdm

# Cấu hình in UTF-8 trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DORIS_HOST = os.getenv("DORIS_HOST", "127.0.0.1")
DORIS_HTTP_PORT = int(os.getenv("DORIS_HTTP_PORT", "8030"))
DORIS_QUERY_PORT = int(os.getenv("DORIS_QUERY_PORT", "9030"))
DORIS_USER = os.getenv("DORIS_USER", "root")
DORIS_PASSWORD = os.getenv("DORIS_PASSWORD", "")
DB_NAME = "real_estate_analytics"
TABLE_NAME = "real_estate_listings"

def get_mysql_connection(db=None):
    """Tạo kết nối tới Doris qua MySQL protocol."""
    return pymysql.connect(
        host=DORIS_HOST,
        port=DORIS_QUERY_PORT,
        user=DORIS_USER,
        password=DORIS_PASSWORD,
        database=db,
        charset="utf8mb4",
        autocommit=True
    )

def wait_for_doris(timeout=180):
    """Chờ cho đến khi Apache Doris khởi động xong và sẵn sàng nhận kết nối."""
    print(f"Đang kiểm tra kết nối tới Apache Doris ({DORIS_HOST}:{DORIS_QUERY_PORT})...", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = get_mysql_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                ver = cursor.fetchone()
                print(f"✅ Đã kết nối thành công tới Apache Doris (Phiên bản: {ver[0]})", flush=True)
            conn.close()
            return True
        except Exception as e:
            time.sleep(3)
    print("❌ Hết thời gian chờ kết nối tới Apache Doris!", flush=True)
    return False

def init_schema():
    """Khởi tạo Database và Table theo script DDL."""
    print("\n--- Khởi tạo Schema Database & Table ---", flush=True)
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME};")
        cursor.execute(f"USE {DB_NAME};")
        
        # Đọc file 02_create_tables.sql
        ddl_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "infra", "doris", "init", "02_create_tables.sql"
        )
        if os.path.exists(ddl_path):
            with open(ddl_path, "r", encoding="utf-8") as f:
                ddl = f.read()
            cursor.execute(ddl)
            print("✅ Đã khởi tạo bảng 'real_estate_listings' thành công!", flush=True)
        else:
            print(f"⚠️ Không tìm thấy file DDL tại: {ddl_path}", flush=True)
    conn.close()

# Tạo session tái sử dụng và giữ nguyên Authorization header khi redirect từ FE sang BE
http_session = requests.Session()
http_session.should_strip_auth = lambda o, n: False

def stream_load_chunk(df_chunk, chunk_id):
    """Nạp một khối dữ liệu (DataFrame) vào Doris bằng HTTP Stream Load API."""
    url = f"http://{DORIS_HOST}:{DORIS_HTTP_PORT}/api/{DB_NAME}/{TABLE_NAME}/_stream_load"
    
    # Định dạng dữ liệu dạng CSV ngăn cách bởi dấu tab (\t)
    csv_bytes = df_chunk.to_csv(
        sep="\t",
        index=False,
        header=False,
        na_rep="\\N"
    ).encode("utf-8")
    
    columns = (
        "name,description,property_type_name,province_name,district_name,"
        "ward_name,street_name,project_name,price,area,floor_count,"
        "frontage_width,house_depth,road_width,bedroom_count,bathroom_count,"
        "house_direction,balcony_direction,published_at"
    )
    
    headers = {
        "Expect": "100-continue",
        "format": "csv",
        "column_separator": "\\t",
        "columns": columns,
        "max_filter_ratio": "0.2"
    }
    
    resp = http_session.put(
        url,
        data=csv_bytes,
        headers=headers,
        auth=(DORIS_USER, DORIS_PASSWORD)
    )
    
    if resp.status_code == 200:
        res_json = resp.json()
        if res_json.get("Status") in ["Success", "Publish Timeout"]:
            return res_json.get("NumberLoadedRows", len(df_chunk))
        else:
            print(f"\n⚠️ Cảnh báo nạp chunk {chunk_id}: {res_json.get('Message')}", flush=True)
            return res_json.get("NumberLoadedRows", 0)
    else:
        print(f"\n❌ Lỗi HTTP {resp.status_code}: {resp.text}", flush=True)
        return 0

def load_data(max_shards=None, chunk_size=25000, start_shard=0, truncate=False):
    """Đọc các file Parquet và nạp vào Doris."""
    if truncate:
        print(f"\n--- Làm sạch bảng {TABLE_NAME} trước khi nạp mới ---", flush=True)
        try:
            conn = get_mysql_connection(db=DB_NAME)
            with conn.cursor() as cursor:
                cursor.execute(f"TRUNCATE TABLE {TABLE_NAME};")
                print("✅ Đã TRUNCATE bảng thành công.", flush=True)
            conn.close()
        except Exception as e:
            print(f"Lỗi truncate: {e}", flush=True)

    # Tìm thư mục dataset
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(project_root, "dataset", "vietnam-real-estates")
    if not os.path.exists(dataset_dir):
        dataset_dir = os.path.join(project_root, "data", "vietnam-real-estates")
        
    parquet_files = sorted(glob.glob(os.path.join(dataset_dir, "shard_*.parquet")))
    if not parquet_files:
        print(f"❌ Không tìm thấy file parquet nào trong thư mục: {dataset_dir}")
        return
        
    if start_shard > 0:
        parquet_files = parquet_files[start_shard:]
    if max_shards:
        parquet_files = parquet_files[:max_shards]
        
    print(f"\n--- Bắt đầu nạp dữ liệu từ {len(parquet_files)} file Parquet ---", flush=True)
    print(f"Dataset path: {dataset_dir}")
    print(f"Chunk size: {chunk_size:,} dòng/lần nạp", flush=True)
    
    total_loaded = 0
    start_time = time.time()
    
    # Thứ tự các cột khớp với Stream Load Header
    target_columns = [
        "name", "description", "property_type_name", "province_name", "district_name",
        "ward_name", "street_name", "project_name", "price", "area", "floor_count",
        "frontage_width", "house_depth", "road_width", "bedroom_count", "bathroom_count",
        "house_direction", "balcony_direction", "published_at"
    ]
    
    for i, file_path in enumerate(parquet_files, 1):
        file_name = os.path.basename(file_path)
        print(f"\n[{i}/{len(parquet_files)}] Đang đọc file {file_name}...", flush=True)
        
        try:
            parquet_file = pq.ParquetFile(file_path)
            num_rows = parquet_file.metadata.num_rows
            shard_loaded = 0
            
            with tqdm(total=num_rows, desc=f"Shard {file_name}", unit="rows") as pbar:
                for batch in parquet_file.iter_batches(batch_size=chunk_size, columns=target_columns):
                    df_chunk = batch.to_pandas()
                    
                    # Làm sạch các giá trị text tránh ký tự tab làm lệch cột
                    if "name" in df_chunk.columns:
                        df_chunk["name"] = df_chunk["name"].fillna("").astype(str).str.replace("\t", " ").str.replace("\n", " ")
                    if "description" in df_chunk.columns:
                        df_chunk["description"] = df_chunk["description"].fillna("").astype(str).str.replace("\t", " ").str.replace("\n", " ")
                    
                    # Đảm bảo published_at đúng định dạng datetime string YYYY-MM-DD HH:MM:SS
                    if "published_at" in df_chunk.columns:
                        df_chunk["published_at"] = pd.to_datetime(df_chunk["published_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
                        df_chunk["published_at"] = df_chunk["published_at"].fillna("2025-06-01 00:00:00")
                        
                    loaded = stream_load_chunk(df_chunk, f"{i}_{shard_loaded // chunk_size}")
                    shard_loaded += loaded
                    pbar.update(len(df_chunk))
                    
            total_loaded += shard_loaded
            print(f" -> Hoàn tất {file_name}: Nạp thành công {shard_loaded:,} dòng.", flush=True)
        except Exception as e:
            print(f" -> Lỗi đọc file {file_name}: {e}", flush=True)
        
    elapsed = time.time() - start_time
    print(f"\n🎉 HOÀN TẤT NẠP DỮ LIỆU!", flush=True)
    print(f"Tổng số bản ghi đã nạp đợt này: {total_loaded:,} dòng")
    print(f"Tổng thời gian: {elapsed:.2f} giây ({total_loaded / max(1, elapsed):.0f} rows/s)", flush=True)
    
    # Kiểm tra số lượng dòng thực tế trong Doris
    verify_count()

def verify_count():
    """Kiểm tra đếm số dòng thực tế trong bảng Doris."""
    try:
        import json
        from datetime import datetime
        
        conn = get_mysql_connection(db=DB_NAME)
        count = 0
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
            count = cursor.fetchone()[0]
            print(f"\n📊 Kiểm tra đếm thực tế trong Apache Doris: {count:,} dòng!", flush=True)
            
            # Thống kê nhanh top 5 tỉnh thành
            cursor.execute(f"SELECT province_name, COUNT(*) as cnt FROM {TABLE_NAME} GROUP BY province_name ORDER BY cnt DESC LIMIT 5;")
            rows = cursor.fetchall()
            print("Top 5 tỉnh/thành có nhiều tin đăng nhất:")
            for p, cnt in rows:
                print(f" - {p}: {cnt:,} tin")
        conn.close()
        
        # Ghi Ingestion Lineage Log
        lineage_log = {
            "source": "Parquet files",
            "destination": f"Doris ({DB_NAME}.{TABLE_NAME})",
            "ingestion_time": datetime.utcnow().isoformat() + "Z",
            "total_records": count,
            "status": "SUCCESS"
        }
        os.makedirs("data", exist_ok=True)
        with open("data/ingestion_lineage.json", "w", encoding="utf-8") as f:
            json.dump(lineage_log, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Lỗi kiểm tra count: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nạp dữ liệu Parquet vào Apache Doris")
    parser.add_argument("--max-shards", type=int, default=None, help="Số lượng shard tối đa cần nạp (None = nạp toàn bộ)")
    parser.add_argument("--start-shard", type=int, default=0, help="Vị trí shard bắt đầu nạp (0-based)")
    parser.add_argument("--chunk-size", type=int, default=25000, help="Số dòng mỗi batch nạp qua Stream Load")
    parser.add_argument("--truncate", action="store_true", help="Làm sạch dữ liệu cũ trong bảng trước khi nạp")
    parser.add_argument("--skip-wait", action="store_true", help="Bỏ qua bước kiểm tra chờ Doris khởi động")
    args = parser.parse_args()
    
    if not args.skip_wait:
        if not wait_for_doris():
            sys.exit(1)
            
    init_schema()
    load_data(
        max_shards=args.max_shards,
        chunk_size=args.chunk_size,
        start_shard=args.start_shard,
        truncate=args.truncate
    )
