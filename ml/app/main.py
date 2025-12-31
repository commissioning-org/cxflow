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

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
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
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("ML_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("automl")

MODELS_DIR = Path(os.environ.get("ML_MODELS_DIR", "/models")).resolve()
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MAX_ROWS = int(os.environ.get("ML_MAX_ROWS", "100000"))
CV_FOLDS = int(os.environ.get("ML_CV_FOLDS", "5"))
ENABLE_SHAP = os.environ.get("ML_ENABLE_SHAP", "true").lower() in ("true", "1", "yes")

# Thread pool for async training
_executor = ThreadPoolExecutor(max_workers=4)

# In-memory job tracker (in production, use Redis or DB)
_training_jobs: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Lifespan & App Setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown lifecycle."""
    logger.info("AutoML service starting up...")
    logger.info(f"Models directory: {MODELS_DIR}")
    logger.info(f"Max rows: {MAX_ROWS}, CV folds: {CV_FOLDS}, SHAP: {ENABLE_SHAP}")
    # Load existing model count
    model_count = len(list(MODELS_DIR.glob("*.joblib")))
    logger.info(f"Loaded {model_count} existing models")
    yield
    logger.info("AutoML service shutting down...")
    _executor.shutdown(wait=False)


app = FastAPI(
    title="AutoML Service",
    version="2.0",
    description="Enhanced AutoML with hyperparameter tuning, explainability, and async training",
    lifespan=lifespan,
)


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


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Make predictions using a trained model."""
    start_time = time.time()

    art = _artifacts(req.model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        model = joblib.load(art.model_path)
        meta = json.loads(art.meta_path.read_text())
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

    model = joblib.load(art.model_path)
    meta = json.loads(art.meta_path.read_text())
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

    for meta_path in MODELS_DIR.glob("*.json"):
        if meta_path.name.endswith(".importance.json") or meta_path.name.endswith(".shap.json"):
            continue

        try:
            meta = json.loads(meta_path.read_text())
            model_path = MODELS_DIR / f"{meta_path.stem}.joblib"

            # Apply filters
            if tag and tag not in meta.get("tags", []):
                continue
            if problem and meta.get("problem") != problem:
                continue

            models.append(
                ModelInfo(
                    model_id=meta["model_id"],
                    model_name=meta.get("model_name"),
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

    meta = json.loads(art.meta_path.read_text())

    return ModelInfo(
        model_id=meta["model_id"],
        model_name=meta.get("model_name"),
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
        meta = json.loads(art.meta_path.read_text())
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
        meta = json.loads(art.meta_path.read_text())
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
    ]

    return StreamingResponse(iter(["\n".join(lines) + "\n"]), media_type="text/plain")


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
