from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.state import MODELS_DIR


@dataclass(frozen=True)
class ModelArtifacts:
    model_path: Path
    meta_path: Path
    importance_path: Path
    shap_path: Path


def artifacts(model_id: str) -> ModelArtifacts:
    safe = "".join(c for c in model_id if c.isalnum() or c in ("-", "_"))
    return ModelArtifacts(
        model_path=MODELS_DIR / f"{safe}.joblib",
        meta_path=MODELS_DIR / f"{safe}.json",
        importance_path=MODELS_DIR / f"{safe}.importance.json",
        shap_path=MODELS_DIR / f"{safe}.shap.json",
    )


@dataclass(frozen=True)
class TimeSeriesArtifacts:
    model_path: Path
    meta_path: Path


def ts_artifacts(model_id: str) -> TimeSeriesArtifacts:
    safe = "".join(c for c in model_id if c.isalnum() or c in ("-", "_"))
    return TimeSeriesArtifacts(
        model_path=MODELS_DIR / f"{safe}.ts.joblib",
        meta_path=MODELS_DIR / f"{safe}.ts.json",
    )
