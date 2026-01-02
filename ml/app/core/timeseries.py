from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import joblib
import pandas as pd

from app.core.artifacts import ts_artifacts


def train_naive(rows: list[dict[str, Any]], target: str, datetime_col: str, frequency: str, seasonality_period: int | None,
                model_name: str | None, tags: list[str]) -> dict[str, Any]:
    df = pd.DataFrame(rows)
    if datetime_col not in df.columns:
        raise ValueError(f"datetime_col '{datetime_col}' not found")
    if target not in df.columns:
        raise ValueError(f"target '{target}' not found")

    df[datetime_col] = pd.to_datetime(df[datetime_col], utc=True, errors="coerce")
    df = df.dropna(subset=[datetime_col, target]).sort_values(datetime_col)
    if df.empty:
        raise ValueError("No valid rows after parsing/cleaning")

    y = pd.to_numeric(df[target], errors="coerce")
    df = df.assign(_y=y).dropna(subset=["_y"])
    if df.empty:
        raise ValueError("Target column must be numeric for forecasting")

    values = df["_y"].astype(float).tolist()
    if len(values) < 2:
        raise ValueError("Need at least 2 numeric observations")

    model_obj = {
        "kind": "seasonal_naive" if seasonality_period else "naive",
        "datetime_col": datetime_col,
        "target": target,
        "frequency": frequency,
        "seasonality_period": seasonality_period,
        "values": values[-5000:],
        "last_timestamp": df[datetime_col].iloc[-1].to_pydatetime().replace(tzinfo=timezone.utc).isoformat(),
    }

    model_id = str(uuid.uuid4())
    art = ts_artifacts(model_id)
    joblib.dump(model_obj, art.model_path)

    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "model_id": model_id,
        "model_name": model_name,
        "datetime_col": datetime_col,
        "target": target,
        "frequency": frequency,
        "seasonality_period": seasonality_period,
        "row_count": int(len(df)),
        "created_at": created_at,
        "tags": tags,
    }
    art.meta_path.write_text(json.dumps(meta, indent=2))
    return meta


def forecast_naive(model_id: str, horizon: int) -> dict[str, Any]:
    art = ts_artifacts(model_id)
    if not art.model_path.exists() or not art.meta_path.exists():
        raise FileNotFoundError("Time series model not found")

    model_obj = joblib.load(art.model_path)
    meta = json.loads(art.meta_path.read_text())

    freq = model_obj.get("frequency") or "D"
    season = model_obj.get("seasonality_period")
    values: list[float] = list(model_obj.get("values") or [])
    if not values:
        raise ValueError("Corrupt time series artifact (missing values)")

    last_ts = pd.to_datetime(model_obj.get("last_timestamp"), utc=True)
    future_index = pd.date_range(start=last_ts, periods=horizon + 1, freq=freq, tz="UTC")[1:]

    preds: list[float] = []
    if season and int(season) > 1 and len(values) >= int(season):
        base = values[-int(season) :]
        for i in range(horizon):
            preds.append(float(base[i % int(season)]))
    else:
        last_val = float(values[-1])
        preds = [last_val for _ in range(horizon)]

    forecasts = [{"timestamp": ts.isoformat(), "forecast": yhat} for ts, yhat in zip(future_index, preds, strict=False)]

    return {
        "model_id": model_id,
        "target": meta.get("target"),
        "datetime_col": meta.get("datetime_col"),
        "frequency": meta.get("frequency"),
        "horizon": horizon,
        "forecasts": forecasts,
    }
