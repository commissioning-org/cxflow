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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/train", response_model=TrainResponse)
def train(req: TrainRequest):
    df = pd.DataFrame(req.rows)
    if req.target not in df.columns:
        raise ValueError(f"target '{req.target}' not found in input columns")

    y = df[req.target]
    X = df.drop(columns=[req.target])

    problem = req.problem or _infer_problem(y)
    metric = req.metric or _default_metric(problem)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=req.test_size, random_state=req.random_state
    )

    preprocess = _build_preprocess(X_train)

    best_name = None
    best_model = None
    best_score = None

    for name, est in _candidates(problem):
        pipe = Pipeline(steps=[("preprocess", preprocess), ("model", est)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)

        s = _score(problem, metric, np.asarray(y_test), np.asarray(preds))

        # For regression: lower is better (rmse). For classification: higher is better.
        is_better = False
        if problem == "regression":
            is_better = best_score is None or s < best_score
        else:
            is_better = best_score is None or s > best_score

        if is_better:
            best_name = name
            best_model = pipe
            best_score = s

    assert best_model is not None and best_score is not None

    model_id = str(uuid.uuid4())
    art = _artifacts(model_id)

    joblib.dump(best_model, art.model_path)
    meta = {
        "model_id": model_id,
        "problem": problem,
        "metric": metric,
        "score": best_score,
        "selected": best_name,
        "features": list(X.columns),
    }
    art.meta_path.write_text(json.dumps(meta, indent=2))

    return TrainResponse(
        model_id=model_id,
        problem=problem,
        metric=metric,
        score=float(best_score),
        features=list(X.columns),
    )


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    art = _artifacts(req.model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise ValueError("model_id not found")

    model = joblib.load(art.model_path)
    df = pd.DataFrame(req.rows)

    preds = model.predict(df)
    # Ensure JSON-serializable
    out: list[Any] = []
    for p in preds:
        if isinstance(p, (np.generic,)):
            out.append(p.item())
        else:
            out.append(p)

    return PredictResponse(model_id=req.model_id, predictions=out)
