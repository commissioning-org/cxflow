"""API routers for the ML service."""

from app.api.experiments import router as experiments_router
from app.api.analysis import router as analysis_router
from app.api.feature_engineering import router as feature_engineering_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.models import router as models_router
from app.api.prediction import router as prediction_router
from app.api.superset import router as superset_router
from app.api.search import router as search_router
from app.api.tfos import router as tfos_router
from app.api.timeseries import router as timeseries_router
from app.api.training import router as training_router

__all__ = [
	"health_router",
	"training_router",
	"prediction_router",
	"models_router",
	"experiments_router",
	"timeseries_router",
	"metrics_router",
	"analysis_router",
	"feature_engineering_router",
	"tfos_router",
	"superset_router",
	"search_router",
]
