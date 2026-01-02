"""
AutoML Service - Enhanced ML Training & Inference API.

Provides automated machine learning capabilities:
- Auto problem detection (classification vs regression)
- Hyperparameter tuning with cross-validation
- Feature importance & SHAP explainability
- Model versioning, listing, and lifecycle management
- Batch prediction with streaming support
- Data profiling & validation
- Async training jobs with status polling

Environment Variables:
    ML_MODELS_DIR: Directory for model artifacts (default: /models)
    ML_LOG_LEVEL: Logging level (default: INFO)
    ML_MAX_ROWS: Max training rows (default: 100000)
    ML_CV_FOLDS: Cross-validation folds (default: 5)
    ML_ENABLE_SHAP: Enable SHAP explanations (default: true)
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api import (
    analysis_router,
    experiments_router,
    feature_engineering_router,
    health_router,
    metrics_router,
    models_router,
    powerbi_router,
    prediction_router,
    tfos_router,
    timeseries_router,
    training_router,
)
from app.core.middleware import request_middleware
from app.core.state import lifespan


def create_app() -> FastAPI:
    app = FastAPI(
        title="AutoML Service",
        version="2.0",
        description="Enhanced AutoML with tuning, explainability, registry, and experiment tracking",
        lifespan=lifespan,
    )

    app.middleware("http")(request_middleware)

    # Routers (backward-compatible routes preserved)
    app.include_router(health_router)
    app.include_router(training_router)
    app.include_router(prediction_router)
    app.include_router(models_router)
    app.include_router(analysis_router)
    app.include_router(experiments_router)
    app.include_router(timeseries_router)
    app.include_router(metrics_router)
    app.include_router(feature_engineering_router)
    app.include_router(tfos_router)
    app.include_router(powerbi_router)

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Legacy monolith (disabled)
#
# We keep the original implementation here for reference while the refactor
# settles, but it is not executed.
# ---------------------------------------------------------------------------

LEGACY_MONOLITH = r'''

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    ElasticNet,
    Lasso,
    LogisticRegression,
    Ridge,
    SGDClassifier,
)
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.config import settings
from app.api import feature_engineering_router

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format=settings.log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("automl")

MODELS_DIR = settings.models_dir
EXPERIMENTS_DIR = settings.experiments_dir

MAX_ROWS = settings.max_rows
CV_FOLDS = settings.cv_folds
ENABLE_SHAP = settings.enable_shap

REGISTRY_PATH = MODELS_DIR / "_registry.json"
EXPERIMENTS_INDEX_PATH = EXPERIMENTS_DIR / "experiments.json"

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

# Rate limiting (in-memory)
_rate_buckets: dict[str, deque[float]] = {}

# Thread pool for async training
_executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs)

# In-memory job tracker (in production, use Redis or DB)
_training_jobs: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Lifespan & App Setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown lifecycle."""
    logger.info("AutoML service starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Models directory: {MODELS_DIR}")
    logger.info(f"Experiments directory: {EXPERIMENTS_DIR}")
    logger.info(
        f"Max rows: {MAX_ROWS}, CV folds: {CV_FOLDS}, SHAP: {ENABLE_SHAP}, cache: {settings.enable_cache}"
    )
    # Load existing model count
    model_count = len(list(MODELS_DIR.glob("*.joblib")))
    logger.info(f"Loaded {model_count} existing models")
    yield
    logger.info("AutoML service shutting down...")
    _executor.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enhanced AutoML with tuning, explainability, registry, and experiment tracking",
    lifespan=lifespan,
)

# Extra routers (keep legacy endpoints below)
app.include_router(feature_engineering_router)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Request context + optional auth + basic rate limiting."""

    # API key auth (optional)
    if settings.api_key:
        provided = request.headers.get("x-api-key")
        if not provided or provided != settings.api_key:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    # Rate limiting (optional)
    if settings.enable_rate_limiting and request.url.path not in ("/health", "/readiness", "/metrics"):
        host = request.client.host if request.client else "unknown"
        key = f"{host}:{request.url.path.split('?')[0]}"
        now = time.time()
        bucket = _rate_buckets.setdefault(key, deque())
        # drop old
        window_start = now - settings.rate_limit_window_sec
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            return JSONResponse(
                {
                    "detail": "Rate limit exceeded",
                    "limit": settings.rate_limit_requests,
                    "window_sec": settings.rate_limit_window_sec,
                },
                status_code=429,
            )
        bucket.append(now)

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.time()
    _stats["requests_total"] += 1.0
    _stats["requests_inflight"] += 1.0
    try:
        response: Response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception", extra={"request_id": request_id})
        raise
    finally:
        _stats["requests_inflight"] = max(0.0, _stats["requests_inflight"] - 1.0)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{(time.time() - start) * 1000:.2f}"
    return response


# ---------------------------------------------------------------------------
# Enums & Models
# ---------------------------------------------------------------------------


class ProblemType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainRequest(BaseModel):
    """Training request with optional hyperparameter tuning."""

    rows: list[dict[str, Any]] = Field(..., min_length=5, description="Training data rows")
    target: str = Field(..., min_length=1, description="Target column name")
    problem: Literal["classification", "regression"] | None = Field(
        None, description="Problem type (auto-detected if not specified)"
    )
    metric: Literal["accuracy", "f1", "rmse", "mae", "r2", "roc_auc"] | None = Field(
        None, description="Evaluation metric"
    )
    test_size: float = Field(0.2, ge=0.05, le=0.5, description="Test split ratio")
    random_state: int = Field(42, description="Random seed for reproducibility")
    enable_cv: bool = Field(True, description="Enable cross-validation")
    enable_tuning: bool = Field(False, description="Enable hyperparameter tuning")
    model_name: str | None = Field(None, description="Optional human-readable model name")
    tags: list[str] = Field(default_factory=list, description="Tags for model organization")

    # Experiment tracking
    experiment_id: str | None = Field(None, description="Optional experiment ID")
    description: str | None = Field(None, description="Optional model description")

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(v) > MAX_ROWS:
            raise ValueError(f"rows exceeds maximum of {MAX_ROWS}")
        return v


class TrainResponse(BaseModel):
    """Training response with extended metrics."""

    model_id: str
    model_name: str | None
    problem: str
    metric: str
    score: float
    cv_score: float | None = None
    cv_std: float | None = None
    selected_model: str
    features: list[str]
    training_time_sec: float
    row_count: int
    created_at: str
    tags: list[str]


class AsyncTrainResponse(BaseModel):
    """Response for async training job."""

    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Status of an async training job."""

    job_id: str
    status: str
    model_id: str | None = None
    error: str | None = None
    progress: float = 0.0
    created_at: str | None = None
    completed_at: str | None = None


class PredictRequest(BaseModel):
    """Prediction request."""

    model_id: str = Field(..., description="Model ID to use for predictions")
    rows: list[dict[str, Any]] = Field(..., min_length=1, description="Rows to predict")
    return_probabilities: bool = Field(False, description="Return class probabilities")


class PredictResponse(BaseModel):
    """Prediction response."""

    model_id: str
    predictions: list[Any]
    probabilities: list[list[float]] | None = None
    inference_time_ms: float


class BatchPredictRequest(BaseModel):
    """Batch prediction with streaming response."""

    model_id: str
    rows: list[dict[str, Any]] = Field(..., min_length=1)
    batch_size: int = Field(1000, ge=100, le=10000)


class ModelInfo(BaseModel):
    """Model metadata info."""

    model_id: str
    model_name: str | None
    description: str | None = None
    version: int | None = None
    stage: str | None = None
    problem: str
    metric: str
    score: float
    cv_score: float | None
    selected_model: str
    features: list[str]
    row_count: int
    created_at: str
    file_size_bytes: int
    tags: list[str]


class ModelListResponse(BaseModel):
    """List of models."""

    models: list[ModelInfo]
    total: int


class FeatureImportanceResponse(BaseModel):
    """Feature importance scores."""

    model_id: str
    importances: dict[str, float]
    method: str


