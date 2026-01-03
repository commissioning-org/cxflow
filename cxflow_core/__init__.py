"""
CXFlow Core Integration Module.

Central integration hub that wires together all CXFlow components:
- ML Service (AutoML, TFoS, experiments)
- Ingestion Pipeline (data validation, transformation, routing)
- Webhook Engine (event distribution, circuit breaker, retry)
- Research Agent (repository analysis, code search)
- JupyterBook (documentation generation, cross-references)
- Superset (BI dashboards, data visualization)
- Workflows (enhanced automation, macros)
- CxSpaceLLM (GitHub Space AI model integration for dataflow enrichment)
"""

__version__ = "2.0.0"

from .config import CXFlowConfig, ServiceConfig
from .registry import ServiceRegistry, ServiceStatus, ServiceInfo
from .gateway import APIGateway
from .events import EventBus, Event, EventPriority
from .health import HealthMonitor, HealthCheckResult
from .connectors import (
    MLServiceConnector,
    WebhookConnector,
    ResearchAgentConnector,
    JupyterBookConnector,
    SupersetConnector,
    CxSpaceLLMConnector,
)
from .workflows import WorkflowOrchestrator, create_orchestrator

__all__ = [
    # Core config
    "CXFlowConfig",
    "ServiceConfig",
    # Registry
    "ServiceRegistry",
    "ServiceStatus",
    "ServiceInfo",
    # Gateway
    "APIGateway",
    # Events
    "EventBus",
    "Event",
    "EventPriority",
    # Health
    "HealthMonitor",
    "HealthCheckResult",
    # Connectors
    "MLServiceConnector",
    "WebhookConnector",
    "ResearchAgentConnector",
    "JupyterBookConnector",
    "SupersetConnector",
    "CxSpaceLLMConnector",
    # Workflows
    "WorkflowOrchestrator",
    "create_orchestrator",
]
