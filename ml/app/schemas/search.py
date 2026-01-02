from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResponse(BaseModel):
    index: str
    query: str
    hits: list[dict[str, Any]]
    offset: int
    limit: int
    estimated_total_hits: int | None = None
    processing_time_ms: int | None = None
    raw: dict[str, Any] | None = None


class ReindexRequest(BaseModel):
    models: bool = True
    experiments: bool = True
    batch_size: int = Field(default=1000, ge=1, le=5000)
    dry_run: bool = False


class ReindexResponse(BaseModel):
    ok: bool
    models_index: str | None = None
    experiments_index: str | None = None
    model_docs: int = 0
    experiment_docs: int = 0
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None
