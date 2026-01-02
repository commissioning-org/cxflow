from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.core.state import logger
from app.schemas.legacy import (
    PBIDeployRequest,
    PBIDtapRequest,
    PBIRefreshRequest,
    PBITrainingWorkspacesRequest,
    PBIWorkspaceRequest,
)

router = APIRouter(tags=["powerbi"])


# Import Power BI client (optional)
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "powerbi"))
    from powerbi_client import PowerBIClient, PowerBIConfig, TokenCache  # type: ignore

    PBI_AVAILABLE = True
except ImportError:
    PBI_AVAILABLE = False
    logger.warning("Power BI client not available")


@router.get("/powerbi/health")
async def powerbi_health():
    if not PBI_AVAILABLE:
        return {"ok": False, "error": "Power BI client not installed", "configured": False}

    config = PowerBIConfig()
    configured = bool(getattr(config, "tenant_id", None) and getattr(config, "client_id", None))

    if not configured:
        return {"ok": False, "configured": False, "error": "Missing PBI_TENANT_ID or PBI_CLIENT_ID"}

    try:
        async with PowerBIClient(config) as client:
            await client.authenticate()
            tenant_id = getattr(config, "tenant_id", "")
            return {
                "ok": True,
                "configured": True,
                "auth_mode": getattr(config, "auth_mode", None),
                "tenant_id": (tenant_id[:8] + "...") if tenant_id else None,
            }
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


@router.get("/powerbi/workspaces")
async def powerbi_list_workspaces(
    top: int = Query(100, ge=1, le=5000),
    filter_: str | None = Query(None, alias="filter", description="OData filter"),
):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            workspaces = await client.list_workspaces(top=top, filter_=filter_)
            return {"workspaces": [ws.model_dump() for ws in workspaces], "count": len(workspaces)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/powerbi/workspaces")
async def powerbi_create_workspace(req: PBIWorkspaceRequest):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            workspace = await client.create_workspace(req.name)

            if req.capacity_id:
                await client.assign_to_capacity(workspace.id, req.capacity_id)
                await client.set_large_dataset_format(workspace.id)

            return {"ok": True, "workspace": workspace.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/powerbi/workspaces/{workspace_id}")
async def powerbi_delete_workspace(workspace_id: str):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            await client.delete_workspace(workspace_id)
            return {"ok": True, "deleted": workspace_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/powerbi/workspaces/dtap")
async def powerbi_generate_dtap(req: PBIDtapRequest):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            result = await client.generate_dtap_workspaces(req.base_name, req.capacity_id, req.stages)
            return {"ok": len(result.get("errors", [])) == 0, "workspaces": result.get("workspaces"), "errors": result.get("errors")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/workspaces/{workspace_id}/datasets")
async def powerbi_list_datasets(workspace_id: str):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            datasets = await client.list_datasets(workspace_id)
            return {"datasets": [ds.model_dump() for ds in datasets], "count": len(datasets)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/powerbi/datasets/refresh")
async def powerbi_trigger_refresh(req: PBIRefreshRequest):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            await client.trigger_refresh(req.workspace_id, req.dataset_id, req.notify_option)
            return {
                "ok": True,
                "message": "Refresh triggered successfully",
                "workspace_id": req.workspace_id,
                "dataset_id": req.dataset_id,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/workspaces/{workspace_id}/datasets/{dataset_id}/refresh-history")
async def powerbi_get_refresh_history(
    workspace_id: str,
    dataset_id: str,
    top: int = Query(100, ge=1, le=1000),
):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            history = await client.get_refresh_history(workspace_id, dataset_id, top)
            return {"refreshes": history, "count": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/pipelines")
async def powerbi_list_pipelines():
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            pipelines = await client.list_pipelines()
            return {"pipelines": [p.model_dump() for p in pipelines], "count": len(pipelines)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/powerbi/pipelines/deploy")
async def powerbi_deploy_pipeline(req: PBIDeployRequest):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            result = await client.deploy_pipeline(
                req.pipeline_id,
                req.source_stage,
                req.note or f"Deployed via API at {datetime.now().isoformat()}",
            )
            return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/workspaces/{workspace_id}/dataflows")
async def powerbi_list_dataflows(workspace_id: str):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            dataflows = await client.list_dataflows(workspace_id)
            return {"dataflows": [df.model_dump() for df in dataflows], "count": len(dataflows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/workspaces/{workspace_id}/reports")
async def powerbi_list_reports(workspace_id: str):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            reports = await client.list_reports(workspace_id)
            return {"reports": reports, "count": len(reports) if isinstance(reports, list) else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/powerbi/capacities")
async def powerbi_list_capacities():
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            capacities = await client.list_capacities()
            return {"capacities": capacities, "count": len(capacities) if isinstance(capacities, list) else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fabric/workspaces")
async def fabric_list_workspaces():
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            workspaces = await client.fabric_list_workspaces()
            return {"workspaces": workspaces, "count": len(workspaces) if isinstance(workspaces, list) else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fabric/workspaces/training")
async def fabric_generate_training_workspaces(req: PBITrainingWorkspacesRequest):
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")

    try:
        async with PowerBIClient() as client:
            result = await client.fabric_generate_training_workspaces(req.base_name, req.count, req.capacity_id)
            return {"ok": len(result.get("errors", [])) == 0, "workspaces": result.get("workspaces"), "errors": result.get("errors")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
