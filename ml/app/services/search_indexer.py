from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from app.config import settings
from app.core.experiments import load_experiments_index
from app.core.registry import load_registry
from app.core.state import MODELS_DIR
from app.services.meilisearch import MeiliClient, MeiliTask


@dataclass(frozen=True)
class ReindexResult:
    models_index: str
    experiments_index: str
    model_docs: int
    experiment_docs: int
    tasks: list[MeiliTask]


def _chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_model_documents() -> list[dict[str, Any]]:
    """Build Meilisearch documents from the local model metadata store."""

    docs: list[dict[str, Any]] = []

    registry = load_registry()
    by_id: dict[str, Any] = registry.get("by_id", {})

    for meta_path in MODELS_DIR.glob("*.json"):
        if meta_path.name.startswith("_"):
            continue
        if meta_path.name.endswith(".importance.json") or meta_path.name.endswith(".shap.json") or meta_path.name.endswith(".ts.json"):
            continue

        try:
            meta = json.loads(meta_path.read_text())
            if not isinstance(meta, dict) or "model_id" not in meta:
                continue

            model_id = str(meta.get("model_id"))
            reg = by_id.get(model_id) if isinstance(by_id, dict) else None

            # Keep the indexed doc shape stable-ish and filter-friendly.
            docs.append(
                {
                    "model_id": model_id,
                    "model_name": meta.get("model_name"),
                    "description": meta.get("description"),
                    "version": meta.get("version") or (reg.get("version") if reg else None),
                    "stage": meta.get("stage") or (reg.get("stage") if reg else None),
                    "problem": meta.get("problem"),
                    "metric": meta.get("metric"),
                    "score": meta.get("score"),
                    "cv_score": meta.get("cv_score"),
                    "selected_model": meta.get("selected"),
                    "features": meta.get("features", []),
                    "row_count": meta.get("row_count", 0),
                    "created_at": meta.get("created_at"),
                    "tags": meta.get("tags", []),
                }
            )
        except Exception:
            continue

    # Deterministic ordering helps debug diffs between reindexes.
    docs.sort(key=lambda d: (d.get("created_at") or "", d.get("model_id") or ""), reverse=True)
    return docs


def build_experiment_documents() -> list[dict[str, Any]]:
    """Build Meilisearch documents from the local experiments index."""

    idx = load_experiments_index()
    exps = idx.get("experiments", [])

    docs: list[dict[str, Any]] = []
    for exp in exps if isinstance(exps, list) else []:
        if not isinstance(exp, dict) or "experiment_id" not in exp:
            continue
        docs.append(
            {
                "experiment_id": str(exp.get("experiment_id")),
                "name": exp.get("name"),
                "description": exp.get("description"),
                "tags": exp.get("tags", {}),
                "created_at": exp.get("created_at"),
                "updated_at": exp.get("updated_at"),
                "run_count": exp.get("run_count", 0),
            }
        )

    docs.sort(key=lambda d: (d.get("created_at") or "", d.get("experiment_id") or ""), reverse=True)
    return docs


def model_index_settings() -> dict[str, Any]:
    return {
        "searchableAttributes": [
            "model_name",
            "description",
            "problem",
            "metric",
            "tags",
            "features",
        ],
        "filterableAttributes": [
            "stage",
            "problem",
            "metric",
            "tags",
        ],
        "sortableAttributes": [
            "created_at",
            "score",
        ],
    }


def experiment_index_settings() -> dict[str, Any]:
    return {
        "searchableAttributes": [
            "name",
            "description",
            "tags",
        ],
        "filterableAttributes": [
            "tags",
        ],
        "sortableAttributes": [
            "created_at",
        ],
    }


def reindex_models(client: MeiliClient, *, batch_size: int = 1000) -> tuple[int, list[MeiliTask]]:
    uid = settings.meili_models_index
    client.ensure_index(
        uid,
        primary_key="model_id",
        settings_payload=model_index_settings() if settings.meili_configure_indexes else None,
        configure=settings.meili_configure_indexes,
    )

    docs = build_model_documents()
    tasks: list[MeiliTask] = []
    for batch in _chunks(docs, batch_size):
        tasks.append(client.add_documents(uid, batch, primary_key="model_id"))

    return len(docs), tasks


def reindex_experiments(client: MeiliClient, *, batch_size: int = 1000) -> tuple[int, list[MeiliTask]]:
    uid = settings.meili_experiments_index
    client.ensure_index(
        uid,
        primary_key="experiment_id",
        settings_payload=experiment_index_settings() if settings.meili_configure_indexes else None,
        configure=settings.meili_configure_indexes,
    )

    docs = build_experiment_documents()
    tasks: list[MeiliTask] = []
    for batch in _chunks(docs, batch_size):
        tasks.append(client.add_documents(uid, batch, primary_key="experiment_id"))

    return len(docs), tasks


def reindex_all(client: MeiliClient, *, batch_size: int = 1000) -> ReindexResult:
    model_count, model_tasks = reindex_models(client, batch_size=batch_size)
    exp_count, exp_tasks = reindex_experiments(client, batch_size=batch_size)

    return ReindexResult(
        models_index=settings.meili_models_index,
        experiments_index=settings.meili_experiments_index,
        model_docs=model_count,
        experiment_docs=exp_count,
        tasks=[*model_tasks, *exp_tasks],
    )
