from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.experiments import create_experiment, get_experiment, list_runs, load_experiments_index, log_run
from app.schemas.legacy import ExperimentCreateRequest, RunLogRequest

router = APIRouter(tags=["experiments"])


@router.get("/experiments")
def list_experiments(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    idx = load_experiments_index()
    exps = idx.get("experiments", [])
    total = len(exps)
    return {"experiments": exps[offset : offset + limit], "total": total}


@router.post("/experiments")
def create_experiment_endpoint(req: ExperimentCreateRequest):
    return create_experiment(req.name, req.description, req.tags)


@router.post("/experiments/{experiment_id}/runs")
def log_run_endpoint(experiment_id: str, req: RunLogRequest):
    try:
        return log_run(
            experiment_id=experiment_id,
            run_id=req.run_id,
            metrics=req.metrics,
            params=req.params,
            tags=req.tags,
            model_id=req.model_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/experiments/{experiment_id}/runs")
def list_runs_endpoint(experiment_id: str, limit: int = Query(100, ge=1, le=1000)):
    exp = get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    runs = list_runs(experiment_id, limit=limit)
    return {"experiment_id": experiment_id, "runs": runs, "total": len(runs)}
