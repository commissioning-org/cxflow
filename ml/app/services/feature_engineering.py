from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.feature_selection import (
    VarianceThreshold,
    mutual_info_classif,
    mutual_info_regression,
)
from sklearn.preprocessing import MinMaxScaler, QuantileTransformer, RobustScaler, StandardScaler


def _infer_task_from_target(y: pd.Series) -> Literal["classification", "regression"]:
    if pd.api.types.is_numeric_dtype(y):
        uniq = y.dropna().nunique()
        # treat small-unique numeric as classification (e.g., 0/1)
        if uniq <= 20 or uniq < len(y) * 0.05:
            return "classification"
        return "regression"
    return "classification"


def _extract_datetime_features(
    df: pd.DataFrame,
    col: str,
    features: list[str],
) -> pd.DataFrame:
    s = pd.to_datetime(df[col], errors="coerce", utc=True)

    out = df.copy()
    prefix = f"{col}__dt"

    if "year" in features:
        out[f"{prefix}_year"] = s.dt.year
    if "month" in features:
        out[f"{prefix}_month"] = s.dt.month
    if "day" in features:
        out[f"{prefix}_day"] = s.dt.day
    if "dayofweek" in features:
        out[f"{prefix}_dayofweek"] = s.dt.dayofweek
    if "hour" in features:
        out[f"{prefix}_hour"] = s.dt.hour
    if "is_weekend" in features:
        out[f"{prefix}_is_weekend"] = (s.dt.dayofweek >= 5).astype(int)

    return out


def _frequency_encode(series: pd.Series) -> tuple[pd.Series, dict[str, float]]:
    vc = series.fillna("<NA>").astype(str).value_counts(normalize=True)
    mapping = vc.to_dict()
    encoded = series.fillna("<NA>").astype(str).map(mapping).astype(float)
    return encoded, mapping


def _target_encode(
    x: pd.Series, y: pd.Series, task: Literal["classification", "regression"]
) -> tuple[pd.Series, dict[str, float]]:
    # For classification, encode by P(y==mode) per category.
    # For regression, encode by mean(y) per category.
    x_key = x.fillna("<NA>").astype(str)

    if task == "classification":
        # choose most frequent class as "positive" in a stable way
        mode = y.mode(dropna=True)
        positive = mode.iloc[0] if len(mode) else None
        if positive is None:
            mapping = {}
            return pd.Series(np.zeros(len(x), dtype=float), index=x.index), mapping
        grp = pd.DataFrame({"x": x_key, "y": y}).groupby("x")["y"]
        mapping = (grp.apply(lambda s: float(np.mean(s == positive)))).to_dict()
    else:
        y_num = pd.to_numeric(y, errors="coerce")
        grp = pd.DataFrame({"x": x_key, "y": y_num}).groupby("x")["y"]
        mapping = grp.mean().fillna(0.0).astype(float).to_dict()

    global_fallback = float(pd.to_numeric(y, errors="coerce").mean()) if task == "regression" else 0.0
    encoded = x_key.map(lambda k: mapping.get(k, global_fallback)).astype(float)
    return encoded, mapping


def _scale_numeric(
    df: pd.DataFrame,
    cols: list[str],
    method: Literal["standard", "minmax", "robust", "quantile"],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not cols:
        return df, {"method": method, "columns": []}

    X = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)

    if method == "minmax":
        scaler = MinMaxScaler()
    elif method == "robust":
        scaler = RobustScaler()
    elif method == "quantile":
        scaler = QuantileTransformer(output_distribution="normal", random_state=42)
    else:
        scaler = StandardScaler()

    Xs = scaler.fit_transform(X)
    out = df.copy()
    for i, c in enumerate(cols):
        out[c] = Xs[:, i]

    info = {"method": method, "columns": cols}
    return out, info


