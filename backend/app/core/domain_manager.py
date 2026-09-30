"""
Domain Manager (Bộ Quản lý Domain & Định tuyến Domain - Domain Router).
Chịu trách nhiệm:
1. Nạp và quản lý toàn bộ các DomainConfig từ thư mục domains/ hoặc động từ CSDL.
2. Hỗ trợ kết nối và tự động khám phá cấu trúc CSDL runtime (PostgreSQL, MySQL, SQLite, DuckDB...).
3. Cung cấp thuật toán Semantic & Keyword Domain Detection để định tuyến câu hỏi vào đúng Domain/Database.
"""

import os
import sys
import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig
from app.db.warehouse_client import _ROUTER, get_warehouse_client
from app.core.introspection import DatabaseIntrospector

logger = logging.getLogger("DomainManager")


class DomainManager:
    """
    Quản lý danh mục các Domain nghiệp vụ trong hệ thống (Singleton/Registry Pattern).
    Hỗ trợ cả Static YAML configs và Dynamic Database Introspection.
    """
    _instance: Optional["DomainManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DomainManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, domains_dir: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        base_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.domains_dir = domains_dir or os.path.join(base_backend, "domains")
        self._domains: Dict[str, DomainConfig] = {}
        self._active_domain_id: str = "default"

        # Tự động quét và nạp các domain có sẵn nếu thư mục tồn tại
        self.reload_domains()
        self._initialized = True

    def reload_domains(self):
        """Quét lại toàn bộ thư mục domains/ để nạp cấu hình mới nhất."""
        self._domains.clear()
        if not os.path.exists(self.domains_dir):
            return

        for item in os.listdir(self.domains_dir):
            item_path = os.path.join(self.domains_dir, item)
            if os.path.isdir(item_path):
                try:
                    config = DomainConfig.load_from_folder(item_path)
                    self._domains[config.domain_id] = config
                except Exception as e:
                    logger.warning(f"Lỗi nạp domain từ '{item}': {e}")

        # Tự động cập nhật active domain
        if self._domains:
            if self._active_domain_id not in self._domains:
                self._active_domain_id = next(iter(self._domains))
        else:
            self.get_active_domain_config()

    def register_domain(self, domain_config: DomainConfig):
        """Đăng ký trực tiếp một domain cấu hình."""
        self._domains[domain_config.domain_id] = domain_config
        self._active_domain_id = domain_config.domain_id

    def register_dynamic_domain(self, domain_config: DomainConfig):
        """Alias cho register_domain."""
        self.register_domain(domain_config)

    def connect_and_register_database(
        self,
        connection_url_or_client: Any,
        domain_id: Optional[str] = None,
        db_name: Optional[str] = None,
        display_name: Optional[str] = None,
        schema: Optional[str] = None,
        register_all_schemas: bool = False,
        save_yaml: bool = False
    ) -> DomainConfig:
        """
        Kết nối tới một CSDL mới (URL, JDBC hoặc client), tự động crawl schema,
        tạo DomainConfig và đăng ký vào DomainManager lẫn WarehouseRouter.
        Hỗ trợ CSDL đa schema (SQL Server, PostgreSQL) tự động bóc tách từng schema thành 1 domain.
        """
        # 1. Đăng ký CSDL gốc vào Warehouse Router
        key = domain_id or schema or db_name or "db"
        client = _ROUTER.register_database(key, connection_url_or_client)
        introspector = DatabaseIntrospector()

        # 2. Xử lý trường hợp quét toàn bộ schemas (register_all_schemas=True hoặc phát hiện multi-schema)
        engine = getattr(client, "engine", None)
        if engine and (register_all_schemas or (schema is None and any(d in getattr(client, "dialect_name", "") for d in ("mssql", "sqlserver", "postgresql")))):
            all_configs = introspector.introspect_all_schemas(engine)
            if all_configs:
                for cfg in all_configs:
                    self.register_domain(cfg)
                    _ROUTER.register_database(cfg.domain_id, client)
                    if save_yaml and self.domains_dir:
                        out_folder = os.path.join(self.domains_dir, cfg.domain_id)
                        introspector.export_to_yaml_folder(cfg, out_folder)

                # Chọn domain active: ưu tiên domain_id nếu người dùng truyền, hoặc domain đầu tiên
                target_active = domain_id if (domain_id and domain_id in self._domains) else all_configs[0].domain_id
                self.set_active_domain(target_active)
                logger.info(f"Đã kết nối và đăng ký đồng loạt {len(all_configs)} business schemas/domains vào hệ thống.")
                return self.get_domain(target_active)

        # 3. Trường hợp quét 1 schema cụ thể hoặc CSDL single-schema thông thường
        domain_cfg = introspector.introspect_any(
            target=client,
            database_name=db_name or key,
            domain_id=domain_id or schema or key,
            display_name=display_name,
            schema=schema
        )

        # 4. Lưu YAML nếu được yêu cầu
        if save_yaml and self.domains_dir:
            out_folder = os.path.join(self.domains_dir, domain_cfg.domain_id)
            introspector.export_to_yaml_folder(domain_cfg, out_folder)

        # 5. Đăng ký vào bộ nhớ
        self.register_domain(domain_cfg)
        _ROUTER.register_database(domain_cfg.domain_id, client)
        self.set_active_domain(domain_cfg.domain_id)
        logger.info(f"Đã kết nối và kích hoạt domain '{domain_cfg.domain_id}' ({len(domain_cfg.tables)} bảng).")
        return domain_cfg

    def get_domain(self, domain_id: str) -> Optional[DomainConfig]:
        """Lấy thông tin cấu hình của domain theo ID."""
        if domain_id in self._domains:
            return self._domains[domain_id]
        if domain_id == "default":
            return self.get_active_domain_config()
        return None

    def list_domains(self) -> List[str]:
        """Trả về danh sách các domain_id đang được hỗ trợ."""
        return list(self._domains.keys())

    def set_active_domain(self, domain_id: str):
        """Đặt domain mặc định đang làm việc."""
        if domain_id not in self._domains:
            # Nếu chưa có, tạo placeholder
            self._domains[domain_id] = DomainConfig(
                domain_id=domain_id,
                display_name=domain_id.replace("_", " ").title(),
                description=f"Domain {domain_id}",
                tables={},
                relationships=[],
                metrics={}
            )
        self._active_domain_id = domain_id

    def get_active_domain(self) -> DomainConfig:
        """Trả về domain đang được kích hoạt."""
        return self.get_active_domain_config()

    def get_active_domain_config(self) -> DomainConfig:
        """Trả về domain đang được kích hoạt (không bao giờ crash nếu rỗng)."""
        if self._active_domain_id in self._domains:
            return self._domains[self._active_domain_id]
        if self._domains:
            first_key = next(iter(self._domains))
            self._active_domain_id = first_key
            return self._domains[first_key]

        # Tạo domain mặc định fallback an toàn khi hệ thống vừa khởi động chưa cắm CSDL nào
        default_cfg = DomainConfig(
            domain_id="default",
            display_name="Default Database",
            description="Cơ sở dữ liệu mặc định (chờ kết nối)",
            tables={},
            relationships=[],
            metrics={}
        )
        self._domains["default"] = default_cfg
        self._active_domain_id = "default"
        return default_cfg

    def detect_domain(self, query: str) -> str:
        """
        Bộ định tuyến sơ bộ (Domain Router) dựa trên so khớp trọng số từ khóa:
        1. Từ khóa đặc trưng của domain (domain_keywords).
        2. Tên tiếng Việt và từ đồng nghĩa của các cột.
        3. Thuật ngữ của các chỉ số nghiệp vụ (metrics).
        Nếu không có domain nào vượt trội, trả về domain đang hoạt động mặc định.
        """
        if not self._domains:
            return "default"
        if len(self._domains) == 1:
            return next(iter(self._domains))

        cleaned_query = query.lower()
        domain_scores: Dict[str, float] = {d_id: 0.0 for d_id in self._domains}

        for d_id, domain in self._domains.items():
            score = 0.0

            # 1. Điểm từ domain_id và domain_keywords (Trọng số 2.0 - 3.0)
            all_kw = set(domain.domain_keywords)
            all_kw.add(d_id)
            for kw in all_kw:
                kw_l = kw.lower()
                if re.search(rf"\b{re.escape(kw_l)}\b", cleaned_query):
                    score += 3.0
                for sub_kw in re.split(r"[_\s]+", kw_l):
                    if len(sub_kw) >= 3 and re.search(rf"\b{re.escape(sub_kw)}\b", cleaned_query):
                        score += 2.0

            # 2. Điểm từ tên bảng, sub-tokens và tên tiếng Việt bảng (Trọng số 2.0 - 3.0)
            for t_name, table in domain.tables.items():
                pure_t = t_name.split(".")[-1].lower()
                for sub_t in pure_t.split("_"):
                    if len(sub_t) >= 3 and re.search(rf"\b{re.escape(sub_t)}\b", cleaned_query):
                        score += 2.5
                if pure_t in cleaned_query or t_name.lower() in cleaned_query:
                    score += 3.0
                if table.vn_name and table.vn_name.lower() in cleaned_query:
                    score += 2.5

                # 3. Điểm từ cột và từ đồng nghĩa (Trọng số 1.0 - 1.5)
                for c_name, col in table.columns.items():
                    if col.vn_name and col.vn_name.lower() in cleaned_query:
                        score += 1.5
                    for syn in col.synonyms:
                        if len(syn) >= 3 and syn.lower() in cleaned_query:
                            score += 1.0

            # 4. Điểm từ Metrics (Trọng số 2.0)
            for m_id, metric in domain.metrics.items():
                for v_term in metric.vn_terms:
                    if v_term.lower() in cleaned_query:
                        score += 2.0

            domain_scores[d_id] = score

        # Tìm domain có điểm cao nhất
        if domain_scores:
            best_domain = max(domain_scores, key=domain_scores.get)
            if domain_scores[best_domain] > 0.0:
                return best_domain

        if self._active_domain_id in self._domains:
            return self._active_domain_id
        return next(iter(self._domains))

    def reset(self):
        """Reset danh sách domain về trạng thái ban đầu (dùng trong test)."""
        self._domains.clear()
        self._active_domain_id = "default"