class ExplainRequest(BaseModel):
    """Request for model explanation (SHAP values)."""

    model_id: str
    rows: list[dict[str, Any]] = Field(..., min_length=1, max_length=100)


class ExplainResponse(BaseModel):
    """SHAP explanation response."""

    model_id: str
    shap_values: list[dict[str, float]]
    base_value: float
    method: str


class DataProfileRequest(BaseModel):
    """Request to profile data."""

    rows: list[dict[str, Any]] = Field(..., min_length=1)
    target: str | None = None


class ColumnProfile(BaseModel):
    """Profile of a single column."""

    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    unique_pct: float
    min: Any = None
    max: Any = None
    mean: float | None = None
    std: float | None = None
    median: float | None = None
    mode: Any = None
    sample_values: list[Any]


class DataProfileResponse(BaseModel):
    """Data profiling response."""

    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    target_distribution: dict[str, int] | None = None
    suggested_problem: str | None = None


# ---------------------------------------------------------------------------
# Artifacts & Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelArtifacts:
    """Paths to model artifacts."""

    model_path: Path
    meta_path: Path
    importance_path: Path
    shap_path: Path


def _artifacts(model_id: str) -> ModelArtifacts:
    """Get artifact paths for a model ID."""
    safe = "".join(c for c in model_id if c.isalnum() or c in ("-", "_"))
    return ModelArtifacts(
        model_path=MODELS_DIR / f"{safe}.joblib",
        meta_path=MODELS_DIR / f"{safe}.json",
        importance_path=MODELS_DIR / f"{safe}.importance.json",
        shap_path=MODELS_DIR / f"{safe}.shap.json",
    )


def _infer_problem(y: pd.Series) -> str:
    """Infer problem type from target column."""
    if pd.api.types.is_numeric_dtype(y):
        uniq = y.dropna().nunique()
        # If few unique values, treat as classification
        if uniq <= 20 or uniq < len(y) * 0.05:
            return ProblemType.CLASSIFICATION.value
        return ProblemType.REGRESSION.value
    return ProblemType.CLASSIFICATION.value


def _default_metric(problem: str) -> str:
    """Get default metric for problem type."""
    return "rmse" if problem == ProblemType.REGRESSION.value else "f1"


def _metric_direction(metric: str) -> Literal["maximize", "minimize"]:
    """Whether higher or lower is better for metric."""
    return "minimize" if metric in ("rmse", "mae") else "maximize"


def _build_preprocess(X: pd.DataFrame) -> ColumnTransformer:
    """Build preprocessing pipeline."""
    numeric_cols = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    categorical_cols = [c for c in X.columns if c not in numeric_cols]

    numeric_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler(with_mean=False)),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
            ("cat", categorical_pipeline, categorical_cols),
        ],
        remainder="drop",
    )


def _candidates(problem: str, enable_tuning: bool = False) -> list[tuple[str, Any, dict]]:
    """
    Get candidate models with optional hyperparameter grids.
    
    Returns list of (name, estimator, param_grid) tuples.
    """
    if problem == ProblemType.REGRESSION.value:
        candidates = [
            ("ridge", Ridge(random_state=42), {"alpha": [0.1, 1.0, 10.0]}),
            ("lasso", Lasso(random_state=42, max_iter=2000), {"alpha": [0.01, 0.1, 1.0]}),
            (
                "elasticnet",
                ElasticNet(random_state=42, max_iter=2000),
                {"alpha": [0.1, 1.0], "l1_ratio": [0.2, 0.5, 0.8]},
            ),
            ("dt", DecisionTreeRegressor(random_state=42), {"max_depth": [5, 10, 20, None]}),
            (
                "rf",
                RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
                {"n_estimators": [100, 200], "max_depth": [10, 20, None]},
            ),
            (
                "gbm",
                GradientBoostingRegressor(random_state=42),
                {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
            ),
            ("hgb", HistGradientBoostingRegressor(random_state=42), {"max_iter": [100, 200]}),
            ("svr", SVR(), {"C": [0.1, 1.0, 10.0], "kernel": ["rbf", "linear"]}),
            (
                "mlp",
                MLPRegressor(random_state=42, max_iter=2000),
                {
                    "hidden_layer_sizes": [(64,), (128,), (64, 32)],
                    "alpha": [0.0001, 0.001],
                    "learning_rate_init": [0.001, 0.01],
                },
            ),
        ]
    else:
        candidates = [
            (
                "logreg",
                LogisticRegression(max_iter=2000, random_state=42),
                {"C": [0.1, 1.0, 10.0]},
            ),
            (
                "sgd",
                SGDClassifier(random_state=42, max_iter=2000),
                {"alpha": [0.0001, 0.001, 0.01]},
            ),
            (
                "dt",
                DecisionTreeClassifier(random_state=42),
                {"max_depth": [5, 10, 20, None]},
            ),
            (
                "rf",
                RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
                {"n_estimators": [100, 200], "max_depth": [10, 20, None]},
            ),
            (
                "gbm",
                GradientBoostingClassifier(random_state=42),
                {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
            ),
            ("hgb", HistGradientBoostingClassifier(random_state=42), {"max_iter": [100, 200]}),
            ("svc", SVC(random_state=42, probability=True), {"C": [0.1, 1.0, 10.0]}),
            (
                "mlp",
                MLPClassifier(random_state=42, max_iter=2000),
                {
                    "hidden_layer_sizes": [(64,), (128,), (64, 32)],
                    "alpha": [0.0001, 0.001],
                    "learning_rate_init": [0.001, 0.01],
                },
            ),
        ]

    if not enable_tuning:
        # Return with empty param grids
        return [(name, est, {}) for name, est, _ in candidates]

    return candidates


def _compute_score(
    problem: str, metric: str, y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None = None
) -> float:
    """Compute evaluation metric score."""
    if problem == ProblemType.REGRESSION.value:
        if metric == "mae":
            return float(mean_absolute_error(y_true, y_pred))
        if metric == "r2":
            return float(r2_score(y_true, y_pred))
        # Default: rmse
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))

    # Classification
    if metric == "accuracy":
        return float(accuracy_score(y_true, y_pred))
    if metric == "roc_auc" and y_proba is not None:
        try:
            if y_proba.ndim == 2 and y_proba.shape[1] == 2:
                return float(roc_auc_score(y_true, y_proba[:, 1]))
            return float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
        except Exception:
            # Fall back to f1 if roc_auc fails
            pass
    # Default: f1
    return float(f1_score(y_true, y_pred, average="weighted"))


def _extract_feature_importance(
    pipeline: Pipeline, feature_names: list[str]
) -> dict[str, float]:
    """Extract feature importances from a fitted pipeline."""
    model = pipeline.named_steps.get("model")
    if model is None:
        return {}

    # Get transformed feature names from preprocessor
    try:
        preprocessor = pipeline.named_steps.get("preprocess")
        if hasattr(preprocessor, "get_feature_names_out"):
            transformed_names = list(preprocessor.get_feature_names_out())
        else:
            transformed_names = feature_names
    except Exception:
        transformed_names = feature_names

    importances: dict[str, float] = {}

    # Tree-based models
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        for i, name in enumerate(transformed_names[: len(imp)]):
            importances[str(name)] = float(imp[i])

    # Linear models
    elif hasattr(model, "coef_"):
        coef = np.abs(model.coef_)
        if coef.ndim > 1:
            coef = coef.mean(axis=0)
        for i, name in enumerate(transformed_names[: len(coef)]):
            importances[str(name)] = float(coef[i])

    # Sort by importance
    return dict(sorted(importances.items(), key=lambda x: abs(x[1]), reverse=True))


def _generate_data_hash(df: pd.DataFrame) -> str:
    """Generate a hash of the dataframe for caching/tracking."""
    content = df.to_json(orient="records")
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to read json {path}: {e}")
    return default


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def _load_registry() -> dict[str, Any]:
    return _read_json(
        REGISTRY_PATH,
        {
            "by_id": {},
            "by_stage": {},
            "versions": {},
            "updated_at": None,
        },
    )


