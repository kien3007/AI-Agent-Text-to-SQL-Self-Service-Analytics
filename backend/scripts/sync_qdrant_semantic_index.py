"""
CLI Script đồng bộ Semantic Metadata và Vector Embeddings vào Qdrant.
Được gọi từ Airflow DAG hoặc chạy thủ công sau khi có schema mới / nạp dữ liệu mới.

Cách dùng:
  python backend/scripts/sync_qdrant_semantic_index.py --domain vietnam_ecommerce --force
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import AppSettings
from app.core.domain_manager import DomainManager
from app.rag.profiling_graph import BilingualDataProfilingGraph

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyncSemanticIndex")


def sync_domain_index(domain_id: str = "vietnam_ecommerce", force: bool = True):
    """Lập chỉ mục toàn bộ metadata, cột và metrics của domain vào Qdrant."""
    logger.info("================================================================")
    logger.info(f" Khởi động Semantic & Vector DB Indexing cho domain: {domain_id}")
    logger.info(f" - Qdrant Host: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    logger.info("================================================================")

    dm = DomainManager()
    conf = dm.get_domain(domain_id)
    if not conf:
        logger.warning(f"Domain '{domain_id}' không tồn tại trong config. Sử dụng active domain...")
        conf = dm.get_active_domain_config()
        domain_id = conf.domain_id

    try:
        graph = BilingualDataProfilingGraph(domain_id=domain_id, in_memory=False)
        graph.index_all(force=force)
        logger.info(f" Hoàn tất lập chỉ mục thành công cho domain '{domain_id}'!")
        return {
            "status": "SUCCESS",
            "domain_id": domain_id,
            "tables_indexed": len(conf.tables),
            "metrics_indexed": len(conf.metrics)
        }
    except Exception as e:
        logger.error(f"❌ Lỗi khi đồng bộ chỉ mục ngữ nghĩa Qdrant: {e}")
        # Thử fallback in-memory nếu không kết nối được Qdrant server
        logger.warning("Thử fallback sang in-memory Qdrant store để kiểm tra tính hợp lệ của graph...")
        try:
            mem_graph = BilingualDataProfilingGraph(domain_id=domain_id, in_memory=True)
            mem_graph.index_all(force=True)
            logger.info(" Fallback in-memory index thành công.")
            return {
                "status": "FALLBACK_IN_MEMORY",
                "domain_id": domain_id,
                "warning": str(e)
            }
        except Exception as fallback_err:
            logger.error(f"Fallback in-memory cũng thất bại: {fallback_err}")
            raise e


def main():
    parser = argparse.ArgumentParser(description="Đồng bộ Semantic Vector Embeddings vào Qdrant")
    parser.add_argument("--domain", type=str, default="vietnam_ecommerce", help="Domain ID cần index")
    parser.add_argument("--force", action="store_true", default=True, help="Ép buộc re-index toàn bộ")
    args = parser.parse_args()

    result = sync_domain_index(domain_id=args.domain, force=args.force)
    print(f"\nKết quả: {result}")


if __name__ == "__main__":
    main()
