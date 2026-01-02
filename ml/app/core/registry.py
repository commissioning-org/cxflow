from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.io_utils import read_json, write_json
from app.core.state import REGISTRY_PATH


def load_registry() -> dict[str, Any]:
    return read_json(
        REGISTRY_PATH,
        {
            "by_id": {},
            "by_stage": {},
            "versions": {},
            "updated_at": None,
        },
    )


def save_registry(registry: dict[str, Any]) -> None:
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(REGISTRY_PATH, registry)


def model_key(meta: dict[str, Any]) -> str:
    return (meta.get("model_name") or meta.get("model_id") or "unknown").strip()


def register_model(meta: dict[str, Any]) -> dict[str, Any]:
    registry = load_registry()
    key = model_key(meta)

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
    registry.setdefault("by_stage", {})
    if stage and stage not in registry["by_stage"]:
        registry["by_stage"][stage] = model_id

    save_registry(registry)

    meta["version"] = next_version
    meta["stage"] = stage
    return meta


def promote_model(model_id: str, stage: str, archive_existing: bool = True) -> dict[str, Any]:
    registry = load_registry()
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
    save_registry(registry)
    return by_id[model_id]


def remove_from_registry(model_id: str) -> None:
    registry = load_registry()
    registry.get("by_id", {}).pop(model_id, None)
    by_stage = registry.get("by_stage", {})
    for stg, mid in list(by_stage.items()):
        if mid == model_id:
            by_stage.pop(stg, None)
    registry["by_stage"] = by_stage
    save_registry(registry)
