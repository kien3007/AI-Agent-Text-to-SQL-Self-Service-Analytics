"""
Domain Management & Bootstrap API Router.
Quản lý các domain nghiệp vụ, xem chi tiết metadata và kích hoạt bootstrap CSDL mới.
"""

import os
from fastapi import APIRouter, HTTPException, Depends
from app.core.domain_manager import DomainManager
from app.core.dbt_generator import AutoDbtGenerator
from app.core.introspection import DatabaseIntrospector
from app.db.doris_client import DorisClient
from app.schemas.api import DomainSwitchRequest, BootstrapRequest
from app.core.auth import require_admin, UserContext

router = APIRouter(prefix="/domains", tags=["Domains"])


@router.get("")
def list_domains():
    """Liệt kê toàn bộ các domain đang cài đặt trong hệ thống."""
    dm = DomainManager()
    domains_data = []
    active_d_id = dm.get_active_domain_config().domain_id if dm.list_domains() else None

    for d_id in dm.list_domains():
        conf = dm.get_domain(d_id)
        if conf:
            domains_data.append({
                "domain_id": conf.domain_id,
                "display_name": conf.display_name,
                "description": conf.description,
                "tables_count": len(conf.tables),
                "metrics_count": len(conf.metrics),
                "is_active": (conf.domain_id == active_d_id)
            })

    return {
        "active_domain": active_d_id,
        "domains": domains_data
    }


@router.get("/{domain_id}")
def get_domain_details(domain_id: str):
    """Lấy thông tin chi tiết bảng, cột, metrics của một domain cụ thể."""
    dm = DomainManager()
    conf = dm.get_domain(domain_id)
    if not conf:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' không tồn tại.")

    tables_summary = []
    for t_name, tbl in conf.tables.items():
        tables_summary.append({
            "table_name": t_name,
            "vn_name": tbl.vn_name,
            "description": tbl.description,
            "columns_count": len(tbl.columns),
            "columns": [
                {
                    "name": c_name,
                    "vn_name": c.vn_name,
                    "data_type": c.data_type,
                    "is_pk": c.is_primary_key,
                    "is_fk": bool(c.foreign_key)
                }
                for c_name, c in tbl.columns.items()
            ]
        })

    metrics_summary = [
        {
            "metric_id": m.metric_id,
            "label": m.vn_terms[0] if m.vn_terms else m.metric_id,
            "vn_terms": m.vn_terms,
            "sql_expression": m.sql_expression,
            "description": m.description
        }
        for m in conf.metrics.values()
    ]

    return {
        "domain_id": conf.domain_id,
        "display_name": conf.display_name,
        "description": conf.description,
        "tables": tables_summary,
        "metrics": metrics_summary,
        "relationships_count": len(conf.relationships)
    }


@router.post("/switch")
def switch_active_domain(req: DomainSwitchRequest, admin: UserContext = Depends(require_admin)):
    """Chuyển đổi domain hoạt động mặc định của hệ thống."""
    dm = DomainManager()
    try:
        dm.set_active_domain(req.domain_id)
        return {
            "status": "success",
            "message": f"Đã kích hoạt domain '{req.domain_id}' thành công.",
            "active_domain": req.domain_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bootstrap")
def bootstrap_new_database(req: BootstrapRequest, admin: UserContext = Depends(require_admin)):
    """
    Quét CSDL mới (MySQL/Doris), tự động sinh Domain YAML và dbt pipeline.
    """
    domain_id = req.domain_id or req.db_name.lower().replace("-", "_")
    display_name = req.display_name or domain_id.replace("_", " ").title()

    client = DorisClient(database=req.db_name)
    try:
        conn = client.get_connection()
        introspector = DatabaseIntrospector(connection=conn)
        domain_config = introspector.introspect_information_schema(
            database_name=req.db_name,
            domain_id=domain_id,
            display_name=display_name
        )

        dm = DomainManager()
        domains_dir = dm.domains_dir
        out_path = os.path.join(domains_dir, domain_id)
        introspector.export_to_yaml_folder(domain_config, out_path)
        dm.reload_domains()

        dbt_summary = None
        if req.auto_dbt:
            gen = AutoDbtGenerator()
            dbt_summary = gen.generate_domain_dbt(domain_config)

        return {
            "status": "success",
            "domain_id": domain_id,
            "tables_found": len(domain_config.tables),
            "relationships_found": len(domain_config.relationships),
            "dbt_generated": dbt_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi bootstrap CSDL '{req.db_name}': {e}")

@router.get("/{domain_id}/lineage")
def get_domain_lineage(domain_id: str):
    """
    Đọc data lineage từ dbt manifest.json nếu có.
    Trả về danh sách models và các bảng nguồn phụ thuộc.
    """
    import json
    import os
    
    dbt_project_dir = os.path.join(os.getcwd(), "dbt_project")
    manifest_path = os.path.join(dbt_project_dir, "target", "manifest.json")
    
    if not os.path.exists(manifest_path):
        # Fallback to ingestion lineage if dbt manifest not found
        ingestion_log = "data/ingestion_lineage.json"
        if os.path.exists(ingestion_log):
            with open(ingestion_log, "r", encoding="utf-8") as f:
                return {"type": "ingestion_lineage", "lineage": json.load(f)}
        return {"status": "no_lineage", "message": "Chưa có dbt manifest hoặc ingestion log."}
        
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        nodes = manifest.get("nodes", {})
        sources = manifest.get("sources", {})
        
        lineage_graph = {
            "models": [],
            "sources": []
        }
        
        for k, v in sources.items():
            lineage_graph["sources"].append({
                "id": k,
                "name": v.get("name"),
                "source_name": v.get("source_name")
            })
            
        for k, v in nodes.items():
            if v.get("resource_type") == "model":
                lineage_graph["models"].append({
                    "id": k,
                    "name": v.get("name"),
                    "depends_on": v.get("depends_on", {}).get("nodes", [])
                })
                
        return {"type": "dbt_lineage", "lineage": lineage_graph}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc dbt manifest: {e}")

@router.get("/{domain_id}/contract")
def get_domain_contract(domain_id: str):
    """Lấy Data Contract của domain."""
    dm = DomainManager()
    conf = dm.get_domain(domain_id)
    if not conf:
        raise HTTPException(status_code=404, detail="Domain không tồn tại.")
        
    return {
        "domain_id": conf.domain_id,
        "owner": conf.owner,
        "data_steward": conf.data_steward,
        "slack_channel": conf.slack_channel,
        "tables_guaranteed": list(conf.tables.keys()),
        "metrics_guaranteed": list(conf.metrics.keys()),
        "SLA": {
            "freshness": "Daily at 02:00 AM UTC",
            "availability": "99.9%"
        }
    }

@router.get("/{domain_id}/freshness")
def get_domain_freshness(domain_id: str):
    """Lấy Data Freshness của domain (mock from ingestion log)."""
    import os, json
    ingestion_log = "data/ingestion_lineage.json"
    if os.path.exists(ingestion_log):
        with open(ingestion_log, "r", encoding="utf-8") as f:
            log = json.load(f)
            return {
                "domain_id": domain_id,
                "last_updated": log.get("ingestion_time"),
                "status": "up_to_date"
            }
    return {
        "domain_id": domain_id,
        "last_updated": None,
        "status": "unknown"
    }
