from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


app = FastAPI(title="AutoML Service", version="1.0")

MODELS_DIR = Path(os.environ.get("ML_MODELS_DIR", "/models")).resolve()
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class TrainRequest(BaseModel):
    # Data: list of records (JSON objects) OR you can send a dict with a "rows" key.
    rows: list[dict[str, Any]] = Field(..., min_length=5)
    target: str = Field(..., min_length=1)
    problem: Literal["classification", "regression"] | None = None
    metric: Literal["accuracy", "f1", "rmse"] | None = None
    test_size: float = Field(0.2, ge=0.05, le=0.5)
    random_state: int = 42


class TrainResponse(BaseModel):
    model_id: str
    problem: str
    metric: str
    score: float
    features: list[str]


class PredictRequest(BaseModel):
    model_id: str
    rows: list[dict[str, Any]] = Field(..., min_length=1)


class PredictResponse(BaseModel):
    model_id: str
    predictions: list[Any]


@dataclass(frozen=True)
class ModelArtifacts:
    model_path: Path
    meta_path: Path


def _artifacts(model_id: str) -> ModelArtifacts:
    safe = "".join(c for c in model_id if c.isalnum() or c in ("-", "_"))
    return ModelArtifacts(
        model_path=MODELS_DIR / f"{safe}.joblib",
        meta_path=MODELS_DIR / f"{safe}.json",
    )


def _infer_problem(y: pd.Series) -> str:
    # Heuristic: numeric with many uniques -> regression; else classification
    if pd.api.types.is_numeric_dtype(y):
        uniq = y.dropna().nunique()
        if uniq > 20:
            return "regression"
    return "classification"


def _default_metric(problem: str) -> str:
    return "rmse" if problem == "regression" else "f1"


def _build_preprocess(X: pd.DataFrame) -> ColumnTransformer:
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
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
            ("cat", categorical_pipeline, categorical_cols),
        ],
        remainder="drop",
    )


def _candidates(problem: str):
    if problem == "regression":
        return [
            ("ridge", Ridge(random_state=42)),
            ("rf", RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)),
            ("hgb", HistGradientBoostingRegressor(random_state=42)),
        ]

    # classification
    return [
        ("logreg", LogisticRegression(max_iter=2000, n_jobs=None)),
        ("rf", RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)),
        ("hgb", HistGradientBoostingClassifier(random_state=42)),
    ]


def _score(problem: str, metric: str, y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if problem == "regression":
        rmse = float(mean_squared_error(y_true, y_pred, squared=False))
        return rmse

    # classification
    if metric == "accuracy":
        return float(accuracy_score(y_true, y_pred))
    return float(f1_score(y_true, y_pred, average="weighted"))


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
