from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.requests import DataProfileRequest, FeatureEngineeringRequest
from app.models.responses import FeatureEngineeringResponse
from app.services.feature_engineering import engineer_features, validate_rows

router = APIRouter(tags=["feature-engineering"])


@router.post("/features/engineer", response_model=FeatureEngineeringResponse)
def features_engineer(req: FeatureEngineeringRequest):
    """Create engineered features from raw rows."""
    try:
        result = engineer_features(
            rows=req.rows,
            target=req.target,
            generate_interactions=req.generate_interactions,
            max_interactions=req.max_interactions,
            encode_categorical=req.encode_categorical,
            categorical_method=req.categorical_method,
            handle_high_cardinality=req.handle_high_cardinality,
            high_cardinality_threshold=req.high_cardinality_threshold,
            extract_datetime=req.extract_datetime,
            datetime_features=req.datetime_features,
            scale_numeric=req.scale_numeric,
            scaling_method=req.scaling_method,
            select_features=req.select_features,
            selection_method=req.selection_method,
            n_features_to_select=req.n_features_to_select,
            selection_threshold=req.selection_threshold,
        )

        df = result["df"]
        sample_rows = df.head(25).to_dict(orient="records")

        original_features = [f for f in result["original_features"] if f != req.target]

        return FeatureEngineeringResponse(
            original_features=original_features,
            generated_features=result["generated_features"],
            selected_features=result["selected_features"],
            dropped_features=result["dropped_features"],
            transformations=result["transformations"],
            encoding_mappings=result.get("encoding_mappings") or None,
            feature_scores=result.get("feature_scores"),
            total_features_before=len(original_features),
            total_features_after=len(result["selected_features"]),
            sample_rows=sample_rows,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/validate")
def data_validate(req: DataProfileRequest):
    """Validate rows for common issues (nulls, duplicates, quasi-constant columns)."""
    try:
        return validate_rows(req.rows, target=req.target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
