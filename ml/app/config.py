"""
Configuration management for the ML service.

Uses Pydantic Settings for environment variable management with validation.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core settings
    app_name: str = "AutoML Service"
    version: str = "3.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    log_json: bool = False

    # Storage paths
    models_dir: Path = Field(default=Path("/models"))
    experiments_dir: Path = Field(default=Path("/experiments"))
    cache_dir: Path = Field(default=Path("/cache"))
    temp_dir: Path = Field(default=Path("/tmp/ml_service"))

    # Training limits
    max_rows: int = Field(default=100000, ge=100, le=10000000)
    max_features: int = Field(default=10000, ge=10)
    max_training_time_sec: int = Field(default=3600, ge=60)
    cv_folds: int = Field(default=5, ge=2, le=20)

    # Model settings
    enable_shap: bool = True
    enable_deep_learning: bool = True
    enable_time_series: bool = True
    enable_auto_feature_engineering: bool = True

    # Threading & async
    max_concurrent_jobs: int = Field(default=4, ge=1, le=32)
    job_timeout_sec: int = Field(default=7200, ge=300)

    # Caching
    enable_cache: bool = True
    cache_ttl_sec: int = Field(default=3600, ge=60)
    cache_max_size_mb: int = Field(default=1024, ge=100)

    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_requests: int = Field(default=100, ge=10)
    rate_limit_window_sec: int = Field(default=60, ge=10)

    # Security
    api_key: str | None = None
    cors_origins: list[str] = Field(default=["*"])

    # External services
    redis_url: str | None = None
    postgres_url: str | None = None
    s3_bucket: str | None = None
    mlflow_tracking_uri: str | None = None

    # Search (Meilisearch)
    meili_url: str | None = Field(
        default=None,
        description="Meilisearch base URL (e.g. http://meilisearch:7700). When unset, search endpoints return 503.",
    )
    meili_api_key: str | None = Field(
        default=None,
        description="Meilisearch API key (optional, depends on your Meilisearch config).",
    )
    meili_timeout_sec: float = Field(default=5.0, ge=0.1, le=60.0)
    meili_models_index: str = Field(default="ml_models", min_length=1)
    meili_experiments_index: str = Field(default="ml_experiments", min_length=1)

    # Search tuning (index settings)
    meili_configure_indexes: bool = True

    # Deep learning
    torch_device: str = "auto"  # auto, cpu, cuda, mps
    default_epochs: int = Field(default=100, ge=1)
    default_batch_size: int = Field(default=64, ge=1)

    # TensorFlowOnSpark
    spark_master: str = "local[*]"
    tfos_cluster_size: int = Field(default=2, ge=1)

    @field_validator("models_dir", "experiments_dir", "cache_dir", "temp_dir", mode="after")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        """Ensure directories exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid}")
        return upper


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
