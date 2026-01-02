from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.core.artifacts import artifacts
from app.core.automl import clear_caches, extract_feature_importance, get_meta_from_cache
from app.core.registry import load_registry, promote_model as promote_model_core, remove_from_registry
from app.core.state import MODELS_DIR
from app.schemas.legacy import (
    ExplainRequest,
    ExplainResponse,
    FeatureImportanceResponse,
    ModelInfo,
    ModelListResponse,
    PromoteModelRequest,
)

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelListResponse)
def list_models(
    tag: str | None = Query(None),
    problem: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    models: list[ModelInfo] = []

    registry = load_registry()
    by_id = registry.get("by_id", {})

    for meta_path in MODELS_DIR.glob("*.json"):
        if meta_path.name.startswith("_"):
            continue
        if meta_path.name.endswith(".importance.json") or meta_path.name.endswith(".shap.json") or meta_path.name.endswith(".ts.json"):
            continue

        try:
            meta = json.loads(meta_path.read_text())
            model_path = MODELS_DIR / f"{meta_path.stem}.joblib"

            reg = by_id.get(meta.get("model_id")) if isinstance(meta, dict) else None

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
                    features=meta.get("features", []),
                    row_count=meta.get("row_count", 0),
                    created_at=meta.get("created_at", ""),
                    file_size_bytes=model_path.stat().st_size if model_path.exists() else 0,
                    tags=meta.get("tags", []),
                )
            )
        except Exception:
            continue

    models.sort(key=lambda m: m.created_at, reverse=True)
    total = len(models)
    models = models[offset : offset + limit]
    return ModelListResponse(models=models, total=total)


@router.get("/models/{model_id}", response_model=ModelInfo)
def get_model(model_id: str):
    art = artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    meta = get_meta_from_cache(model_id)
    registry = load_registry()
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
        features=meta.get("features", []),
        row_count=meta.get("row_count", 0),
        created_at=meta.get("created_at", ""),
        file_size_bytes=art.model_path.stat().st_size if art.model_path.exists() else 0,
        tags=meta.get("tags", []),
    )


@router.delete("/models/{model_id}")
def delete_model(model_id: str):
    art = artifacts(model_id)

    if not art.meta_path.exists() and not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    deleted = []
    for path in [art.model_path, art.meta_path, art.importance_path, art.shap_path]:
        if path.exists():
            path.unlink()
            deleted.append(path.name)

    clear_caches(model_id)
    try:
        remove_from_registry(model_id)
    except Exception:
        pass

    return {"deleted": True, "model_id": model_id, "files": deleted}


@router.get("/models/{model_id}/importance", response_model=FeatureImportanceResponse)
def get_feature_importance(model_id: str):
    art = artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    if art.importance_path.exists():
        importances = json.loads(art.importance_path.read_text())
        return FeatureImportanceResponse(model_id=model_id, importances=importances, method="cached")

    try:
        model = joblib.load(art.model_path)
        meta = get_meta_from_cache(model_id)
        importances = extract_feature_importance(model, meta.get("features", []))
        if importances:
            art.importance_path.write_text(json.dumps(importances, indent=2))
        return FeatureImportanceResponse(model_id=model_id, importances=importances, method="computed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute importance: {e}")


@router.post("/models/{model_id}/explain", response_model=ExplainResponse)
def explain_predictions(model_id: str, req: ExplainRequest):
    if not settings.enable_shap:
        raise HTTPException(status_code=400, detail="SHAP explanations disabled")

    art = artifacts(model_id)
    if not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        import shap  # type: ignore
    except ImportError:
        raise HTTPException(status_code=501, detail="SHAP not installed")

    try:
        model = joblib.load(art.model_path)
        meta = get_meta_from_cache(model_id)
        df = pd.DataFrame(req.rows)[meta["features"]]

        estimator = model.named_steps.get("model")
        preprocessor = model.named_steps.get("preprocess")

        X_transformed = preprocessor.transform(df)

        if hasattr(estimator, "predict_proba"):
            explainer = shap.TreeExplainer(estimator, feature_perturbation="interventional")
        else:
            explainer = shap.Explainer(estimator)

        shap_values = explainer.shap_values(X_transformed)

        if isinstance(shap_values, list):
            shap_values = shap_values[1] if len(shap_values) == 2 else np.mean(shap_values, axis=0)

        try:
            feature_names = list(preprocessor.get_feature_names_out())
        except Exception:
            feature_names = meta["features"]

        result_shap: list[dict[str, float]] = []
        for row_idx in range(len(df)):
            row_shap = {}
            for feat_idx, feat_name in enumerate(feature_names[: shap_values.shape[1]]):
                row_shap[str(feat_name)] = float(shap_values[row_idx, feat_idx])
            result_shap.append(row_shap)

        expected_value = explainer.expected_value
        base = float(expected_value) if np.isscalar(expected_value) else float(expected_value[0])

        return ExplainResponse(
            model_id=model_id,
            shap_values=result_shap,
            base_value=base,
            method="TreeExplainer" if hasattr(estimator, "predict_proba") else "Explainer",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/promote")
def promote_model(model_id: str, req: PromoteModelRequest):
    art = artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        record = promote_model_core(model_id=model_id, stage=req.stage, archive_existing=req.archive_existing)

        meta = get_meta_from_cache(model_id)
        meta["stage"] = record.get("stage")
        meta["version"] = record.get("version")
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        art.meta_path.write_text(json.dumps(meta, indent=2))

        clear_caches(model_id)
        return {"ok": True, "model_id": model_id, "stage": record.get("stage"), "version": record.get("version")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/resolve")
def resolve_model(stage: Literal["development", "staging", "production"] = Query("production")):
    registry = load_registry()
    mid = registry.get("by_stage", {}).get(stage)
    if not mid:
        raise HTTPException(status_code=404, detail=f"No model in stage '{stage}'")
    return {"stage": stage, "model_id": mid}


@router.get("/models/{model_id}/card")
def model_card(model_id: str):
    art = artifacts(model_id)
    if not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    meta = get_meta_from_cache(model_id)
    importance = None
    if art.importance_path.exists():
        try:
            importance = json.loads(art.importance_path.read_text())
        except Exception:
            importance = None

    top_features = None
    if isinstance(importance, dict) and importance:
        top_features = list(importance.items())[:20]

    registry = load_registry()
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
