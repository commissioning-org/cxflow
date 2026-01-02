from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.timeseries import forecast_naive, train_naive
from app.schemas.legacy import TimeSeriesForecastRequest, TimeSeriesTrainRequest, TimeSeriesTrainResponse

router = APIRouter(tags=["timeseries"])


@router.post("/timeseries/train", response_model=TimeSeriesTrainResponse)
def train_timeseries(req: TimeSeriesTrainRequest):
    try:
        meta = train_naive(
            rows=req.rows,
            target=req.target,
            datetime_col=req.datetime_col,
            frequency=req.frequency,
            seasonality_period=req.seasonality_period,
            model_name=req.model_name,
            tags=req.tags,
        )
        return TimeSeriesTrainResponse(
            model_id=meta["model_id"],
            model_name=meta.get("model_name"),
            target=meta["target"],
            datetime_col=meta["datetime_col"],
            frequency=meta["frequency"],
            seasonality_period=meta.get("seasonality_period"),
            row_count=meta["row_count"],
            created_at=meta["created_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeseries/forecast")
def forecast_timeseries(req: TimeSeriesForecastRequest):
    try:
        return forecast_naive(req.model_id, req.horizon)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Time series model not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
