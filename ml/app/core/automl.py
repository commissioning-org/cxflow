from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Lasso, LogisticRegression, Ridge, SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.config import settings
from app.core.artifacts import artifacts
from app.core.experiments import log_run
from app.core.registry import register_model
from app.core.state import _META_CACHE, _MODEL_CACHE, _training_jobs, logger, touch_cache_hit
from app.schemas.legacy import JobStatus, ProblemType


def infer_problem(y: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(y):
        uniq = y.dropna().nunique()
        if uniq <= 20 or uniq < len(y) * 0.05:
            return ProblemType.CLASSIFICATION.value
        return ProblemType.REGRESSION.value
    return ProblemType.CLASSIFICATION.value


def default_metric(problem: str) -> str:
    return "rmse" if problem == ProblemType.REGRESSION.value else "f1"


def metric_direction(metric: str) -> Literal["maximize", "minimize"]:
    return "minimize" if metric in ("rmse", "mae") else "maximize"


def build_preprocess(X: pd.DataFrame) -> ColumnTransformer:
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
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
            ("cat", categorical_pipeline, categorical_cols),
        ],
        remainder="drop",
    )


def candidates(problem: str, enable_tuning: bool = False) -> list[tuple[str, Any, dict]]:
    if problem == ProblemType.REGRESSION.value:
        cands = [
            ("ridge", Ridge(random_state=42), {"alpha": [0.1, 1.0, 10.0]}),
            ("lasso", Lasso(random_state=42, max_iter=2000), {"alpha": [0.01, 0.1, 1.0]}),
            (
                "elasticnet",
                ElasticNet(random_state=42, max_iter=2000),
                {"alpha": [0.1, 1.0], "l1_ratio": [0.2, 0.5, 0.8]},
            ),
            ("dt", DecisionTreeRegressor(random_state=42), {"max_depth": [5, 10, 20, None]}),
            (
                "rf",
                RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
                {"n_estimators": [100, 200], "max_depth": [10, 20, None]},
            ),
            (
                "gbm",
                GradientBoostingRegressor(random_state=42),
                {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
            ),
            ("hgb", HistGradientBoostingRegressor(random_state=42), {"max_iter": [100, 200]}),
            ("svr", SVR(), {"C": [0.1, 1.0, 10.0], "kernel": ["rbf", "linear"]}),
            (
                "mlp",
                MLPRegressor(random_state=42, max_iter=2000),
                {
                    "hidden_layer_sizes": [(64,), (128,), (64, 32)],
                    "alpha": [0.0001, 0.001],
                    "learning_rate_init": [0.001, 0.01],
                },
            ),
        ]
    else:
        cands = [
            ("logreg", LogisticRegression(max_iter=2000, random_state=42), {"C": [0.1, 1.0, 10.0]}),
            ("sgd", SGDClassifier(random_state=42, max_iter=2000), {"alpha": [0.0001, 0.001, 0.01]}),
            ("dt", DecisionTreeClassifier(random_state=42), {"max_depth": [5, 10, 20, None]}),
            (
                "rf",
                RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
                {"n_estimators": [100, 200], "max_depth": [10, 20, None]},
            ),
            (
                "gbm",
                GradientBoostingClassifier(random_state=42),
                {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1]},
            ),
            ("hgb", HistGradientBoostingClassifier(random_state=42), {"max_iter": [100, 200]}),
            ("svc", SVC(random_state=42, probability=True), {"C": [0.1, 1.0, 10.0]}),
            (
                "mlp",
                MLPClassifier(random_state=42, max_iter=2000),
                {
                    "hidden_layer_sizes": [(64,), (128,), (64, 32)],
                    "alpha": [0.0001, 0.001],
                    "learning_rate_init": [0.001, 0.01],
                },
            ),
        ]

    if not enable_tuning:
        return [(n, e, {}) for n, e, _ in cands]
    return cands


def compute_score(
    problem: str,
    metric: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
) -> float:
    if problem == ProblemType.REGRESSION.value:
        if metric == "mae":
            return float(mean_absolute_error(y_true, y_pred))
        if metric == "r2":
            return float(r2_score(y_true, y_pred))
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))

    if metric == "accuracy":
        return float(accuracy_score(y_true, y_pred))
    if metric == "roc_auc" and y_proba is not None:
        try:
            if y_proba.ndim == 2 and y_proba.shape[1] == 2:
                return float(roc_auc_score(y_true, y_proba[:, 1]))
            return float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
        except Exception:
            pass
    return float(f1_score(y_true, y_pred, average="weighted"))


