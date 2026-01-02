from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.core.state import MODELS_DIR, _stats, _training_jobs
from app.schemas.legacy import JobStatus

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics():
    """Prometheus-style metrics endpoint."""
    model_count = len(list(MODELS_DIR.glob("*.joblib")))
    jobs_pending = sum(1 for j in _training_jobs.values() if j["status"] == JobStatus.PENDING.value)
    jobs_running = sum(1 for j in _training_jobs.values() if j["status"] == JobStatus.RUNNING.value)
    jobs_completed = sum(1 for j in _training_jobs.values() if j["status"] == JobStatus.COMPLETED.value)
    jobs_failed = sum(1 for j in _training_jobs.values() if j["status"] == JobStatus.FAILED.value)

    lines = [
        "# HELP automl_models_total Total number of trained models",
        "# TYPE automl_models_total gauge",
        f"automl_models_total {model_count}",
        "# HELP automl_jobs_pending Pending training jobs",
        "# TYPE automl_jobs_pending gauge",
        f"automl_jobs_pending {jobs_pending}",
        "# HELP automl_jobs_running Running training jobs",
        "# TYPE automl_jobs_running gauge",
        f"automl_jobs_running {jobs_running}",
        "# HELP automl_jobs_completed Completed training jobs",
        "# TYPE automl_jobs_completed counter",
        f"automl_jobs_completed {jobs_completed}",
        "# HELP automl_jobs_failed Failed training jobs",
        "# TYPE automl_jobs_failed counter",
        f"automl_jobs_failed {jobs_failed}",
        "# HELP automl_requests_total Total HTTP requests",
        "# TYPE automl_requests_total counter",
        f"automl_requests_total {_stats['requests_total']}",
        "# HELP automl_requests_inflight Current in-flight HTTP requests",
        "# TYPE automl_requests_inflight gauge",
        f"automl_requests_inflight {_stats['requests_inflight']}",
        "# HELP automl_model_cache_hits Model cache hits",
        "# TYPE automl_model_cache_hits counter",
        f"automl_model_cache_hits {_stats['model_cache_hits']}",
        "# HELP automl_model_cache_misses Model cache misses",
        "# TYPE automl_model_cache_misses counter",
        f"automl_model_cache_misses {_stats['model_cache_misses']}",
        "# HELP automl_meta_cache_hits Meta cache hits",
        "# TYPE automl_meta_cache_hits counter",
        f"automl_meta_cache_hits {_stats['meta_cache_hits']}",
        "# HELP automl_meta_cache_misses Meta cache misses",
        "# TYPE automl_meta_cache_misses counter",
        f"automl_meta_cache_misses {_stats['meta_cache_misses']}",
    ]

    return StreamingResponse(iter(["\n".join(lines) + "\n"]), media_type="text/plain")