def engineer_features(
    rows: list[dict[str, Any]],
    target: str | None,
    generate_interactions: bool,
    max_interactions: int,
    encode_categorical: bool,
    categorical_method: Literal["onehot", "target", "frequency", "ordinal"],
    handle_high_cardinality: bool,
    high_cardinality_threshold: int,
    extract_datetime: bool,
    datetime_features: list[str],
    scale_numeric: bool,
    scaling_method: Literal["standard", "minmax", "robust", "quantile"],
    select_features: bool,
    selection_method: Literal["mutual_info", "f_score", "rfe", "boruta"],
    n_features_to_select: int | None,
    selection_threshold: float,
) -> dict[str, Any]:
    """Return engineered dataframe and metadata. Intentionally lightweight and dependency-minimal."""

    df = pd.DataFrame(rows)
    original_features = list(df.columns)

    y = None
    task: Literal["classification", "regression"] | None = None
    if target and target in df.columns:
        y = df[target]
        task = _infer_task_from_target(y)

    transformations: dict[str, str] = {}
    encoding_mappings: dict[str, dict[str, Any]] = {}

    # datetime feature extraction
    if extract_datetime:
        datetime_cols = [c for c in df.columns if c != target and ("date" in c.lower() or "time" in c.lower())]
        for c in datetime_cols:
            try:
                df = _extract_datetime_features(df, c, datetime_features)
                transformations[c] = "datetime_extract"
            except Exception:
                continue

    # categorize columns
    numeric_cols = [c for c in df.columns if c != target and pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in df.columns if c != target and c not in numeric_cols]

    # categorical encoding
    if encode_categorical and categorical_cols:
        for c in list(categorical_cols):
            series = df[c]
            nunique = int(series.nunique(dropna=True))
            if handle_high_cardinality and nunique >= high_cardinality_threshold and categorical_method == "onehot":
                # fall back to frequency encoding to avoid explosion
                enc, mapping = _frequency_encode(series)
                new_c = f"{c}__freq"
                df[new_c] = enc
                transformations[c] = "frequency_encoding(high_cardinality_fallback)"
                encoding_mappings[c] = mapping
                df = df.drop(columns=[c])
                continue

            if categorical_method == "frequency":
                enc, mapping = _frequency_encode(series)
                new_c = f"{c}__freq"
                df[new_c] = enc
                transformations[c] = "frequency_encoding"
                encoding_mappings[c] = mapping
                df = df.drop(columns=[c])
            elif categorical_method == "target":
                if y is None or task is None:
                    # cannot do supervised encoding without target
                    enc, mapping = _frequency_encode(series)
                    new_c = f"{c}__freq"
                    df[new_c] = enc
                    transformations[c] = "frequency_encoding(fallback_no_target)"
                    encoding_mappings[c] = mapping
                    df = df.drop(columns=[c])
                else:
                    enc, mapping = _target_encode(series, y, task)
                    new_c = f"{c}__te"
                    df[new_c] = enc
                    transformations[c] = "target_encoding"
                    encoding_mappings[c] = mapping
                    df = df.drop(columns=[c])
            elif categorical_method == "ordinal":
                mapping = {k: i for i, k in enumerate(series.fillna("<NA>").astype(str).unique().tolist())}
                new_c = f"{c}__ord"
                df[new_c] = series.fillna("<NA>").astype(str).map(mapping).astype(int)
                transformations[c] = "ordinal_encoding"
                encoding_mappings[c] = mapping
                df = df.drop(columns=[c])
            else:
                # onehot
                dummies = pd.get_dummies(series, prefix=c, dummy_na=True)
                for col in dummies.columns:
                    transformations[col] = f"one_hot({c})"
                df = pd.concat([df.drop(columns=[c]), dummies], axis=1)
                transformations[c] = "one_hot"

    # recompute numeric cols after encoding
    feature_cols = [c for c in df.columns if c != target]
    numeric_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(df[c])]

    # scaling
    if scale_numeric:
        df, scale_info = _scale_numeric(df, numeric_cols, scaling_method)
        for c in scale_info.get("columns", []):
            transformations[c] = f"scale({scaling_method})"

    # interactions (numeric only)
    generated_features: list[str] = []
    if generate_interactions and len(numeric_cols) >= 2:
        pairs = []
        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                pairs.append((numeric_cols[i], numeric_cols[j]))
        pairs = pairs[: max_interactions]
        for a, b in pairs:
            new_c = f"{a}__x__{b}"
            df[new_c] = pd.to_numeric(df[a], errors="coerce").fillna(0.0) * pd.to_numeric(df[b], errors="coerce").fillna(0.0)
            generated_features.append(new_c)
            transformations[new_c] = "interaction"

    # Feature selection
    dropped_features: list[str] = []
    selected_features = [c for c in df.columns if c != target]
    feature_scores: dict[str, float] | None = None

    if select_features and len(selected_features) > 1:
        X = df[selected_features].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)

        # remove near-constant
        try:
            vt = VarianceThreshold(threshold=1e-12)
            X_v = vt.fit_transform(X)
            kept_idx = vt.get_support(indices=True)
            kept = [selected_features[i] for i in kept_idx]
            removed = [c for c in selected_features if c not in kept]
            dropped_features.extend(removed)
            selected_features = kept
            X = X_v
            for c in removed:
                transformations[c] = "dropped(near_constant)"
        except Exception:
            pass

        if y is not None and len(selected_features) > 1 and selection_method == "mutual_info":
            y_arr = y
            if task == "classification":
                y_arr = y_arr.fillna("<NA>").astype(str)
                scores = mutual_info_classif(X, y_arr, random_state=42)
            else:
                y_num = pd.to_numeric(y_arr, errors="coerce").fillna(0.0).to_numpy(dtype=float)
                scores = mutual_info_regression(X, y_num, random_state=42)
            feature_scores = {f: float(s) for f, s in zip(selected_features, scores, strict=False)}
            # filter by threshold and optionally top-N
            kept = [f for f, s in feature_scores.items() if s >= selection_threshold]
            if n_features_to_select:
                kept = sorted(kept, key=lambda f: feature_scores.get(f, 0.0), reverse=True)[:n_features_to_select]
            removed = [f for f in selected_features if f not in set(kept)]
            dropped_features.extend(removed)
            selected_features = kept

    # final dataframe contains target if present
    final_cols = selected_features + ([target] if target and target in df.columns else [])
    df_out = df[final_cols].copy()

    return {
        "df": df_out,
        "original_features": original_features,
        "generated_features": generated_features,
        "selected_features": selected_features,
        "dropped_features": dropped_features,
        "transformations": transformations,
        "encoding_mappings": encoding_mappings,
        "feature_scores": feature_scores,
    }


