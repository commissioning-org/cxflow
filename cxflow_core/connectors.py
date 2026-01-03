"""Integration connectors for all CXFlow services."""

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .events import Event, EventBus
from .registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ServiceConnector(ABC):
    """Base class for service connectors."""
    
    def __init__(self, service_name: str, registry: ServiceRegistry, event_bus: EventBus):
        self.service_name = service_name
        self.registry = registry
        self.event_bus = event_bus
    
    def get_service_url(self) -> str | None:
        """Get service URL from registry."""
        return self.registry.find_service(self.service_name)
    
    @abstractmethod
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call service endpoint."""
        pass


class MLServiceConnector(ServiceConnector):
    """Connector for ML Service."""
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        super().__init__("ml", registry, event_bus)
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call ML service endpoint."""
        url = self.get_service_url()
        if not url:
            raise RuntimeError("ML service not available")
        
        full_url = f"{url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def train(self, data: dict[str, Any]) -> dict[str, Any]:
        """Train a model."""
        await self.event_bus.publish(Event(
            type="ml.train.start",
            source="ml_connector",
            payload={"rows": len(data.get("rows", []))}
        ))
        
        result = await self.call("train", method="POST", json=data)
        
        await self.event_bus.publish(Event(
            type="ml.train.complete",
            source="ml_connector",
            payload={"model_id": result.get("model_id")}
        ))
        
        return result
    
    async def predict(self, model_id: str, rows: list[dict]) -> dict[str, Any]:
        """Make predictions."""
        return await self.call("predict", method="POST", json={
            "model_id": model_id,
            "rows": rows,
        })
    
    async def list_models(self) -> dict[str, Any]:
        """List all models."""
        return await self.call("models")


class WebhookConnector(ServiceConnector):
    """Connector for Webhook Engine."""
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        super().__init__("webhook_engine", registry, event_bus)
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call webhook engine endpoint."""
        url = self.get_service_url()
        if not url:
            raise RuntimeError("Webhook engine not available")
        
        full_url = f"{url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def send_webhook(self, target_url: str, payload: dict) -> dict[str, Any]:
        """Send a webhook."""
        await self.event_bus.publish(Event(
            type="webhook.send",
            source="webhook_connector",
            payload={"url": target_url}
        ))
        
        return await self.call("send", method="POST", json={
            "url": target_url,
            "payload": payload,
        })


class ResearchAgentConnector(ServiceConnector):
    """Connector for Research Agent."""
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        super().__init__("research_agent", registry, event_bus)
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call research agent endpoint."""
        url = self.get_service_url()
        if not url:
            raise RuntimeError("Research agent not available")
        
        full_url = f"{url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def analyze_repo(self, repo: str) -> dict[str, Any]:
        """Analyze a repository."""
        await self.event_bus.publish(Event(
            type="research.analyze.start",
            source="research_connector",
            payload={"repo": repo}
        ))
        
        result = await self.call("analyze", method="POST", json={"repo": repo})
        
        await self.event_bus.publish(Event(
            type="research.analyze.complete",
            source="research_connector",
            payload={"repo": repo}
        ))
        
        return result


class JupyterBookConnector(ServiceConnector):
    """Connector for JupyterBook."""
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        super().__init__("jupyterbook", registry, event_bus)
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call jupyterbook endpoint."""
        url = self.get_service_url()
        if not url:
            raise RuntimeError("JupyterBook not available")
        
        full_url = f"{url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def build_book(self, config: dict[str, Any]) -> dict[str, Any]:
        """Build a Jupyter Book."""
        await self.event_bus.publish(Event(
            type="jupyterbook.build.start",
            source="jupyterbook_connector",
            payload={"title": config.get("title")}
        ))
        
        result = await self.call("build", method="POST", json=config)
        
        await self.event_bus.publish(Event(
            type="jupyterbook.build.complete",
            source="jupyterbook_connector",
            payload={"book_id": result.get("book_id")}
        ))
        
        return result


class SupersetConnector(ServiceConnector):
    """Connector for Superset."""
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        super().__init__("superset", registry, event_bus)
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call superset endpoint."""
        url = self.get_service_url()
        if not url:
            raise RuntimeError("Superset not available")
        
        full_url = f"{url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def create_dashboard(self, config: dict[str, Any]) -> dict[str, Any]:
        """Create a Superset dashboard."""
        await self.event_bus.publish(Event(
            type="superset.dashboard.create",
            source="superset_connector",
            payload={"title": config.get("title")}
        ))
        
        return await self.call("api/v1/dashboard", method="POST", json=config)
