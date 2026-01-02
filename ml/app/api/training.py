from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.core.automl import run_training
from app.core.state import _training_jobs, logger
from app.schemas.legacy import AsyncTrainResponse, JobStatus, JobStatusResponse, TrainRequest, TrainResponse

router = APIRouter(tags=["training"])


@router.post("/train", response_model=TrainResponse)
def train(req: TrainRequest):
    """Train a model synchronously."""
    try:
        df = pd.DataFrame(req.rows)
        result = run_training(
            df=df,
            target=req.target,
            problem=req.problem,
            metric=req.metric,
            test_size=req.test_size,
            random_state=req.random_state,
            enable_cv=req.enable_cv,
            enable_tuning=req.enable_tuning,
            model_name=req.model_name,
            tags=req.tags,
            description=req.description,
            experiment_id=req.experiment_id,
        )

        return TrainResponse(
            model_id=result["model_id"],
            model_name=result.get("model_name"),
            problem=result["problem"],
            metric=result["metric"],
            score=result["score"],
            cv_score=result.get("cv_score"),
            cv_std=result.get("cv_std"),
            selected_model=result["selected"],
            features=result["features"],
            training_time_sec=result["training_time_sec"],
            row_count=result["row_count"],
            created_at=result["created_at"],
            tags=result.get("tags", []),
        )
    except ValueError as e:
        logger.error(f"Training validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Training failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/async", response_model=AsyncTrainResponse)
async def train_async(req: TrainRequest, background_tasks: BackgroundTasks):
    """Start an asynchronous training job."""
    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    _training_jobs[job_id] = {
        "status": JobStatus.PENDING.value,
        "model_id": None,
        "error": None,
        "progress": 0.0,
        "created_at": created_at,
        "completed_at": None,
    }

    def _run_async():
        try:
            _training_jobs[job_id]["status"] = JobStatus.RUNNING.value
            df = pd.DataFrame(req.rows)
            result = run_training(
                df=df,
                target=req.target,
                problem=req.problem,
                metric=req.metric,
                test_size=req.test_size,
                random_state=req.random_state,
                enable_cv=req.enable_cv,
                enable_tuning=req.enable_tuning,
                model_name=req.model_name,
                tags=req.tags,
                description=req.description,
                experiment_id=req.experiment_id,
                job_id=job_id,
            )
            _training_jobs[job_id]["status"] = JobStatus.COMPLETED.value
            _training_jobs[job_id]["model_id"] = result["model_id"]
            _training_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.exception(f"Async training job {job_id} failed")
            _training_jobs[job_id]["status"] = JobStatus.FAILED.value
            _training_jobs[job_id]["error"] = str(e)
            _training_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    background_tasks.add_task(_run_async)

    return AsyncTrainResponse(
        job_id=job_id,
        status=JobStatus.PENDING.value,
        message="Training job started. Poll /train/status/{job_id} for updates.",
    )


@router.get("/train/status/{job_id}", response_model=JobStatusResponse)
def train_status(job_id: str):
    if job_id not in _training_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _training_jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        model_id=job.get("model_id"),
        error=job.get("error"),
        progress=job.get("progress", 0.0),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


@router.get("/train/jobs")
def list_training_jobs(status: str | None = Query(None), limit: int = Query(200, ge=1, le=5000)):
    items = []
    for jid, job in _training_jobs.items():
        if status and job.get("status") != status:
            continue
        items.append({"job_id": jid, **job})
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"jobs": items[:limit], "total": len(items)}


@router.post("/train/cancel/{job_id}")
def cancel_training_job(job_id: str):
    if job_id not in _training_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _training_jobs[job_id]
    if job.get("status") in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        return {"ok": False, "job_id": job_id, "status": job.get("status"), "message": "Job already finished"}

    job["status"] = JobStatus.CANCELLED.value
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["error"] = "Cancelled by user"
    return {"ok": True, "job_id": job_id, "status": JobStatus.CANCELLED.value}