def _save_registry(registry: dict[str, Any]) -> None:
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(REGISTRY_PATH, registry)


def _model_key(meta: dict[str, Any]) -> str:
    # Use model_name for versioning if present; otherwise fall back to model_id
    return (meta.get("model_name") or meta.get("model_id") or "unknown").strip()


def _register_model(meta: dict[str, Any]) -> dict[str, Any]:
    """Register model in registry and annotate meta with version/stage."""
    registry = _load_registry()
    key = _model_key(meta)
    versions: dict[str, int] = registry.get("versions", {})
    next_version = int(versions.get(key, 0)) + 1
    versions[key] = next_version
    registry["versions"] = versions

    model_id = meta["model_id"]
    stage = meta.get("stage") or "development"
    record = {
        "model_id": model_id,
        "model_name": meta.get("model_name"),
        "key": key,
        "version": next_version,
        "stage": stage,
        "created_at": meta.get("created_at"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    registry.setdefault("by_id", {})[model_id] = record
    # Default stage mapping only if not already set
    registry.setdefault("by_stage", {})
    if stage and stage not in registry["by_stage"]:
        registry["by_stage"][stage] = model_id

    _save_registry(registry)

    # Add back to meta
    meta["version"] = next_version
    meta["stage"] = stage
    return meta


def _promote_model(model_id: str, stage: str, archive_existing: bool = True) -> dict[str, Any]:
    registry = _load_registry()
    by_id: dict[str, Any] = registry.get("by_id", {})
    if model_id not in by_id:
        raise ValueError("Model not registered")

    by_stage: dict[str, str] = registry.get("by_stage", {})
    existing = by_stage.get(stage)
    if archive_existing and existing and existing != model_id and existing in by_id:
        by_id[existing]["stage"] = "archived"

    by_id[model_id]["stage"] = stage
    by_id[model_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    by_stage[stage] = model_id

    registry["by_id"] = by_id
    registry["by_stage"] = by_stage
    _save_registry(registry)
    return by_id[model_id]


def _get_model_from_cache(model_id: str) -> Any:
    art = _artifacts(model_id)
    if not art.model_path.exists():
        raise FileNotFoundError("Model not found")
    mtime = art.model_path.stat().st_mtime

    if settings.enable_cache:
        cached = _MODEL_CACHE.get(model_id)
        if cached and cached.get("mtime") == mtime:
            _stats["model_cache_hits"] += 1.0
            return cached["model"]
        _stats["model_cache_misses"] += 1.0

    model = joblib.load(art.model_path)
    if settings.enable_cache:
        _MODEL_CACHE[model_id] = {"mtime": mtime, "model": model, "loaded_at": time.time()}
    return model


def _get_meta_from_cache(model_id: str) -> dict[str, Any]:
    art = _artifacts(model_id)
    if not art.meta_path.exists():
        raise FileNotFoundError("Metadata not found")
    mtime = art.meta_path.stat().st_mtime

    if settings.enable_cache:
        cached = _META_CACHE.get(model_id)
        if cached and cached.get("mtime") == mtime:
            _stats["meta_cache_hits"] += 1.0
            return cached["meta"]
        _stats["meta_cache_misses"] += 1.0

    meta = json.loads(art.meta_path.read_text())
    if settings.enable_cache:
        _META_CACHE[model_id] = {"mtime": mtime, "meta": meta, "loaded_at": time.time()}
    return meta


def _load_experiments_index() -> dict[str, Any]:
    return _read_json(EXPERIMENTS_INDEX_PATH, {"experiments": [], "updated_at": None})


def _save_experiments_index(idx: dict[str, Any]) -> None:
    idx["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(EXPERIMENTS_INDEX_PATH, idx)


def _create_experiment(name: str, description: str | None = None, tags: dict[str, str] | None = None) -> dict[str, Any]:
    exp_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    exp = {
        "experiment_id": exp_id,
        "name": name,
        "description": description,
        "tags": tags or {},
        "created_at": created_at,
        "updated_at": created_at,
        "run_count": 0,
    }
    idx = _load_experiments_index()
    idx.setdefault("experiments", []).append(exp)
    _save_experiments_index(idx)
    (EXPERIMENTS_DIR / exp_id / "runs").mkdir(parents=True, exist_ok=True)
    return exp


def _get_experiment(exp_id: str) -> dict[str, Any] | None:
    idx = _load_experiments_index()
    for exp in idx.get("experiments", []):
        if exp.get("experiment_id") == exp_id:
            return exp
    return None


def _update_experiment(exp: dict[str, Any]) -> None:
    idx = _load_experiments_index()
    out = []
    for item in idx.get("experiments", []):
        if item.get("experiment_id") == exp.get("experiment_id"):
            out.append(exp)
        else:
            out.append(item)
    idx["experiments"] = out
    _save_experiments_index(idx)


def _log_run(
    experiment_id: str,
    run_id: str | None,
    metrics: dict[str, float] | None = None,
    params: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    exp = _get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    run_path = EXPERIMENTS_DIR / experiment_id / "runs" / f"{run_id}.json"

    existing = _read_json(run_path, None)
    if existing is None:
        run = {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "status": "running",
            "start_time": now,
            "end_time": None,
            "params": params or {},
            "metrics": metrics or {},
            "tags": tags or {},
            "model_id": model_id,
        }
        exp["run_count"] = int(exp.get("run_count", 0)) + 1
    else:
        run = existing
        run["params"].update(params or {})
        run["metrics"].update(metrics or {})
        run["tags"].update(tags or {})
        if model_id:
            run["model_id"] = model_id

    run["updated_at"] = now
    _write_json(run_path, run)
    exp["updated_at"] = now
    _update_experiment(exp)
    return run


# ---------------------------------------------------------------------------
# Core Training Logic
# ---------------------------------------------------------------------------


def _run_training(
    df: pd.DataFrame,
    target: str,
    problem: str | None,
    metric: str | None,
    test_size: float,
    random_state: int,
    enable_cv: bool,
    enable_tuning: bool,
    model_name: str | None,
    tags: list[str],
    description: str | None = None,
    experiment_id: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """
    Core training logic - can be run sync or async.
    
    Returns dict with training results.
    """
    start_time = time.time()
    logger.info(f"Starting training job: rows={len(df)}, target={target}")

    if target not in df.columns:
        raise ValueError(f"target '{target}' not found in input columns: {list(df.columns)}")

    y = df[target]
    X = df.drop(columns=[target])

    if X.empty or len(X.columns) == 0:
        raise ValueError("No features available after dropping target column")

    # Infer problem type
    actual_problem = problem or _infer_problem(y)
    actual_metric = metric or _default_metric(actual_problem)
    direction = _metric_direction(actual_metric)

    logger.info(f"Problem: {actual_problem}, Metric: {actual_metric}, Tuning: {enable_tuning}")

    # Encode labels if classification
    label_encoder = None
    if actual_problem == ProblemType.CLASSIFICATION.value:
        if not pd.api.types.is_numeric_dtype(y):
            label_encoder = LabelEncoder()
            y = pd.Series(label_encoder.fit_transform(y), index=y.index)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y if actual_problem == ProblemType.CLASSIFICATION.value else None
    )

    preprocess = _build_preprocess(X_train)

    best_name: str | None = None
    best_model: Pipeline | None = None
    best_score: float | None = None
    best_cv_score: float | None = None
    best_cv_std: float | None = None

    candidates = _candidates(actual_problem, enable_tuning)
    total_candidates = len(candidates)

    for idx, (name, est, param_grid) in enumerate(candidates):
        if job_id:
            if _training_jobs.get(job_id, {}).get("status") == JobStatus.CANCELLED.value:
                raise RuntimeError("Training cancelled")
            _training_jobs[job_id]["progress"] = (idx + 1) / total_candidates * 0.8

        try:
            pipe = Pipeline(steps=[("preprocess", preprocess), ("model", est)])

            if enable_tuning and param_grid:
                # Simple grid search with CV
                from sklearn.model_selection import GridSearchCV

                # Prefix params with 'model__'
                grid_params = {f"model__{k}": v for k, v in param_grid.items()}
                scoring = "neg_root_mean_squared_error" if actual_metric == "rmse" else actual_metric
                if actual_metric == "mae":
                    scoring = "neg_mean_absolute_error"

                grid = GridSearchCV(
                    pipe,
                    grid_params,
                    cv=min(CV_FOLDS, len(X_train) // 2),
                    scoring=scoring,
                    n_jobs=-1,
                    error_score="raise",
                )
                grid.fit(X_train, y_train)
                pipe = grid.best_estimator_
                cv_score = abs(grid.best_score_) if "neg" in str(scoring) else grid.best_score_
                cv_std = None
            else:
                pipe.fit(X_train, y_train)
                cv_score = None
                cv_std = None

                # Cross-validation if enabled
                if enable_cv and len(X_train) >= CV_FOLDS * 2:
                    try:
                        scoring = "neg_root_mean_squared_error" if actual_metric == "rmse" else actual_metric
                        if actual_metric == "mae":
                            scoring = "neg_mean_absolute_error"

                        cv_scores = cross_val_score(
                            pipe, X_train, y_train, cv=CV_FOLDS, scoring=scoring, n_jobs=-1
                        )
                        cv_score = float(np.mean(np.abs(cv_scores)))
                        cv_std = float(np.std(np.abs(cv_scores)))
                    except Exception as e:
                        logger.warning(f"CV failed for {name}: {e}")

            # Evaluate on test set
            preds = pipe.predict(X_test)
            proba = None
            if hasattr(pipe, "predict_proba"):
                try:
                    proba = pipe.predict_proba(X_test)
                except Exception:
                    pass

            score = _compute_score(actual_problem, actual_metric, np.asarray(y_test), preds, proba)

            logger.info(f"  {name}: test_score={score:.4f}, cv_score={cv_score}")

            # Determine if better
            is_better = False
            if best_score is None:
                is_better = True
            elif direction == "minimize":
                is_better = score < best_score
            else:
                is_better = score > best_score

            if is_better:
                best_name = name
                best_model = pipe
                best_score = score
                best_cv_score = cv_score
                best_cv_std = cv_std

        except Exception as e:
            logger.warning(f"Failed to train {name}: {e}")
            continue

    if best_model is None or best_score is None:
        raise RuntimeError("All candidate models failed to train")

    # Generate model ID
    model_id = str(uuid.uuid4())
    art = _artifacts(model_id)

    # Save model
    joblib.dump(best_model, art.model_path)

    # Extract feature importance
    importance = _extract_feature_importance(best_model, list(X.columns))
    if importance:
        art.importance_path.write_text(json.dumps(importance, indent=2))

    # Save label encoder if used
    encoder_info = None
    if label_encoder:
        encoder_info = list(label_encoder.classes_)

    training_time = time.time() - start_time
    created_at = datetime.now(timezone.utc).isoformat()

    meta = {
        "model_id": model_id,
        "model_name": model_name,
        "description": description,
        "problem": actual_problem,
        "metric": actual_metric,
        "score": best_score,
        "cv_score": best_cv_score,
        "cv_std": best_cv_std,
        "selected": best_name,
        "features": list(X.columns),
        "row_count": len(df),
        "training_time_sec": training_time,
        "created_at": created_at,
        "tags": tags,
        "label_encoder": encoder_info,
        "data_hash": _generate_data_hash(df),
    }

    # Register model (adds version/stage)
    try:
        meta = _register_model(meta)
    except Exception as e:
        logger.warning(f"Registry update failed: {e}")

    # Experiment tracking
    if experiment_id:
        try:
            run = _log_run(
                experiment_id=experiment_id,
                run_id=None,
                metrics={"score": float(best_score), "training_time_sec": float(training_time)},
                params={"problem": actual_problem, "metric": actual_metric, "selected_model": best_name},
                tags={"model_name": model_name or ""},
                model_id=model_id,
            )
            meta["experiment_id"] = experiment_id
            meta["run_id"] = run["run_id"]
        except Exception as e:
            logger.warning(f"Experiment logging failed: {e}")

    art.meta_path.write_text(json.dumps(meta, indent=2))

    logger.info(f"Training complete: model_id={model_id}, score={best_score:.4f}, time={training_time:.2f}s")

    if job_id:
        _training_jobs[job_id]["progress"] = 1.0

    return meta


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "ok": True,
        "version": "2.0",
        "models_dir": str(MODELS_DIR),
        "model_count": len(list(MODELS_DIR.glob("*.joblib"))),
    }


@app.get("/readiness")
def readiness():
    """Readiness probe for Kubernetes."""
    # Check models directory is accessible
    try:
        _ = list(MODELS_DIR.iterdir())
        return {"ready": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/train", response_model=TrainResponse)
def train(req: TrainRequest):
    """
    Train a model synchronously.
    
    For large datasets, consider using /train/async instead.
    """
    try:
        df = pd.DataFrame(req.rows)
        result = _run_training(
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


@app.post("/train/async", response_model=AsyncTrainResponse)
async def train_async(req: TrainRequest, background_tasks: BackgroundTasks):
    """
    Start an asynchronous training job.
    
    Returns immediately with a job_id. Use /train/status/{job_id} to poll.
    """
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
            result = _run_training(
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


@app.get("/train/status/{job_id}", response_model=JobStatusResponse)
def train_status(job_id: str):
    """Get the status of an async training job."""
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


@app.get("/train/jobs")
def list_training_jobs(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(200, ge=1, le=5000),
):
    """List training jobs currently known to this instance."""
    items = []
    for jid, job in _training_jobs.items():
        if status and job.get("status") != status:
            continue
        items.append({"job_id": jid, **job})
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"jobs": items[:limit], "total": len(items)}


@app.post("/train/cancel/{job_id}")
def cancel_training_job(job_id: str):
    """Best-effort cancellation for async training.

    Notes:
      - The current implementation checks cancellation between candidate models.
      - If a single candidate is currently fitting, cancellation takes effect after that fit completes.
    """
    if job_id not in _training_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _training_jobs[job_id]
    if job.get("status") in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        return {"ok": False, "job_id": job_id, "status": job.get("status"), "message": "Job already finished"}

    job["status"] = JobStatus.CANCELLED.value
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["error"] = "Cancelled by user"
    return {"ok": True, "job_id": job_id, "status": JobStatus.CANCELLED.value}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Make predictions using a trained model."""
    start_time = time.time()

    art = _artifacts(req.model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        model = _get_model_from_cache(req.model_id)
        meta = _get_meta_from_cache(req.model_id)
        df = pd.DataFrame(req.rows)

        # Ensure columns match
        missing = set(meta["features"]) - set(df.columns)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required features: {missing}",
            )

        # Reorder columns to match training
        df = df[meta["features"]]

        preds = model.predict(df)

        # Handle label encoding
        if meta.get("label_encoder"):
            label_classes = meta["label_encoder"]
            preds = [label_classes[int(p)] for p in preds]

        # Get probabilities if requested
        probabilities = None
        if req.return_probabilities and hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(df)
                probabilities = proba.tolist()
            except Exception:
                pass

        # Ensure JSON-serializable
        out: list[Any] = []
        for p in preds:
            if isinstance(p, (np.generic,)):
                out.append(p.item())
            else:
                out.append(p)

        inference_time = (time.time() - start_time) * 1000

        return PredictResponse(
            model_id=req.model_id,
            predictions=out,
            probabilities=probabilities,
            inference_time_ms=inference_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch")
async def predict_batch(req: BatchPredictRequest):
    """
    Batch prediction with streaming NDJSON response.
    
    Returns predictions in batches as newline-delimited JSON.
    """
    art = _artifacts(req.model_id)
    if not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    model = _get_model_from_cache(req.model_id)
    meta = _get_meta_from_cache(req.model_id)
    df = pd.DataFrame(req.rows)

    # Validate features
    df = df[meta["features"]]

    async def generate():
        for i in range(0, len(df), req.batch_size):
            batch = df.iloc[i : i + req.batch_size]
            preds = model.predict(batch)

            # Handle label encoding
            if meta.get("label_encoder"):
                label_classes = meta["label_encoder"]
                preds = [label_classes[int(p)] for p in preds]

            result = {
                "batch_start": i,
                "batch_size": len(batch),
                "predictions": [p.item() if isinstance(p, np.generic) else p for p in preds],
            }
            yield json.dumps(result) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/models", response_model=ModelListResponse)
def list_models(
    tag: str | None = Query(None, description="Filter by tag"),
    problem: str | None = Query(None, description="Filter by problem type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all trained models with optional filtering."""
    models: list[ModelInfo] = []

    registry = _load_registry()
    by_id = registry.get("by_id", {})

    for meta_path in MODELS_DIR.glob("*.json"):
        if meta_path.name.startswith("_"):
            continue
        if meta_path.name.endswith(".importance.json") or meta_path.name.endswith(".shap.json"):
            continue

        try:
            meta = json.loads(meta_path.read_text())
            model_path = MODELS_DIR / f"{meta_path.stem}.joblib"

            reg = by_id.get(meta.get("model_id")) if isinstance(meta, dict) else None

            # Apply filters
            if tag and tag not in meta.get("tags", []):
                continue
            if problem and meta.get("problem") != problem:
                continue

            models.append(
                ModelInfo(
                    model_id=meta["model_id"],
                    model_name=meta.get("model_name"),
                    description=meta.get("description"),
                    version=meta.get("version") or (reg.get("version") if reg else None),
                    stage=meta.get("stage") or (reg.get("stage") if reg else None),
                    problem=meta["problem"],
                    metric=meta["metric"],
                    score=meta["score"],
                    cv_score=meta.get("cv_score"),
                    selected_model=meta["selected"],
                    features=meta["features"],
                    row_count=meta.get("row_count", 0),
                    created_at=meta.get("created_at", ""),
                    file_size_bytes=model_path.stat().st_size if model_path.exists() else 0,
                    tags=meta.get("tags", []),
                )
            )
        except Exception as e:
            logger.warning(f"Failed to load model metadata: {meta_path}: {e}")

    # Sort by creation date (newest first)
    models.sort(key=lambda m: m.created_at, reverse=True)

    total = len(models)
    models = models[offset : offset + limit]

    return ModelListResponse(models=models, total=total)


@app.get("/models/{model_id}", response_model=ModelInfo)
def get_model(model_id: str):
    """Get details of a specific model."""
    art = _artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    meta = _get_meta_from_cache(model_id)
    registry = _load_registry()
    reg = registry.get("by_id", {}).get(model_id)

    return ModelInfo(
        model_id=meta["model_id"],
        model_name=meta.get("model_name"),
        description=meta.get("description"),
        version=meta.get("version") or (reg.get("version") if reg else None),
        stage=meta.get("stage") or (reg.get("stage") if reg else None),
        problem=meta["problem"],
        metric=meta["metric"],
        score=meta["score"],
        cv_score=meta.get("cv_score"),
        selected_model=meta["selected"],
        features=meta["features"],
        row_count=meta.get("row_count", 0),
        created_at=meta.get("created_at", ""),
        file_size_bytes=art.model_path.stat().st_size if art.model_path.exists() else 0,
        tags=meta.get("tags", []),
    )


@app.delete("/models/{model_id}")
def delete_model(model_id: str):
    """Delete a trained model."""
    art = _artifacts(model_id)

    if not art.meta_path.exists() and not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    deleted = []
    for path in [art.model_path, art.meta_path, art.importance_path, art.shap_path]:
        if path.exists():
            path.unlink()
            deleted.append(path.name)

    # Remove from caches
    _MODEL_CACHE.pop(model_id, None)
    _META_CACHE.pop(model_id, None)

    # Remove from registry
    try:
        registry = _load_registry()
        registry.get("by_id", {}).pop(model_id, None)
        by_stage = registry.get("by_stage", {})
        for stg, mid in list(by_stage.items()):
            if mid == model_id:
                by_stage.pop(stg, None)
        registry["by_stage"] = by_stage
        _save_registry(registry)
    except Exception:
        pass

    logger.info(f"Deleted model {model_id}: {deleted}")

    return {"deleted": True, "model_id": model_id, "files": deleted}


@app.get("/models/{model_id}/importance", response_model=FeatureImportanceResponse)
def get_feature_importance(model_id: str):
    """Get feature importance scores for a model."""
    art = _artifacts(model_id)

    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    # Try cached importance first
    if art.importance_path.exists():
        importances = json.loads(art.importance_path.read_text())
        return FeatureImportanceResponse(
            model_id=model_id,
            importances=importances,
            method="cached",
        )

    # Compute from model
    try:
        model = joblib.load(art.model_path)
        meta = _get_meta_from_cache(model_id)
        importances = _extract_feature_importance(model, meta["features"])

        if importances:
            art.importance_path.write_text(json.dumps(importances, indent=2))

        return FeatureImportanceResponse(
            model_id=model_id,
            importances=importances,
            method="computed",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute importance: {e}")


@app.post("/models/{model_id}/explain", response_model=ExplainResponse)
def explain_predictions(model_id: str, req: ExplainRequest):
    """
    Get SHAP explanations for predictions.
    
    Requires SHAP library and ML_ENABLE_SHAP=true.
    """
    if not ENABLE_SHAP:
        raise HTTPException(status_code=400, detail="SHAP explanations disabled")

    art = _artifacts(model_id)
    if not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        import shap
    except ImportError:
        raise HTTPException(status_code=501, detail="SHAP not installed")

    try:
        model = joblib.load(art.model_path)
        meta = _get_meta_from_cache(model_id)
        df = pd.DataFrame(req.rows)[meta["features"]]

        # Get the underlying model
        estimator = model.named_steps.get("model")
        preprocessor = model.named_steps.get("preprocess")

        X_transformed = preprocessor.transform(df)

        # Choose appropriate explainer
        if hasattr(estimator, "predict_proba"):
            explainer = shap.TreeExplainer(estimator, feature_perturbation="interventional")
        else:
            explainer = shap.Explainer(estimator)

        shap_values = explainer.shap_values(X_transformed)

        # Handle multi-class
        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) == 2 else np.mean(shap_values, axis=0)

        # Map back to feature names
        try:
            feature_names = list(preprocessor.get_feature_names_out())
        except Exception:
            feature_names = meta["features"]

        result_shap: list[dict[str, float]] = []
        for row_idx in range(len(df)):
            row_shap = {}
            for feat_idx, feat_name in enumerate(feature_names[: shap_values.shape[1]]):
                row_shap[feat_name] = float(shap_values[row_idx, feat_idx])
            result_shap.append(row_shap)

        return ExplainResponse(
            model_id=model_id,
            shap_values=result_shap,
            base_value=float(explainer.expected_value) if np.isscalar(explainer.expected_value) else float(explainer.expected_value[0]),
            method="TreeExplainer" if hasattr(estimator, "predict_proba") else "Explainer",
        )

    except Exception as e:
        logger.exception("SHAP explanation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profile", response_model=DataProfileResponse)
def profile_data(req: DataProfileRequest):
    """
    Profile a dataset to understand its structure and statistics.
    
    Useful before training to validate data quality.
    """
    df = pd.DataFrame(req.rows)
    columns: list[ColumnProfile] = []

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = int(series.isnull().sum())
        unique_count = int(series.nunique())

        profile = ColumnProfile(
            name=col,
            dtype=dtype,
            null_count=null_count,
            null_pct=round(null_count / len(df) * 100, 2),
            unique_count=unique_count,
            unique_pct=round(unique_count / len(df) * 100, 2),
            sample_values=series.dropna().head(5).tolist(),
        )

        if pd.api.types.is_numeric_dtype(series):
            profile.min = float(series.min()) if not series.isnull().all() else None
            profile.max = float(series.max()) if not series.isnull().all() else None
            profile.mean = float(series.mean()) if not series.isnull().all() else None
            profile.std = float(series.std()) if not series.isnull().all() else None
            profile.median = float(series.median()) if not series.isnull().all() else None
        else:
            mode_val = series.mode()
            profile.mode = mode_val.iloc[0] if len(mode_val) > 0 else None

        columns.append(profile)

    # Target distribution if specified
    target_dist = None
    suggested = None
    if req.target and req.target in df.columns:
        target_series = df[req.target]
        target_dist = target_series.value_counts().head(20).to_dict()
        target_dist = {str(k): int(v) for k, v in target_dist.items()}
        suggested = _infer_problem(target_series)

    return DataProfileResponse(
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        target_distribution=target_dist,
        suggested_problem=suggested,
    )


@app.get("/metrics")
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


@app.get("/models/{model_id}/card")
def model_card(model_id: str):
    """Return a lightweight model card summary (JSON) for observability/governance."""
    art = _artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    meta = _get_meta_from_cache(model_id)
    importance = None
    if art.importance_path.exists():
        try:
            importance = json.loads(art.importance_path.read_text())
        except Exception:
            importance = None

    top_features = None
    if isinstance(importance, dict) and importance:
        top_features = list(importance.items())[:20]

    registry = _load_registry()
    reg = registry.get("by_id", {}).get(model_id)

    return {
        "model_id": meta.get("model_id"),
        "model_name": meta.get("model_name"),
        "description": meta.get("description"),
        "problem": meta.get("problem"),
        "metric": meta.get("metric"),
        "score": meta.get("score"),
        "cv_score": meta.get("cv_score"),
        "cv_std": meta.get("cv_std"),
        "selected_model": meta.get("selected"),
        "created_at": meta.get("created_at"),
        "tags": meta.get("tags", []),
        "data_hash": meta.get("data_hash"),
        "feature_count": len(meta.get("features", []) or []),
        "features": meta.get("features", []),
        "top_importance": top_features,
        "registry": reg,
        "artifacts": {
            "model_path": str(art.model_path),
            "meta_path": str(art.meta_path),
            "importance_path": str(art.importance_path) if art.importance_path.exists() else None,
            "shap_path": str(art.shap_path) if art.shap_path.exists() else None,
        },
    }


# ---------------------------------------------------------------------------
# Time Series (lightweight: naive / seasonal naive)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeSeriesArtifacts:
    model_path: Path
    meta_path: Path


def _ts_artifacts(model_id: str) -> TimeSeriesArtifacts:
    safe = "".join(c for c in model_id if c.isalnum() or c in ("-", "_"))
    return TimeSeriesArtifacts(
        model_path=MODELS_DIR / f"{safe}.ts.joblib",
        meta_path=MODELS_DIR / f"{safe}.ts.json",
    )


class TimeSeriesTrainRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=10)
    target: str = Field(..., min_length=1)
    datetime_col: str = Field(..., min_length=1)
    frequency: str = Field("D", description="Pandas offset alias (D, H, T, W, M, etc.)")
    seasonality_period: int | None = Field(None, ge=2, le=366, description="Season length (optional)")
    model_name: str | None = None
    tags: list[str] = Field(default_factory=list)


class TimeSeriesTrainResponse(BaseModel):
    model_id: str
    model_name: str | None
    target: str
    datetime_col: str
    frequency: str
    seasonality_period: int | None
    row_count: int
    created_at: str


class TimeSeriesForecastRequest(BaseModel):
    model_id: str
    horizon: int = Field(..., ge=1, le=3650)


@app.post("/timeseries/train", response_model=TimeSeriesTrainResponse)
def train_timeseries(req: TimeSeriesTrainRequest):
    """Train a lightweight time-series forecaster (no external TS libs required)."""
    df = pd.DataFrame(req.rows)
    if req.datetime_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"datetime_col '{req.datetime_col}' not found")
    if req.target not in df.columns:
        raise HTTPException(status_code=400, detail=f"target '{req.target}' not found")

    df[req.datetime_col] = pd.to_datetime(df[req.datetime_col], utc=True, errors="coerce")
    df = df.dropna(subset=[req.datetime_col, req.target]).sort_values(req.datetime_col)
    if df.empty:
        raise HTTPException(status_code=400, detail="No valid rows after parsing/cleaning")

    y = pd.to_numeric(df[req.target], errors="coerce")
    df = df.assign(_y=y).dropna(subset=["_y"])
    if df.empty:
        raise HTTPException(status_code=400, detail="Target column must be numeric for forecasting")

    values = df["_y"].astype(float).tolist()
    timestamps = df[req.datetime_col].tolist()
    if len(values) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 numeric observations")

    model_obj = {
        "kind": "seasonal_naive" if req.seasonality_period else "naive",
        "datetime_col": req.datetime_col,
        "target": req.target,
        "frequency": req.frequency,
        "seasonality_period": req.seasonality_period,
        "values": values[-5000:],
        "last_timestamp": pd.to_datetime(timestamps[-1], utc=True).isoformat(),
    }

    model_id = str(uuid.uuid4())
    art = _ts_artifacts(model_id)
    joblib.dump(model_obj, art.model_path)

    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "model_id": model_id,
        "model_name": req.model_name,
        "datetime_col": req.datetime_col,
        "target": req.target,
        "frequency": req.frequency,
        "seasonality_period": req.seasonality_period,
        "row_count": int(len(df)),
        "created_at": created_at,
        "tags": req.tags,
    }
    art.meta_path.write_text(json.dumps(meta, indent=2))

    return TimeSeriesTrainResponse(
        model_id=model_id,
        model_name=req.model_name,
        target=req.target,
        datetime_col=req.datetime_col,
        frequency=req.frequency,
        seasonality_period=req.seasonality_period,
        row_count=int(len(df)),
        created_at=created_at,
    )


@app.post("/timeseries/forecast")
def forecast_timeseries(req: TimeSeriesForecastRequest):
    """Forecast using a trained time-series model."""
    art = _ts_artifacts(req.model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Time series model not found")

    model_obj = joblib.load(art.model_path)
    meta = json.loads(art.meta_path.read_text())

    freq = model_obj.get("frequency") or "D"
    season = model_obj.get("seasonality_period")
    values: list[float] = list(model_obj.get("values") or [])
    if not values:
        raise HTTPException(status_code=500, detail="Corrupt time series artifact (missing values)")

    last_ts = pd.to_datetime(model_obj.get("last_timestamp"), utc=True)
    future_index = pd.date_range(start=last_ts, periods=req.horizon + 1, freq=freq, tz="UTC")[1:]

    preds: list[float] = []
    if season and int(season) > 1 and len(values) >= int(season):
        base = values[-int(season) :]
        for i in range(req.horizon):
            preds.append(float(base[i % int(season)]))
    else:
        last_val = float(values[-1])
        preds = [last_val for _ in range(req.horizon)]

    out = []
    for ts, yhat in zip(future_index, preds, strict=False):
        out.append({"timestamp": ts.isoformat(), "forecast": yhat})

    return {
        "model_id": req.model_id,
        "target": meta.get("target"),
        "datetime_col": meta.get("datetime_col"),
        "frequency": meta.get("frequency"),
        "horizon": req.horizon,
        "forecasts": out,
    }


# ---------------------------------------------------------------------------
# Model Registry & Experiment Tracking Endpoints
# ---------------------------------------------------------------------------


class PromoteModelRequest(BaseModel):
    stage: Literal["development", "staging", "production", "archived"] = Field(
        ..., description="Target stage"
    )
    archive_existing: bool = Field(True, description="Archive existing model in stage")


@app.post("/models/{model_id}/promote")
def promote_model(model_id: str, req: PromoteModelRequest):
    """Promote a model into a lifecycle stage (development/staging/production)."""
    art = _artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        record = _promote_model(model_id=model_id, stage=req.stage, archive_existing=req.archive_existing)
        # Reflect into model meta for easier reads
        meta = _get_meta_from_cache(model_id)
        meta["stage"] = record.get("stage")
        meta["version"] = record.get("version")
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        art.meta_path.write_text(json.dumps(meta, indent=2))
        _META_CACHE.pop(model_id, None)
        return {"ok": True, "model_id": model_id, "stage": record.get("stage"), "version": record.get("version")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models/resolve")
def resolve_model(stage: Literal["development", "staging", "production"] = Query("production")):
    """Resolve the current model_id for a stage."""
    registry = _load_registry()
    mid = registry.get("by_stage", {}).get(stage)
    if not mid:
        raise HTTPException(status_code=404, detail=f"No model in stage '{stage}'")
    return {"stage": stage, "model_id": mid}


class ExperimentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


@app.get("/experiments")
def list_experiments(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    idx = _load_experiments_index()
    exps = idx.get("experiments", [])
    total = len(exps)
    return {"experiments": exps[offset : offset + limit], "total": total}


@app.post("/experiments")
def create_experiment(req: ExperimentCreateRequest):
    exp = _create_experiment(req.name, req.description, req.tags)
    return exp


class RunLogRequest(BaseModel):
    run_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)
    model_id: str | None = None


@app.post("/experiments/{experiment_id}/runs")
def log_run(experiment_id: str, req: RunLogRequest):
    try:
        run = _log_run(
            experiment_id=experiment_id,
            run_id=req.run_id,
            metrics=req.metrics,
            params=req.params,
            tags=req.tags,
            model_id=req.model_id,
        )
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/experiments/{experiment_id}/runs")
def list_runs(experiment_id: str, limit: int = Query(100, ge=1, le=1000)):
    exp = _get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    runs_dir = EXPERIMENTS_DIR / experiment_id / "runs"
    runs = []
    if runs_dir.exists():
        for p in runs_dir.glob("*.json"):
            try:
                runs.append(json.loads(p.read_text()))
            except Exception:
                continue
    runs.sort(key=lambda r: r.get("start_time", ""), reverse=True)
    return {"experiment_id": experiment_id, "runs": runs[:limit], "total": len(runs)}


# ---------------------------------------------------------------------------
# TensorFlowOnSpark Integration Endpoints
# ---------------------------------------------------------------------------

# In-memory TFoS job tracker
_tfos_jobs: dict[str, dict[str, Any]] = {}


class TFoSJobRequest(BaseModel):
    """TensorFlowOnSpark job submission request."""

    job_id: str | None = None
    data_path: str = Field(..., description="Path to training data (NDJSON/CSV)")
    target_column: str = Field("label", description="Target column name")
    format: Literal["ndjson", "csv", "tfr"] = Field("ndjson", description="Data format")

    # Spark configuration
    spark_master: str = Field("local[*]", description="Spark master URL")
    cluster_size: int = Field(2, ge=1, le=100, description="Number of TF workers")
    num_ps: int = Field(0, ge=0, le=10, description="Number of parameter servers")
    executor_memory: str = Field("2g", description="Memory per executor")

    # Training configuration
    epochs: int = Field(5, ge=1, le=1000)
    batch_size: int = Field(64, ge=1, le=10000)
    learning_rate: float = Field(0.001, ge=1e-6, le=1.0)

    # TFoS options
    input_mode: Literal["SPARK", "TENSORFLOW"] = Field("SPARK")
    tensorboard: bool = Field(True)
    master_node: str = Field("chief")
    async_mode: bool = Field(True, description="Run asynchronously")


class TFoSJobResponse(BaseModel):
    """TFoS job submission response."""

    ok: bool
    job_id: str
    status: str
    message: str | None = None
    model_dir: str | None = None
    log_dir: str | None = None


class TFoSJobStatus(BaseModel):
    """TFoS job status."""

    job_id: str
    status: str
    progress: float = 0.0
    model_dir: str | None = None
    export_dir: str | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    metrics: dict[str, float] | None = None


@app.post("/tfos/submit", response_model=TFoSJobResponse)
async def tfos_submit(req: TFoSJobRequest, background_tasks: BackgroundTasks):
    """
    Submit a TensorFlowOnSpark distributed training job.

    This endpoint creates a job specification and submits it for execution
    on the Spark cluster. Use /tfos/status/{job_id} to poll for completion.
    """
    import subprocess
    import shutil

    job_id = req.job_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Create directories
    model_dir = MODELS_DIR / "tfos" / job_id
    log_dir = Path("/tmp/tfos_logs") / job_id
    export_dir = MODELS_DIR / "tfos_export" / job_id

    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize job status
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
        """Background task to run TFoS job."""
        try:
            _tfos_jobs[job_id]["status"] = JobStatus.RUNNING.value
            _tfos_jobs[job_id]["progress"] = 0.1

            # Build spark-submit command
            spark_submit = shutil.which("spark-submit") or os.environ.get("SPARK_HOME", "/opt/spark") + "/bin/spark-submit"
            training_script = os.environ.get("TFOS_TRAINING_SCRIPT", "/app/tfos_training_script.py")

            # Check if script exists
            if not os.path.isfile(training_script):
                # Use inline training
                training_script = str(Path(__file__).parent.parent.parent / "ingestion" / "tfos_training_script.py")

            cmd = [
                spark_submit,
                "--master", req.spark_master,
                "--conf", f"spark.executor.instances={req.cluster_size}",
                "--conf", f"spark.executor.memory={req.executor_memory}",
                training_script,
                "--cluster_size", str(req.cluster_size),
                "--num_ps", str(req.num_ps),
                "--epochs", str(req.epochs),
                "--batch_size", str(req.batch_size),
                "--learning_rate", str(req.learning_rate),
                "--data_path", req.data_path,
                "--target_column", req.target_column,
                "--format", req.format,
                "--model_dir", str(model_dir),
                "--export_dir", str(export_dir),
                "--input_mode", req.input_mode,
            ]

            if req.tensorboard:
                cmd.append("--tensorboard")

            if req.master_node:
                cmd.extend(["--master_node", req.master_node])

            logger.info(f"Starting TFoS job {job_id}: {' '.join(cmd[:5])}...")

            # Run subprocess
            _tfos_jobs[job_id]["progress"] = 0.2
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
            )

            # Save output
            (log_dir / "stdout.log").write_text(result.stdout)
            (log_dir / "stderr.log").write_text(result.stderr)

            _tfos_jobs[job_id]["progress"] = 0.9

            if result.returncode == 0:
                _tfos_jobs[job_id]["status"] = JobStatus.COMPLETED.value
                _tfos_jobs[job_id]["progress"] = 1.0

                # Try to load metrics
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
    else:
        # Synchronous execution
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


@app.get("/tfos/status/{job_id}", response_model=TFoSJobStatus)
def tfos_status(job_id: str):
    """Get the status of a TFoS training job."""
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


@app.get("/tfos/jobs")
def tfos_list_jobs(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all TFoS training jobs."""
    jobs = []

    for job_id, job in _tfos_jobs.items():
        if status and job["status"] != status:
            continue

        jobs.append({
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", 0.0),
            "created_at": job.get("created_at"),
            "completed_at": job.get("completed_at"),
        })

    # Sort by creation date (newest first)
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {
        "jobs": jobs[:limit],
        "total": len(jobs),
    }


@app.delete("/tfos/jobs/{job_id}")
def tfos_delete_job(job_id: str):
    """Delete a TFoS job and its artifacts."""
    if job_id not in _tfos_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _tfos_jobs[job_id]

    # Don't delete running jobs
    if job["status"] == JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")

    # Delete directories
    deleted = []
    for dir_key in ["model_dir", "export_dir", "log_dir"]:
        dir_path = job.get(dir_key)
        if dir_path and os.path.isdir(dir_path):
            import shutil
            shutil.rmtree(dir_path, ignore_errors=True)
            deleted.append(dir_path)

    # Remove from tracker
    del _tfos_jobs[job_id]

    return {
        "deleted": True,
        "job_id": job_id,
        "directories": deleted,
    }


@app.get("/tfos/health")
def tfos_health():
    """Check TFoS/Spark availability."""
    import shutil

    spark_submit = shutil.which("spark-submit")
    spark_home = os.environ.get("SPARK_HOME", "")

    if not spark_submit and spark_home:
        spark_submit = os.path.join(spark_home, "bin", "spark-submit")
        if not os.path.isfile(spark_submit):
            spark_submit = None

    # Count jobs by status
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


# ---------------------------------------------------------------------------
# Power BI Automation Endpoints
# ---------------------------------------------------------------------------

# Import Power BI client
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "powerbi"))
    from powerbi_client import PowerBIClient, PowerBIConfig, TokenCache
    PBI_AVAILABLE = True
except ImportError:
    PBI_AVAILABLE = False
    logger.warning("Power BI client not available")


class PBIWorkspaceRequest(BaseModel):
    """Power BI workspace creation request."""
    name: str = Field(..., description="Workspace name")
    capacity_id: str | None = Field(None, description="Premium capacity GUID")


class PBIRefreshRequest(BaseModel):
    """Dataset refresh request."""
    workspace_id: str = Field(..., description="Workspace GUID")
    dataset_id: str = Field(..., description="Dataset GUID")
    notify_option: str = Field("NoNotification", description="Notification option")


class PBIDeployRequest(BaseModel):
    """Pipeline deployment request."""
    pipeline_id: str = Field(..., description="Pipeline GUID")
    source_stage: int = Field(0, ge=0, le=2, description="Source stage (0=Dev, 1=Test)")
    note: str = Field("", description="Deployment note")


class PBIDtapRequest(BaseModel):
    """DTAP workspace generation request."""
    base_name: str = Field(..., description="Base workspace name")
    capacity_id: str = Field(..., description="Premium capacity GUID")
    stages: list[str] = Field(["dev", "tst", ""], description="Stage suffixes")


class PBITrainingWorkspacesRequest(BaseModel):
    """Training workspace generation request."""
    base_name: str = Field(..., description="Base workspace name")
    count: int = Field(10, ge=1, le=100, description="Number of workspaces")
    capacity_id: str | None = Field(None, description="Capacity GUID")


@app.get("/powerbi/health")
async def powerbi_health():
    """Check Power BI configuration and connectivity."""
    if not PBI_AVAILABLE:
        return {
            "ok": False,
            "error": "Power BI client not installed",
            "configured": False,
        }
    
    config = PowerBIConfig()
    configured = bool(config.tenant_id and config.client_id)
    
    if not configured:
        return {
            "ok": False,
            "configured": False,
            "error": "Missing PBI_TENANT_ID or PBI_CLIENT_ID",
        }
    
    # Test authentication
    try:
        async with PowerBIClient(config) as client:
            await client.authenticate()
            return {
                "ok": True,
                "configured": True,
                "auth_mode": config.auth_mode,
                "tenant_id": config.tenant_id[:8] + "...",
            }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
        }


@app.get("/powerbi/workspaces")
async def powerbi_list_workspaces(
    top: int = Query(100, ge=1, le=5000),
    filter_: str | None = Query(None, alias="filter", description="OData filter"),
):
    """List Power BI workspaces."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            workspaces = await client.list_workspaces(top=top, filter_=filter_)
            return {
                "workspaces": [ws.model_dump() for ws in workspaces],
                "count": len(workspaces),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/powerbi/workspaces")
async def powerbi_create_workspace(req: PBIWorkspaceRequest):
    """Create a new Power BI workspace."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            workspace = await client.create_workspace(req.name)
            
            # Assign to capacity if provided
            if req.capacity_id:
                await client.assign_to_capacity(workspace.id, req.capacity_id)
                await client.set_large_dataset_format(workspace.id)
            
            return {
                "ok": True,
                "workspace": workspace.model_dump(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/powerbi/workspaces/{workspace_id}")
async def powerbi_delete_workspace(workspace_id: str):
    """Delete a Power BI workspace."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            await client.delete_workspace(workspace_id)
            return {"ok": True, "deleted": workspace_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/powerbi/workspaces/dtap")
async def powerbi_generate_dtap(req: PBIDtapRequest):
    """Generate DTAP workspaces (Dev/Test/Prod)."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            result = await client.generate_dtap_workspaces(
                req.base_name,
                req.capacity_id,
                req.stages,
            )
            return {
                "ok": len(result["errors"]) == 0,
                "workspaces": result["workspaces"],
                "errors": result["errors"],
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/workspaces/{workspace_id}/datasets")
async def powerbi_list_datasets(workspace_id: str):
    """List datasets in a workspace."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            datasets = await client.list_datasets(workspace_id)
            return {
                "datasets": [ds.model_dump() for ds in datasets],
                "count": len(datasets),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/powerbi/datasets/refresh")
async def powerbi_trigger_refresh(req: PBIRefreshRequest):
    """Trigger a dataset refresh."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            await client.trigger_refresh(
                req.workspace_id,
                req.dataset_id,
                req.notify_option,
            )
            return {
                "ok": True,
                "message": "Refresh triggered successfully",
                "workspace_id": req.workspace_id,
                "dataset_id": req.dataset_id,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/workspaces/{workspace_id}/datasets/{dataset_id}/refresh-history")
async def powerbi_get_refresh_history(
    workspace_id: str,
    dataset_id: str,
    top: int = Query(100, ge=1, le=1000),
):
    """Get dataset refresh history."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            history = await client.get_refresh_history(workspace_id, dataset_id, top)
            return {
                "refreshes": history,
                "count": len(history),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/pipelines")
async def powerbi_list_pipelines():
    """List deployment pipelines."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            pipelines = await client.list_pipelines()
            return {
                "pipelines": [p.model_dump() for p in pipelines],
                "count": len(pipelines),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/powerbi/pipelines/deploy")
async def powerbi_deploy_pipeline(req: PBIDeployRequest):
    """Trigger a pipeline deployment."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            result = await client.deploy_pipeline(
                req.pipeline_id,
                req.source_stage,
                req.note or f"Deployed via API at {datetime.now().isoformat()}",
            )
            return {
                "ok": True,
                "result": result,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/workspaces/{workspace_id}/dataflows")
async def powerbi_list_dataflows(workspace_id: str):
    """List dataflows in a workspace."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            dataflows = await client.list_dataflows(workspace_id)
            return {
                "dataflows": [df.model_dump() for df in dataflows],
                "count": len(dataflows),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/workspaces/{workspace_id}/reports")
async def powerbi_list_reports(workspace_id: str):
    """List reports in a workspace."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            reports = await client.list_reports(workspace_id)
            return {
                "reports": reports,
                "count": len(reports),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/powerbi/capacities")
async def powerbi_list_capacities():
    """List available capacities."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            capacities = await client.list_capacities()
            return {
                "capacities": capacities,
                "count": len(capacities),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Fabric endpoints
@app.get("/fabric/workspaces")
async def fabric_list_workspaces():
    """List Fabric workspaces."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            workspaces = await client.fabric_list_workspaces()
            return {
                "workspaces": workspaces,
                "count": len(workspaces),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fabric/workspaces/training")
async def fabric_generate_training_workspaces(req: PBITrainingWorkspacesRequest):
    """Generate training workspaces for workshops."""
    if not PBI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Power BI client not available")
    
    try:
        async with PowerBIClient() as client:
            result = await client.fabric_generate_training_workspaces(
                req.base_name,
                req.count,
                req.capacity_id,
            )
            return {
                "ok": len(result["errors"]) == 0,
                "workspaces": result["workspaces"],
                "errors": result["errors"],
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

'''
