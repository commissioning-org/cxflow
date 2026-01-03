"""Unified configuration management for all CXFlow services."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ServiceConfig:
    """Configuration for a single service."""
    
    name: str
    host: str
    port: int
    enabled: bool = True
    health_endpoint: str = "/health"
    timeout: int = 30
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CXFlowConfig:
    """
    Central configuration for all CXFlow services.
    
    Reads from environment variables and provides a unified interface
    for all components.
    """
    
    # Base directories
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    models_dir: Path = field(default_factory=lambda: Path("/models"))
    data_dir: Path = field(default_factory=lambda: Path("/data"))
    
    # ML Service
    ml_service: ServiceConfig = field(default_factory=lambda: ServiceConfig(
        name="ml",
        host=os.getenv("ML_HOST", "ml"),
        port=int(os.getenv("ML_PORT", "8000")),
        enabled=os.getenv("ML_ENABLED", "true").lower() == "true",
    ))
    
    # Webhook Engine
    webhook_service: ServiceConfig = field(default_factory=lambda: ServiceConfig(
        name="webhook_engine",
        host=os.getenv("WEBHOOK_HOST", "localhost"),
        port=int(os.getenv("WEBHOOK_PORT", "8001")),
        enabled=os.getenv("WEBHOOK_ENABLED", "true").lower() == "true",
    ))
    
    # Research Agent
    research_agent: ServiceConfig = field(default_factory=lambda: ServiceConfig(
        name="research_agent",
        host=os.getenv("RESEARCH_HOST", "localhost"),
        port=int(os.getenv("RESEARCH_PORT", "8002")),
        enabled=os.getenv("RESEARCH_ENABLED", "true").lower() == "true",
    ))
    
    # JupyterBook
    jupyterbook: ServiceConfig = field(default_factory=lambda: ServiceConfig(
        name="jupyterbook",
        host=os.getenv("JUPYTERBOOK_HOST", "localhost"),
        port=int(os.getenv("JUPYTERBOOK_PORT", "8003")),
        enabled=os.getenv("JUPYTERBOOK_ENABLED", "true").lower() == "true",
    ))
    
    # Superset
    superset: ServiceConfig = field(default_factory=lambda: ServiceConfig(
        name="superset",
        host=os.getenv("SUPERSET_HOST", "localhost"),
        port=int(os.getenv("SUPERSET_PORT", "8088")),
        enabled=os.getenv("SUPERSET_ENABLED", "false").lower() == "true",
    ))
    
    # Event Bus
    event_bus_enabled: bool = field(
        default_factory=lambda: os.getenv("EVENT_BUS_ENABLED", "true").lower() == "true"
    )
    event_bus_backend: str = field(
        default_factory=lambda: os.getenv("EVENT_BUS_BACKEND", "memory")
    )
    
    # API Gateway
    gateway_port: int = field(
        default_factory=lambda: int(os.getenv("GATEWAY_PORT", "8100"))
    )
    gateway_enabled: bool = field(
        default_factory=lambda: os.getenv("GATEWAY_ENABLED", "true").lower() == "true"
    )
    
    # CxSpaceLLM Configuration
    cxspacellm_enabled: bool = field(
        default_factory=lambda: os.getenv("CXSPACELLM_ENABLED", "true").lower() == "true"
    )
    cxspacellm_model: str = field(
        default_factory=lambda: os.getenv("CXSPACELLM_MODEL", "CxSpaceLLM")
    )
    cxspacellm_base_url: str = field(
        default_factory=lambda: os.getenv("CXSPACELLM_BASE_URL", "https://models.inference.ai.azure.com")
    )
    cxspacellm_token: str = field(
        default_factory=lambda: os.getenv("CXSPACELLM_TOKEN", "")
    )
    cxspacellm_timeout: int = field(
        default_factory=lambda: int(os.getenv("CXSPACELLM_TIMEOUT_SECONDS", "60"))
    )
    
    def get_service_url(self, service_name: str) -> str:
        """Get the full URL for a service."""
        service = getattr(self, f"{service_name}_service", None)
        if not service:
            raise ValueError(f"Unknown service: {service_name}")
        return f"http://{service.host}:{service.port}"
    
    def get_all_services(self) -> list[ServiceConfig]:
        """Get all configured services."""
        return [
            self.ml_service,
            self.webhook_service,
            self.research_agent,
            self.jupyterbook,
            self.superset,
        ]
    
    def get_enabled_services(self) -> list[ServiceConfig]:
        """Get only enabled services."""
        return [s for s in self.get_all_services() if s.enabled]
