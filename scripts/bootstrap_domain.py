"""
Script CLI: Bootstrap Domain (Tự động khám phá CSDL mới hoặc Khôi phục Domain).
Sử dụng:
  1. Quét CSDL mới (DuckDB / MySQL):
     python scripts/bootstrap_domain.py --db-name my_company_db --domain-id my_domain --display-name "Tên Nghiệp Vụ"
  2. Liệt kê các domain đang cài đặt:
     python scripts/bootstrap_domain.py --list
  3. Khôi phục các domain mẫu từ backup:
     python scripts/bootstrap_domain.py --restore
"""

import os
import sys
import argparse
import shutil

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import backend
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.domain_manager import DomainManager
from app.core.introspection import DatabaseIntrospector
from app.core.dbt_generator import AutoDbtGenerator
from app.db.warehouse_client import get_warehouse_client


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Domain cho AI-Agent Text-to-SQL")
    parser.add_argument("--list", action="store_true", help="Liệt kê toàn bộ các domain hiện có trong hệ thống")
    parser.add_argument("--restore", action="store_true", help="Khôi phục các domain mẫu (real_estate, ecommerce, healthcare) từ backup")
    parser.add_argument("--db-name", type=str, help="Tên database cần quét introspection (DuckDB/SQL)")
    parser.add_argument("--domain-id", type=str, help="Mã định danh domain mới (VD: logistics, hr, crm)")
    parser.add_argument("--display-name", type=str, help="Tên hiển thị của domain mới")
    parser.add_argument("--auto-dbt", action="store_true", help="Tự động sinh toàn bộ pipeline dbt (staging, marts, metrics) và đồng bộ vào Agent")
    parser.add_argument("--db-path", type=str, default=None, help="Đường dẫn file DuckDB database")

    args = parser.parse_args()

    dm = DomainManager()
    domains_dir = dm.domains_dir
    backup_dir = os.path.join(backend_dir, ".domains_backup")

    # 1. Khôi phục từ backup
    if args.restore:
        if not os.path.exists(backup_dir):
            print(f"[INFO] Không tìm thấy thư mục backup tại: {backup_dir}")
            print("[INFO] Bạn có thể tự động tạo domain mới từ CSDL bằng lệnh:")
            print("       python scripts/bootstrap_domain.py --db-name warehouse --domain-id ecommerce --display-name \"Thương Mại Điện Tử\" --auto-dbt")
            return
        for item in os.listdir(backup_dir):
            src = os.path.join(backup_dir, item)
            dst = os.path.join(domains_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"[RESTORE] Đã khôi phục domain: '{item}'")
        dm.reload_domains()
        print(f"[SUCCESS] Hoàn tất khôi phục. Các domain hiện có: {dm.list_domains()}")
        return

    # 2. Liệt kê domain
    if args.list:
        dm.reload_domains()
        installed = dm.list_domains()
        print("=" * 60)
        print(f"DANH SÁCH DOMAIN HIỆN TẠI ({len(installed)} domain):")
        print("=" * 60)
        if not installed:
            print("(!) Hiện tại CHƯA CÓ domain nào được cài đặt trong 'backend/app/domains/'.")
            print("    Hệ thống đang ở trạng thái 'Cold-Start' sẵn sàng nhận CSDL mới.")
        else:
            for d_id in installed:
                conf = dm.get_domain(d_id)
                print(f"• Domain: {d_id} | Tên: {conf.display_name} | Bảng: {len(conf.tables)} | Metrics: {len(conf.metrics)}")
        print("=" * 60)
        return

    # 3. Quét CSDL mới (Introspection)
    if args.db_name:
        domain_id = args.domain_id or args.db_name.lower().replace("-", "_")
        display_name = args.display_name or domain_id.replace("_", " ").title()

        print(f"[INTROSPECTION] Bắt đầu kết nối CSDL '{args.db_name}'...")
        client = get_warehouse_client(db_path=args.db_path)

        try:
            conn = client.get_connection()
            introspector = DatabaseIntrospector(connection=conn)
            print(f"[INTROSPECTION] Đang quét tables, columns, constraints từ CSDL '{args.db_name}'...")
            domain_config = introspector.introspect_information_schema(
                database_name=args.db_name,
                domain_id=domain_id,
                display_name=display_name
            )

            out_path = os.path.join(domains_dir, domain_id)
            introspector.export_to_yaml_folder(domain_config, out_path)
            dm.reload_domains()

            print("=" * 60)
            print(f"[SUCCESS] Đã nạp thành công domain mới: '{domain_id}'")
            print(f"• Số lượng bảng phát hiện: {len(domain_config.tables)}")
            print(f"• Số lượng quan hệ khóa ngoại: {len(domain_config.relationships)}")
            print(f"• File cấu hình đã lưu tại: {out_path}")

            # 4. Tự động sinh pipeline dbt nếu có cờ --auto-dbt
            if args.auto_dbt:
                print("=" * 60)
                print(f"[AUTO-DBT] Bắt đầu tự động tạo pipeline dbt cho domain '{domain_id}'...")
                gen = AutoDbtGenerator()
                dbt_res = gen.generate_domain_dbt(domain_config)
                print(f"[AUTO-DBT] Hoàn thành sinh dbt pipeline:")
                print(f"• Staging models đã tạo ({len(dbt_res['staging_models'])}): {', '.join(dbt_res['staging_models'])}")
                print(f"• Data Marts đã tạo ({len(dbt_res['marts_models'])}): {', '.join(dbt_res['marts_models'])}")
                print(f"• Semantic Metrics tự động: {dbt_res['metrics_count']} metrics")
                print(f"• Đã tự động cấu hình profiles.yml và nạp vào AI Agent!")
            print("=" * 60)
        except Exception as e:
            print(f"[ERROR] Lỗi khi kết nối hoặc quét CSDL: {e}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
