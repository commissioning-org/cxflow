from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.state import logger
from app.schemas.legacy import (
    SupersetDashboardCreateRequest,
    SupersetDatasetRefreshRequest,
    SupersetSQLExecuteRequest,
)

# Import Superset client
try:
    from superset.client import SupersetClient  # type: ignore
    from superset.config import SupersetConfig  # type: ignore

    SUPERSET_AVAILABLE = True
except Exception as e:  # pragma: no cover
    SUPERSET_AVAILABLE = False
    _IMPORT_ERROR = str(e)
    logger.warning("Superset client not available: %s", e)


router = APIRouter(tags=["superset"])


def _get_client() -> SupersetClient:
    if not SUPERSET_AVAILABLE:
        raise HTTPException(status_code=503, detail=f"Superset integration not available: {_IMPORT_ERROR}")

    cfg = SupersetConfig.from_env()
    client = SupersetClient(
        base_url=cfg.base_url,
        username=cfg.username,
        password=cfg.password,
        api_key=cfg.api_key,
        config=cfg,
    )

    # If using username/password (no API key), login to obtain access + CSRF.
    if not cfg.api_key and cfg.username and cfg.password:
        client.login()

    return client


@router.get("/superset/health")
def superset_health():
    """Health check for Superset integration."""
    client = _get_client()
    try:
        health = client.health_check()
        version = {}
        try:
            version = client.get_version()
        except Exception:
            version = {}
        return {"ok": True, "health": health, "version": version}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/superset/dashboards")
def superset_list_dashboards(
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=500),
):
    client = _get_client()
    try:
        return client.get_dashboards(page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/superset/dashboards")
def superset_create_dashboard(req: SupersetDashboardCreateRequest):
    client = _get_client()
    try:
        payload = {k: v for k, v in req.model_dump().items() if v is not None}
        return client.create_dashboard(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/superset/dashboards/{dashboard_id}")
def superset_delete_dashboard(dashboard_id: int):
    client = _get_client()
    try:
        return client.delete_dashboard(dashboard_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/superset/datasets")
def superset_list_datasets(
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=500),
):
    client = _get_client()
    try:
        return client.get_datasets(page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/superset/datasets/{dataset_id}/refresh")
def superset_refresh_dataset(dataset_id: int):
    client = _get_client()
    try:
        return client.refresh_dataset(dataset_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/superset/datasets/refresh")
def superset_refresh_dataset_by_body(req: SupersetDatasetRefreshRequest):
    """Refresh a dataset by id (body), convenient for automation macros."""
    return superset_refresh_dataset(req.dataset_id)


@router.post("/superset/sql/execute")
def superset_execute_sql(req: SupersetSQLExecuteRequest):
    client = _get_client()
    try:
        return client.execute_sql(
            database_id=req.database_id,
            sql=req.sql,
            schema=req.schema,
            run_async=req.run_async,
            select_as_cta=req.select_as_cta,
            ctas_method=req.ctas_method,
            tmp_table_name=req.tmp_table_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
