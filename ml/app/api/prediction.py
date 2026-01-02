from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from app.core.artifacts import artifacts
from app.core.automl import get_meta_from_cache, get_model_from_cache
from app.schemas.legacy import BatchPredictRequest, PredictRequest, PredictResponse

router = APIRouter(tags=["prediction"])


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    start_time = time.time()

    art = artifacts(req.model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        model = get_model_from_cache(req.model_id)
        meta = get_meta_from_cache(req.model_id)
        df = pd.DataFrame(req.rows)

        missing = set(meta["features"]) - set(df.columns)
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required features: {missing}")

        df = df[meta["features"]]

        preds = model.predict(df)

        if meta.get("label_encoder"):
            label_classes = meta["label_encoder"]
            preds = [label_classes[int(p)] for p in preds]

        probabilities = None
        if req.return_probabilities and hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(df)
                probabilities = proba.tolist()
            except Exception:
                probabilities = None

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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch")
async def predict_batch(req: BatchPredictRequest):
    art = artifacts(req.model_id)
    if not art.model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    model = get_model_from_cache(req.model_id)
    meta = get_meta_from_cache(req.model_id)
    df = pd.DataFrame(req.rows)

    df = df[meta["features"]]

    async def generate():
        for i in range(0, len(df), req.batch_size):
            batch = df.iloc[i : i + req.batch_size]
            preds = model.predict(batch)

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
