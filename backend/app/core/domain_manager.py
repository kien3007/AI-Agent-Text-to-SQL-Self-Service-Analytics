"""
Domain Manager (Bộ Quản lý Domain & Định tuyến Domain - Domain Router).
Chịu trách nhiệm:
1. Nạp và quản lý toàn bộ các DomainConfig từ thư mục domains/.
2. Hỗ trợ đăng ký domain động hoặc chuyển đổi domain runtime.
3. Cung cấp thuật toán Semantic & Keyword Domain Detection để định tuyến câu hỏi vào đúng Domain.
"""

import os
import sys
import re
from typing import Dict, Any, List, Optional, Tuple

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.schemas.domain import DomainConfig


class DomainManager:
    """
    Quản lý danh mục các Domain nghiệp vụ trong hệ thống (Singleton/Registry Pattern).
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

        base_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.domains_dir = domains_dir or os.path.join(base_backend, "domains")
        self._domains: Dict[str, DomainConfig] = {}
        self._active_domain_id: str = "real_estate"

        # Tự động quét và nạp các domain có sẵn
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
                    print(f"[DomainManager] Cảnh báo lỗi nạp domain từ '{item}': {e}")

        # Tự động cập nhật active domain nếu domain hiện tại không còn tồn tại
        if self._active_domain_id not in self._domains and self._domains:
            self._active_domain_id = next(iter(self._domains))

    def register_domain(self, domain_config: DomainConfig):
        """Đăng ký trực tiếp một domain cấu hình."""
        self._domains[domain_config.domain_id] = domain_config

    def get_domain(self, domain_id: str) -> Optional[DomainConfig]:
        """Lấy thông tin cấu hình của domain theo ID."""
        return self._domains.get(domain_id)

    def list_domains(self) -> List[str]:
        """Trả về danh sách các domain_id đang được hỗ trợ."""
        return list(self._domains.keys())

    def set_active_domain(self, domain_id: str):
        """Đặt domain mặc định đang làm việc."""
        if domain_id not in self._domains:
            raise ValueError(f"Domain '{domain_id}' chưa được đăng ký trong hệ thống.")
        self._active_domain_id = domain_id

    def get_active_domain() -> DomainConfig:
        """Trả về domain đang được kích hoạt."""
        return self.get_domain(self._active_domain_id)

    def get_active_domain_config(self) -> DomainConfig:
        """Trả về domain đang được kích hoạt."""
        if self._active_domain_id in self._domains:
            return self._domains[self._active_domain_id]
        if self._domains:
            first_key = next(iter(self._domains))
            return self._domains[first_key]
        raise RuntimeError("Không có domain nào được đăng ký trong hệ thống!")

    def detect_domain(self, query: str) -> str:
        """
        Bộ định tuyến sơ bộ (Domain Router) dựa trên so khớp trọng số từ khóa:
        1. Từ khóa đặc trưng của domain (domain_keywords).
        2. Tên tiếng Việt và từ đồng nghĩa của các cột.
        3. Thuật ngữ của các chỉ số nghiệp vụ (metrics).
        Nếu không có domain nào vượt trội, trả về domain đang hoạt động mặc định.
        """
        cleaned_query = query.lower()
        domain_scores: Dict[str, float] = {d_id: 0.0 for d_id in self._domains}

        for d_id, domain in self._domains.items():
            score = 0.0

            # 1. Điểm từ domain_keywords (Trọng số 3.0)
            for kw in domain.domain_keywords:
                if re.search(rf"\b{re.escape(kw.lower())}\b", cleaned_query):
                    score += 3.0

            # 2. Điểm từ tên bảng và tên tiếng Việt bảng (Trọng số 2.5)
            for t_name, table in domain.tables.items():
                if t_name.lower() in cleaned_query:
                    score += 2.5
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
        if self._domains:
            return next(iter(self._domains))
        return self._active_domain_id
