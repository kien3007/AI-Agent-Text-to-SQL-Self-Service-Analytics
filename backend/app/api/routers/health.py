"""
Health Check & Status API Router.
Cung cấp trạng thái hoạt động của hệ thống, CSDL và các domain đã nạp.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import time

from app.core.domain_manager import DomainManager
from app.db.warehouse_client import get_warehouse_client
from app.agent.llm_client import DualModelLLM
from app.rag.qdrant_provider import get_qdrant_client
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
def health_check():
    """Kiểm tra tình trạng sống của API server, Data Warehouse (DuckDB), Qdrant Vector DB và các domain."""
    dm = DomainManager()
    domains = dm.list_domains()
    active_domain_cfg = dm.get_active_domain_config()
    active_domain = active_domain_cfg.domain_id if active_domain_cfg else None

    # Check Data Warehouse (DuckDB)
    warehouse_status = "unhealthy"
    try:
        client = get_warehouse_client()
        res = client.execute_query_dict("SELECT 1")
        if res:
            warehouse_status = "healthy"
    except Exception:
        pass

    # Check LLM
    llm_status = "healthy"

    # Check Qdrant Vector DB (On-premise / Server)
    qdrant_status = "unhealthy"
    try:
        qdrant_client = get_qdrant_client()
        qdrant_client.get_collections()
        qdrant_status = "healthy"
    except Exception:
        pass

    ownership = None
    if active_domain_cfg:
        ownership = {
            "owner": active_domain_cfg.owner,
            "data_steward": active_domain_cfg.data_steward,
            "slack_channel": active_domain_cfg.slack_channel
        }

    return {
        "status": "healthy" if warehouse_status == "healthy" and qdrant_status == "healthy" else "degraded",
        "service": "AI-Agent-Text-to-SQL",
        "warehouse_engine": getattr(settings, "WAREHOUSE_BACKEND", "duckdb"),
        "loaded_domains": domains,
        "active_domain": active_domain,
        "domain_ownership": ownership,
        "total_domains": len(domains),
        "dependencies": {
            "warehouse": warehouse_status,
            "llm": llm_status,
            "qdrant": qdrant_status
        }
    }

class BenchmarkRequest(BaseModel):
    queries: list[str]
    domain_id: str

@router.post("/benchmark")
def run_benchmark(req: BenchmarkRequest):
    """
    Benchmark endpoint chạy nhiều truy vấn đồng thời và tính P95/P99 latency.
    """
    from app.agent.graph import AgentOrchestrator
    orchestrator = AgentOrchestrator(use_explain=False)
    
    results = []
    start_all = time.time()
    
    for q in req.queries:
        t0 = time.time()
        try:
            state = orchestrator.invoke(q, req.domain_id)
            results.append({
                "query": q,
                "status": "success",
                "latency_ms": (time.time() - t0) * 1000,
                "sql": state.sql_query
            })
        except Exception as e:
            results.append({
                "query": q,
                "status": "error",
                "error": str(e),
                "latency_ms": (time.time() - t0) * 1000
            })
            
    latencies = [r["latency_ms"] for r in results if r["status"] == "success"]
    latencies.sort()
    
    success_count = len(latencies)
    p95 = latencies[int(success_count * 0.95)] if latencies else 0
    p99 = latencies[int(success_count * 0.99)] if latencies else 0
    avg_latency = sum(latencies) / success_count if latencies else 0
    
    return {
        "total_queries": len(req.queries),
        "successful_queries": success_count,
        "total_time_s": time.time() - start_all,
        "summary": {
            "success_rate": success_count / len(req.queries) if req.queries else 0,
            "avg_latency_ms": avg_latency,
            "p50_ms": latencies[success_count // 2] if latencies else 0,
            "p95_ms": p95,
            "p99_ms": p99
        },
        "details": results
    }