def validate_rows(rows: list[dict[str, Any]], target: str | None = None) -> dict[str, Any]:
    df = pd.DataFrame(rows)
    issues: list[str] = []

    if df.empty:
        return {"ok": False, "issues": ["Empty dataset"], "summary": {}}

    # duplicates
    dup = int(df.duplicated().sum())
    if dup:
        issues.append(f"{dup} duplicate rows")

    # missingness
    null_counts = df.isnull().sum().sort_values(ascending=False)
    top_nulls = {str(k): int(v) for k, v in null_counts.head(20).to_dict().items() if int(v) > 0}

    if target and target in df.columns:
        if df[target].isnull().any():
            issues.append("Target contains nulls")

    # quasi-constant columns
    quasi_constant = []
    for c in df.columns:
        vc = df[c].value_counts(dropna=False)
        if len(vc) == 0:
            continue
        top_frac = float(vc.iloc[0]) / max(1, len(df))
        if top_frac >= 0.999:
            quasi_constant.append(c)

    summary = {
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "duplicate_rows": dup,
        "top_null_counts": top_nulls,
        "quasi_constant_columns": quasi_constant[:50],
        "dtypes": {c: str(df[c].dtype) for c in df.columns[:200]},
    }

    return {"ok": len(issues) == 0, "issues": issues, "summary": summary}
