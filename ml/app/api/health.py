from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.state import MODELS_DIR

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Health check endpoint."""
    return {
        "ok": True,
        "version": "2.0",
        "models_dir": str(MODELS_DIR),
        "model_count": len(list(MODELS_DIR.glob("*.joblib"))),
    }


@router.get("/readiness")
def readiness():
    """Readiness probe for Kubernetes."""
    try:
        _ = list(MODELS_DIR.iterdir())
        return {"ready": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