def extract_feature_importance(pipeline: Pipeline, feature_names: list[str]) -> dict[str, float]:
    model = pipeline.named_steps.get("model")
    if model is None:
        return {}

    try:
        preprocessor = pipeline.named_steps.get("preprocess")
        if hasattr(preprocessor, "get_feature_names_out"):
            transformed_names = list(preprocessor.get_feature_names_out())
        else:
            transformed_names = feature_names
    except Exception:
        transformed_names = feature_names

    importances: dict[str, float] = {}
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        for i, name in enumerate(transformed_names[: len(imp)]):
            importances[str(name)] = float(imp[i])
    elif hasattr(model, "coef_"):
        coef = np.abs(model.coef_)
        if coef.ndim > 1:
            coef = coef.mean(axis=0)
        for i, name in enumerate(transformed_names[: len(coef)]):
            importances[str(name)] = float(coef[i])

    return dict(sorted(importances.items(), key=lambda x: abs(x[1]), reverse=True))


def generate_data_hash(df: pd.DataFrame) -> str:
    content = df.to_json(orient="records")
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_model_from_cache(model_id: str) -> Any:
    art = artifacts(model_id)
    if not art.model_path.exists():
        raise FileNotFoundError("Model not found")
    mtime = art.model_path.stat().st_mtime

    if settings.enable_cache:
        cached = _MODEL_CACHE.get(model_id)
        if cached and cached.get("mtime") == mtime:
            touch_cache_hit("model_hit")
            return cached["model"]
        touch_cache_hit("model_miss")

    model = joblib.load(art.model_path)
    if settings.enable_cache:
        _MODEL_CACHE[model_id] = {"mtime": mtime, "model": model, "loaded_at": time.time()}
    return model


def get_meta_from_cache(model_id: str) -> dict[str, Any]:
    art = artifacts(model_id)
    if not art.meta_path.exists():
        raise FileNotFoundError("Metadata not found")
    mtime = art.meta_path.stat().st_mtime

    if settings.enable_cache:
        cached = _META_CACHE.get(model_id)
        if cached and cached.get("mtime") == mtime:
            touch_cache_hit("meta_hit")
            return cached["meta"]
        touch_cache_hit("meta_miss")

    meta = json.loads(art.meta_path.read_text())
    if settings.enable_cache:
        _META_CACHE[model_id] = {"mtime": mtime, "meta": meta, "loaded_at": time.time()}
    return meta


def clear_caches(model_id: str) -> None:
    _MODEL_CACHE.pop(model_id, None)
    _META_CACHE.pop(model_id, None)


