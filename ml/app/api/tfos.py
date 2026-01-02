from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.core.state import MODELS_DIR, _tfos_jobs, logger
from app.schemas.legacy import JobStatus, TFoSJobRequest, TFoSJobResponse, TFoSJobStatus

router = APIRouter(tags=["tfos"])


@router.post("/tfos/submit", response_model=TFoSJobResponse)
async def tfos_submit(req: TFoSJobRequest, background_tasks: BackgroundTasks):
    import shutil
    import subprocess
    import uuid

    job_id = req.job_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    model_dir = MODELS_DIR / "tfos" / job_id
    log_dir = Path("/tmp/tfos_logs") / job_id
    export_dir = MODELS_DIR / "tfos_export" / job_id

    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    _tfos_jobs[job_id] = {
        "status": JobStatus.PENDING.value,
        "progress": 0.0,
        "model_dir": str(model_dir),
        "export_dir": str(export_dir),
        "log_dir": str(log_dir),
        "error": None,
        "created_at": created_at,
        "completed_at": None,
        "metrics": None,
        "config": req.model_dump(),
    }

    def _run_tfos():
        try:
            _tfos_jobs[job_id]["status"] = JobStatus.RUNNING.value
            _tfos_jobs[job_id]["progress"] = 0.1

            spark_submit = shutil.which("spark-submit") or os.environ.get("SPARK_HOME", "/opt/spark") + "/bin/spark-submit"
            training_script = os.environ.get("TFOS_TRAINING_SCRIPT", "/app/tfos_training_script.py")

            if not os.path.isfile(training_script):
                training_script = str(Path(__file__).resolve().parents[3] / "ingestion" / "tfos_training_script.py")

            cmd = [
                spark_submit,
                "--master",
                req.spark_master,
                "--conf",
                f"spark.executor.instances={req.cluster_size}",
                "--conf",
                f"spark.executor.memory={req.executor_memory}",
                training_script,
                "--cluster_size",
                str(req.cluster_size),
                "--num_ps",
                str(req.num_ps),
                "--epochs",
                str(req.epochs),
                "--batch_size",
                str(req.batch_size),
                "--learning_rate",
                str(req.learning_rate),
                "--data_path",
                req.data_path,
                "--target_column",
                req.target_column,
                "--format",
                req.format,
                "--model_dir",
                str(model_dir),
                "--export_dir",
                str(export_dir),
                "--input_mode",
                req.input_mode,
            ]

            if req.tensorboard:
                cmd.append("--tensorboard")

            if req.master_node:
                cmd.extend(["--master_node", req.master_node])

            logger.info(f"Starting TFoS job {job_id}: {' '.join(cmd[:5])}...")

            _tfos_jobs[job_id]["progress"] = 0.2
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            (log_dir / "stdout.log").write_text(result.stdout)
            (log_dir / "stderr.log").write_text(result.stderr)

            _tfos_jobs[job_id]["progress"] = 0.9

            if result.returncode == 0:
                _tfos_jobs[job_id]["status"] = JobStatus.COMPLETED.value
                _tfos_jobs[job_id]["progress"] = 1.0

                metrics_path = model_dir / "metadata.json"
                if metrics_path.exists():
                    try:
                        import json

                        meta = json.loads(metrics_path.read_text())
                        _tfos_jobs[job_id]["metrics"] = meta.get("final_metrics")
                    except Exception:
                        pass
            else:
                _tfos_jobs[job_id]["status"] = JobStatus.FAILED.value
                _tfos_jobs[job_id]["error"] = result.stderr[:1000] if result.stderr else "Unknown error"

            _tfos_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

        except subprocess.TimeoutExpired:
            _tfos_jobs[job_id]["status"] = JobStatus.FAILED.value
            _tfos_jobs[job_id]["error"] = "Job timed out after 1 hour"
            _tfos_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.exception(f"TFoS job {job_id} failed")
            _tfos_jobs[job_id]["status"] = JobStatus.FAILED.value
            _tfos_jobs[job_id]["error"] = str(e)
            _tfos_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    if req.async_mode:
        background_tasks.add_task(_run_tfos)
        return TFoSJobResponse(
            ok=True,
            job_id=job_id,
            status=JobStatus.PENDING.value,
            message="TFoS job submitted. Poll /tfos/status/{job_id} for updates.",
            model_dir=str(model_dir),
            log_dir=str(log_dir),
        )

    _run_tfos()
    job_status = _tfos_jobs[job_id]
    return TFoSJobResponse(
        ok=job_status["status"] == JobStatus.COMPLETED.value,
        job_id=job_id,
        status=job_status["status"],
        message=job_status.get("error"),
        model_dir=str(model_dir),
        log_dir=str(log_dir),
    )


@router.get("/tfos/status/{job_id}", response_model=TFoSJobStatus)
def tfos_status(job_id: str):
    if job_id not in _tfos_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _tfos_jobs[job_id]
    return TFoSJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0.0),
        model_dir=job.get("model_dir"),
        export_dir=job.get("export_dir"),
        error=job.get("error"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
        metrics=job.get("metrics"),
    )


@router.get("/tfos/jobs")
def tfos_list_jobs(status: str | None = Query(None), limit: int = Query(100, ge=1, le=1000)):
    jobs = []
    for job_id, job in _tfos_jobs.items():
        if status and job["status"] != status:
            continue
        jobs.append(
            {
                "job_id": job_id,
                "status": job["status"],
                "progress": job.get("progress", 0.0),
                "created_at": job.get("created_at"),
                "completed_at": job.get("completed_at"),
            }
        )
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"jobs": jobs[:limit], "total": len(jobs)}


@router.delete("/tfos/jobs/{job_id}")
def tfos_delete_job(job_id: str):
    import shutil

    if job_id not in _tfos_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _tfos_jobs[job_id]
    if job["status"] == JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")

    deleted = []
    for dir_key in ["model_dir", "export_dir", "log_dir"]:
        dir_path = job.get(dir_key)
        if dir_path and os.path.isdir(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
            deleted.append(dir_path)

    del _tfos_jobs[job_id]
    return {"deleted": True, "job_id": job_id, "directories": deleted}


@router.get("/tfos/health")
def tfos_health():
    import shutil

    spark_submit = shutil.which("spark-submit")
    spark_home = os.environ.get("SPARK_HOME", "")

    if not spark_submit and spark_home:
        spark_submit = os.path.join(spark_home, "bin", "spark-submit")
        if not os.path.isfile(spark_submit):
            spark_submit = None

    job_counts = {
        "pending": sum(1 for j in _tfos_jobs.values() if j["status"] == JobStatus.PENDING.value),
        "running": sum(1 for j in _tfos_jobs.values() if j["status"] == JobStatus.RUNNING.value),
        "completed": sum(1 for j in _tfos_jobs.values() if j["status"] == JobStatus.COMPLETED.value),
        "failed": sum(1 for j in _tfos_jobs.values() if j["status"] == JobStatus.FAILED.value),
    }

    return {
        "ok": spark_submit is not None,
        "spark_available": spark_submit is not None,
        "spark_submit_path": spark_submit,
        "spark_home": spark_home or None,
        "tfos_jobs": job_counts,
        "total_jobs": len(_tfos_jobs),
    }
