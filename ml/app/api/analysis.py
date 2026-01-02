from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from app.core.automl import infer_problem
from app.schemas.legacy import ColumnProfile, DataProfileRequest, DataProfileResponse

router = APIRouter(tags=["analysis"])


@router.post("/profile", response_model=DataProfileResponse)
def profile_data(req: DataProfileRequest):
    """Profile a dataset to understand its structure and statistics."""
    df = pd.DataFrame(req.rows)
    columns: list[ColumnProfile] = []

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = int(series.isnull().sum())
        unique_count = int(series.nunique())

        profile = ColumnProfile(
            name=col,
            dtype=dtype,
            null_count=null_count,
            null_pct=round(null_count / len(df) * 100, 2) if len(df) else 0.0,
            unique_count=unique_count,
            unique_pct=round(unique_count / len(df) * 100, 2) if len(df) else 0.0,
            sample_values=series.dropna().head(5).tolist(),
        )

        if pd.api.types.is_numeric_dtype(series):
            profile.min = float(series.min()) if not series.isnull().all() else None
            profile.max = float(series.max()) if not series.isnull().all() else None
            profile.mean = float(series.mean()) if not series.isnull().all() else None
            profile.std = float(series.std()) if not series.isnull().all() else None
            profile.median = float(series.median()) if not series.isnull().all() else None
        else:
            mode_val = series.mode()
            profile.mode = mode_val.iloc[0] if len(mode_val) > 0 else None

        columns.append(profile)

    target_dist = None
    suggested = None
    if req.target and req.target in df.columns:
        target_series = df[req.target]
        target_dist = target_series.value_counts().head(20).to_dict()
        target_dist = {str(k): int(v) for k, v in target_dist.items()}
        suggested = infer_problem(target_series)

    return DataProfileResponse(
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        target_distribution=target_dist,
        suggested_problem=suggested,
    )
