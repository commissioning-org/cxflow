"""Legacy schemas preserved from the original monolithic `app.main`.

These keep request/response shapes stable while we split endpoints into routers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.config import settings


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

    # Added enhancements
    experiment_id: str | None = Field(None, description="Optional experiment ID")
    description: str | None = Field(None, description="Optional model description")

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(v) > settings.max_rows:
            raise ValueError(f"rows exceeds maximum of {settings.max_rows}")
        return v


class TrainResponse(BaseModel):
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
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    model_id: str | None = None
    error: str | None = None
    progress: float = 0.0
    created_at: str | None = None
    completed_at: str | None = None


class PredictRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to use for predictions")
    rows: list[dict[str, Any]] = Field(..., min_length=1, description="Rows to predict")
    return_probabilities: bool = Field(False, description="Return class probabilities")


class PredictResponse(BaseModel):
    model_id: str
    predictions: list[Any]
    probabilities: list[list[float]] | None = None
    inference_time_ms: float


class BatchPredictRequest(BaseModel):
    model_id: str
    rows: list[dict[str, Any]] = Field(..., min_length=1)
    batch_size: int = Field(1000, ge=100, le=10000)


class ModelInfo(BaseModel):
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
    models: list[ModelInfo]
    total: int


class FeatureImportanceResponse(BaseModel):
    model_id: str
    importances: dict[str, float]
    method: str


class ExplainRequest(BaseModel):
    model_id: str
    rows: list[dict[str, Any]] = Field(..., min_length=1, max_length=100)


class ExplainResponse(BaseModel):
    model_id: str
    shap_values: list[dict[str, float]]
    base_value: float
    method: str


class DataProfileRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=1)
    target: str | None = None


class ColumnProfile(BaseModel):
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
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    target_distribution: dict[str, int] | None = None
    suggested_problem: str | None = None


class PromoteModelRequest(BaseModel):
    stage: Literal["development", "staging", "production", "archived"] = Field(
        ..., description="Target stage"
    )
    archive_existing: bool = Field(True, description="Archive existing model in stage")


class ExperimentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class RunLogRequest(BaseModel):
    run_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)
    model_id: str | None = None


class TimeSeriesTrainRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(..., min_length=10)
    target: str = Field(..., min_length=1)
    datetime_col: str = Field(..., min_length=1)
    frequency: str = Field("D", description="Pandas offset alias")
    seasonality_period: int | None = Field(None, ge=2, le=366)
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


# ---------------------------------------------------------------------------
# TensorFlowOnSpark (TFoS) schemas
# ---------------------------------------------------------------------------


class TFoSJobRequest(BaseModel):
    """TensorFlowOnSpark job submission request."""

    job_id: str | None = None
    data_path: str = Field(..., description="Path to training data (NDJSON/CSV)")
    target_column: str = Field("label", description="Target column name")
    format: Literal["ndjson", "csv", "tfr"] = Field("ndjson", description="Data format")

    spark_master: str = Field("local[*]", description="Spark master URL")
    cluster_size: int = Field(2, ge=1, le=100, description="Number of TF workers")
    num_ps: int = Field(0, ge=0, le=10, description="Number of parameter servers")
    executor_memory: str = Field("2g", description="Memory per executor")

    epochs: int = Field(5, ge=1, le=1000)
    batch_size: int = Field(64, ge=1, le=10000)
    learning_rate: float = Field(0.001, ge=1e-6, le=1.0)

    input_mode: Literal["SPARK", "TENSORFLOW"] = Field("SPARK")
    tensorboard: bool = Field(True)
    master_node: str = Field("chief")
    async_mode: bool = Field(True, description="Run asynchronously")


class TFoSJobResponse(BaseModel):
    ok: bool
    job_id: str
    status: str
    message: str | None = None
    model_dir: str | None = None
    log_dir: str | None = None


class TFoSJobStatus(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    model_dir: str | None = None
    export_dir: str | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    metrics: dict[str, float] | None = None



# ---------------------------------------------------------------------------
# Superset schemas
# ---------------------------------------------------------------------------


class SupersetDashboardCreateRequest(BaseModel):
    """Create a Superset dashboard (minimal payload wrapper)."""

    dashboard_title: str = Field(..., description="Dashboard title")
    slug: str | None = Field(None, description="Optional URL slug")
    published: bool | None = Field(None, description="Published flag")


class SupersetSQLExecuteRequest(BaseModel):
    """Execute SQL via Superset SQL Lab."""

    database_id: int = Field(..., ge=1, description="Superset database id")
    sql: str = Field(..., min_length=1, description="SQL to execute")
    schema: str | None = Field(None, description="Optional schema")
    run_async: bool = Field(False, description="Run query asynchronously")
    select_as_cta: bool = Field(False, description="Use CTAS")
    ctas_method: str = Field("TABLE", description="CTAS method")
    tmp_table_name: str | None = Field(None, description="Optional temp table name")


class SupersetDatasetRefreshRequest(BaseModel):
    """Refresh a Superset dataset's columns from source."""

    dataset_id: int = Field(..., ge=1, description="Superset dataset id")
