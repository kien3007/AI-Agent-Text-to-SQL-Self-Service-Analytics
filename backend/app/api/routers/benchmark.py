"""
Benchmark API Router.
Cung cấp endpoints để lấy kết quả benchmark, danh sách golden dataset và kích hoạt chạy test suite thực tế.
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])

# Root paths
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent.parent.parent.parent
_EVAL_BENCHMARK_DIR = _PROJECT_ROOT / "evaluation" / "benchmark"
_RESULTS_FILE = _EVAL_BENCHMARK_DIR / "benchmark_results.json"
_DATASET_FILE = _EVAL_BENCHMARK_DIR / "golden_dataset.json"

# State lock to prevent concurrent benchmark runs
_benchmark_lock = asyncio.Lock()
_is_running = False
_current_status = "IDLE"


class BenchmarkRunRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Số lượng câu hỏi cần chạy (mặc định chạy toàn bộ)")
    dataset_path: Optional[str] = Field(None, description="Đường dẫn file dataset nếu muốn chỉ định file khác")


@router.get("/status")
def get_benchmark_status():
    """Kiểm tra trạng thái thực thi hiện tại của bộ Benchmark."""
    global _is_running, _current_status
    return {
        "is_running": _is_running,
        "status": _current_status,
        "has_cached_results": _RESULTS_FILE.exists()
    }


@router.get("/dataset")
def get_golden_dataset():
    """Truy xuất danh sách các câu hỏi vàng (Golden Dataset) dùng để đánh giá chuẩn."""
    if not _DATASET_FILE.exists():
        raise HTTPException(status_code=404, detail="File golden_dataset.json không tồn tại.")
    try:
        with open(_DATASET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "total_items": len(data),
            "dataset": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi đọc golden_dataset.json: {e}")


@router.get("/results")
def get_benchmark_results():
    """Lấy kết quả benchmark gần nhất từ file lưu trữ."""
    if not _RESULTS_FILE.exists():
        # Nếu chưa chạy benchmark, load dataset để hiển thị test cases mẫu với trạng thái PENDING
        if _DATASET_FILE.exists():
            try:
                with open(_DATASET_FILE, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                return {
                    "timestamp": "Chưa thực thi",
                    "total_queries": len(dataset),
                    "metrics": {
                        "valid_sql_rate_percent": 0.0,
                        "guardrail_safety_rate_percent": 100.0,
                        "clarification_detection_rate_percent": 0.0,
                        "avg_latency_sec": 0.0,
                        "p50_latency_sec": 0.0,
                        "p90_latency_sec": 0.0
                    },
                    "breakdown": {
                        "sql_queries_evaluated": 0,
                        "sql_queries_passed": 0,
                        "guardrail_queries_evaluated": 0,
                        "guardrail_queries_passed": 0,
                        "clarification_queries_evaluated": 0,
                        "clarification_queries_passed": 0
                    },
                    "results": [
                        {
                            "id": item["id"],
                            "query": item["query"],
                            "complexity": item.get("complexity", "medium"),
                            "category": item.get("category", "general"),
                            "latency_sec": 0.0,
                            "passed": False,
                            "notes": "Chưa chạy kiểm thử",
                            "generated_sql": "",
                            "needs_clarification": False,
                            "is_blocked": False
                        }
                        for item in dataset
                    ]
                }
            except Exception:
                pass
        raise HTTPException(status_code=404, detail="Chưa có kết quả benchmark nào được lưu.")

    try:
        with open(_RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi đọc benchmark_results.json: {e}")


@router.post("/run")
async def trigger_benchmark_run(req: BenchmarkRunRequest = BenchmarkRunRequest()):
    """
    Kích hoạt chạy bộ kiểm thử Benchmark Spider/BIRD & Guardrails trên hệ thống thực tế.
    Chạy trong thread pool không gây nghẽn luồng FastAPI.
    """
    global _is_running, _current_status

    if _benchmark_lock.locked():
        raise HTTPException(status_code=409, detail="Bộ benchmark hiện đang trong quá trình chạy, vui lòng đợi hoàn tất.")

    async with _benchmark_lock:
        _is_running = True
        _current_status = "RUNNING"
        try:
            # Đảm bảo import được module evaluation
            if str(_PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(_PROJECT_ROOT))

            from evaluation.scripts.run_benchmark import run_benchmark

            ds_path = req.dataset_path or str(_DATASET_FILE)
            out_dir = str(_EVAL_BENCHMARK_DIR)
            limit = req.limit

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: run_benchmark(dataset_path=ds_path, output_dir=out_dir, limit=limit)
            )

            _current_status = "COMPLETED"
            return {
                "status": "success",
                "message": f"Đã chạy xong benchmark {len(results.get('results', []))} câu hỏi kiểm thử.",
                "data": results
            }
        except Exception as e:
            _current_status = f"FAILED: {str(e)}"
            raise HTTPException(status_code=500, detail=f"Lỗi khi chạy benchmark: {e}")
        finally:
            _is_running = False
