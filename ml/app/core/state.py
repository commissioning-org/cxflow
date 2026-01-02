from __future__ import annotations

import logging
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format=settings.log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("automl")

# ---------------------------------------------------------------------------
# Directories / Paths
# ---------------------------------------------------------------------------

MODELS_DIR: Path = settings.models_dir
EXPERIMENTS_DIR: Path = settings.experiments_dir

REGISTRY_PATH: Path = MODELS_DIR / "_registry.json"
EXPERIMENTS_INDEX_PATH: Path = EXPERIMENTS_DIR / "experiments.json"

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

# Simple in-memory caches
_MODEL_CACHE: dict[str, dict[str, Any]] = {}
_META_CACHE: dict[str, dict[str, Any]] = {}

# Basic counters (in-memory)
_stats: dict[str, float] = {
    "requests_total": 0.0,
    "requests_inflight": 0.0,
    "model_cache_hits": 0.0,
    "model_cache_misses": 0.0,
    "meta_cache_hits": 0.0,
    "meta_cache_misses": 0.0,
}

# Rate limiting buckets (in-memory)
_rate_buckets: dict[str, deque[float]] = {}

# Thread pool for async training
_executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)

# In-memory job tracker (in production, use Redis/DB)
_training_jobs: dict[str, dict[str, Any]] = {}

# In-memory TFoS job tracker
_tfos_jobs: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("AutoML service starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Models directory: {MODELS_DIR}")
    logger.info(f"Experiments directory: {EXPERIMENTS_DIR}")
    logger.info(
        f"Max rows: {settings.max_rows}, CV folds: {settings.cv_folds}, SHAP: {settings.enable_shap}, cache: {settings.enable_cache}"
    )

    # Ensure dirs exist
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    model_count = len(list(MODELS_DIR.glob("*.joblib")))
    logger.info(f"Loaded {model_count} existing models")
    yield
    logger.info("AutoML service shutting down...")
    _executor.shutdown(wait=False)


def bump_request_stats(started: bool) -> None:
    if started:
        _stats["requests_total"] += 1.0
        _stats["requests_inflight"] += 1.0
    else:
        _stats["requests_inflight"] = max(0.0, _stats["requests_inflight"] - 1.0)


def touch_cache_hit(kind: str) -> None:
    if kind == "model_hit":
        _stats["model_cache_hits"] += 1.0
    elif kind == "model_miss":
        _stats["model_cache_misses"] += 1.0
    elif kind == "meta_hit":
        _stats["meta_cache_hits"] += 1.0
    elif kind == "meta_miss":
        _stats["meta_cache_misses"] += 1.0


def now_ts() -> float:
    return time.time()
