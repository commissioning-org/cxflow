from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.schemas.search import ReindexRequest, ReindexResponse, SearchResponse
from app.services.meilisearch import MeiliClient, MeiliError
from app.services.search_indexer import reindex_all, reindex_experiments, reindex_models

router = APIRouter(tags=["search"])


def _client_or_503() -> MeiliClient:
    if not settings.meili_url:
        raise HTTPException(status_code=503, detail="Search is not configured (ML_MEILI_URL is unset)")
    return MeiliClient(base_url=settings.meili_url, api_key=settings.meili_api_key, timeout_sec=settings.meili_timeout_sec)


@router.get("/search/health")
def search_health():
    if not settings.meili_url:
        return {"configured": False, "meili_url": None}

    client = _client_or_503()
    try:
        health = client.health()
        return {"configured": True, "meili_url": settings.meili_url, "health": health}
    except MeiliError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/search/models", response_model=SearchResponse)
def search_models(
    q: str = Query("", description="Query string"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    filter: str | None = Query(None, description="Meilisearch filter expression"),
):
    client = _client_or_503()
    try:
        out = client.search(settings.meili_models_index, q=q, limit=limit, offset=offset, filter=filter)
        return SearchResponse(
            index=settings.meili_models_index,
            query=q,
            hits=out.get("hits", []) if isinstance(out, dict) else [],
            offset=int(out.get("offset", offset)) if isinstance(out, dict) else offset,
            limit=int(out.get("limit", limit)) if isinstance(out, dict) else limit,
            estimated_total_hits=out.get("estimatedTotalHits") if isinstance(out, dict) else None,
            processing_time_ms=out.get("processingTimeMs") if isinstance(out, dict) else None,
            raw=out if isinstance(out, dict) else {"raw": out},
        )
    except MeiliError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/search/experiments", response_model=SearchResponse)
def search_experiments(
    q: str = Query("", description="Query string"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    filter: str | None = Query(None, description="Meilisearch filter expression"),
):
    client = _client_or_503()
    try:
        out = client.search(settings.meili_experiments_index, q=q, limit=limit, offset=offset, filter=filter)
        return SearchResponse(
            index=settings.meili_experiments_index,
            query=q,
            hits=out.get("hits", []) if isinstance(out, dict) else [],
            offset=int(out.get("offset", offset)) if isinstance(out, dict) else offset,
            limit=int(out.get("limit", limit)) if isinstance(out, dict) else limit,
            estimated_total_hits=out.get("estimatedTotalHits") if isinstance(out, dict) else None,
            processing_time_ms=out.get("processingTimeMs") if isinstance(out, dict) else None,
            raw=out if isinstance(out, dict) else {"raw": out},
        )
    except MeiliError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/search/reindex", response_model=ReindexResponse)
def reindex(req: ReindexRequest):
    client = _client_or_503()

    if req.dry_run:
        # Only compute counts; do not touch Meilisearch.
        # We still return index names to show what would be targeted.
        from app.services.search_indexer import build_experiment_documents, build_model_documents

        model_docs = len(build_model_documents()) if req.models else 0
        exp_docs = len(build_experiment_documents()) if req.experiments else 0
        return ReindexResponse(
            ok=True,
            models_index=settings.meili_models_index if req.models else None,
            experiments_index=settings.meili_experiments_index if req.experiments else None,
            model_docs=model_docs,
            experiment_docs=exp_docs,
            tasks=[],
            note="dry_run=true (no calls were made to Meilisearch)",
        )

    try:
        tasks = []
        model_docs = 0
        exp_docs = 0

        if req.models and req.experiments:
            res = reindex_all(client, batch_size=req.batch_size)
            tasks = [t.raw or {} for t in res.tasks]
            model_docs = res.model_docs
            exp_docs = res.experiment_docs
            return ReindexResponse(
                ok=True,
                models_index=res.models_index,
                experiments_index=res.experiments_index,
                model_docs=model_docs,
                experiment_docs=exp_docs,
                tasks=tasks,
            )

        if req.models:
            model_docs, model_tasks = reindex_models(client, batch_size=req.batch_size)
            tasks.extend([t.raw or {} for t in model_tasks])

        if req.experiments:
            exp_docs, exp_tasks = reindex_experiments(client, batch_size=req.batch_size)
            tasks.extend([t.raw or {} for t in exp_tasks])

        return ReindexResponse(
            ok=True,
            models_index=settings.meili_models_index if req.models else None,
            experiments_index=settings.meili_experiments_index if req.experiments else None,
            model_docs=model_docs,
            experiment_docs=exp_docs,
            tasks=tasks,
        )
    except MeiliError as e:
        raise HTTPException(status_code=502, detail=str(e))