def run_training(
    df: pd.DataFrame,
    target: str,
    problem: str | None,
    metric: str | None,
    test_size: float,
    random_state: int,
    enable_cv: bool,
    enable_tuning: bool,
    model_name: str | None,
    tags: list[str],
    description: str | None = None,
    experiment_id: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    logger.info(f"Starting training job: rows={len(df)}, target={target}")

    if target not in df.columns:
        raise ValueError(f"target '{target}' not found in input columns: {list(df.columns)}")

    y = df[target]
    X = df.drop(columns=[target])

    if X.empty or len(X.columns) == 0:
        raise ValueError("No features available after dropping target column")

    actual_problem = problem or infer_problem(y)
    actual_metric = metric or default_metric(actual_problem)
    direction = metric_direction(actual_metric)

    label_encoder = None
    if actual_problem == ProblemType.CLASSIFICATION.value:
        if not pd.api.types.is_numeric_dtype(y):
            label_encoder = LabelEncoder()
            y = pd.Series(label_encoder.fit_transform(y), index=y.index)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if actual_problem == ProblemType.CLASSIFICATION.value else None,
    )

    preprocess = build_preprocess(X_train)

    best_name: str | None = None
    best_model: Pipeline | None = None
    best_score: float | None = None
    best_cv_score: float | None = None
    best_cv_std: float | None = None

    cands = candidates(actual_problem, enable_tuning)
    total_candidates = len(cands)

    for idx, (name, est, param_grid) in enumerate(cands):
        if job_id:
            if _training_jobs.get(job_id, {}).get("status") == JobStatus.CANCELLED.value:
                raise RuntimeError("Training cancelled")
            _training_jobs[job_id]["progress"] = (idx + 1) / total_candidates * 0.8

        try:
            pipe = Pipeline(steps=[("preprocess", preprocess), ("model", est)])

            if enable_tuning and param_grid:
                grid_params = {f"model__{k}": v for k, v in param_grid.items()}
                scoring = "neg_root_mean_squared_error" if actual_metric == "rmse" else actual_metric
                if actual_metric == "mae":
                    scoring = "neg_mean_absolute_error"

                grid = GridSearchCV(
                    pipe,
                    grid_params,
                    cv=max(2, min(settings.cv_folds, len(X_train) // 2)),
                    scoring=scoring,
                    n_jobs=-1,
                    error_score="raise",
                )
                grid.fit(X_train, y_train)
                pipe = grid.best_estimator_
                cv_score = abs(grid.best_score_) if "neg" in str(scoring) else grid.best_score_
                cv_std = None
            else:
                pipe.fit(X_train, y_train)
                cv_score = None
                cv_std = None

                if enable_cv and len(X_train) >= settings.cv_folds * 2:
                    try:
                        scoring = "neg_root_mean_squared_error" if actual_metric == "rmse" else actual_metric
                        if actual_metric == "mae":
                            scoring = "neg_mean_absolute_error"

                        cv_scores = cross_val_score(
                            pipe, X_train, y_train, cv=settings.cv_folds, scoring=scoring, n_jobs=-1
                        )
                        cv_score = float(np.mean(np.abs(cv_scores)))
                        cv_std = float(np.std(np.abs(cv_scores)))
                    except Exception as e:
                        logger.warning(f"CV failed for {name}: {e}")

            preds = pipe.predict(X_test)
            proba = None
            if hasattr(pipe, "predict_proba"):
                try:
                    proba = pipe.predict_proba(X_test)
                except Exception:
                    pass

            score = compute_score(actual_problem, actual_metric, np.asarray(y_test), preds, proba)

            is_better = False
            if best_score is None:
                is_better = True
            elif direction == "minimize":
                is_better = score < best_score
            else:
                is_better = score > best_score

            if is_better:
                best_name = name
                best_model = pipe
                best_score = score
                best_cv_score = cv_score
                best_cv_std = cv_std

        except Exception as e:
            logger.warning(f"Failed to train {name}: {e}")
            continue

    if best_model is None or best_score is None:
        raise RuntimeError("All candidate models failed to train")

    model_id = str(uuid.uuid4())
    art = artifacts(model_id)

    joblib.dump(best_model, art.model_path)

    importance = extract_feature_importance(best_model, list(X.columns))
    if importance:
        art.importance_path.write_text(json.dumps(importance, indent=2))

    encoder_info = None
    if label_encoder:
        encoder_info = list(label_encoder.classes_)

    training_time = time.time() - start_time
    created_at = datetime.now(timezone.utc).isoformat()

    meta: dict[str, Any] = {
        "model_id": model_id,
        "model_name": model_name,
        "description": description,
        "problem": actual_problem,
        "metric": actual_metric,
        "score": float(best_score),
        "cv_score": best_cv_score,
        "cv_std": best_cv_std,
        "selected": best_name,
        "features": list(X.columns),
        "row_count": len(df),
        "training_time_sec": training_time,
        "created_at": created_at,
        "tags": tags,
        "label_encoder": encoder_info,
        "data_hash": generate_data_hash(df),
    }

    try:
        meta = register_model(meta)
    except Exception as e:
        logger.warning(f"Registry update failed: {e}")

    if experiment_id:
        try:
            run = log_run(
                experiment_id=experiment_id,
                run_id=None,
                metrics={"score": float(best_score), "training_time_sec": float(training_time)},
                params={"problem": actual_problem, "metric": actual_metric, "selected_model": best_name},
                tags={"model_name": model_name or ""},
                model_id=model_id,
            )
            meta["experiment_id"] = experiment_id
            meta["run_id"] = run["run_id"]
        except Exception as e:
            logger.warning(f"Experiment logging failed: {e}")

    art.meta_path.write_text(json.dumps(meta, indent=2))

    if job_id:
        _training_jobs[job_id]["progress"] = 1.0

    return meta
