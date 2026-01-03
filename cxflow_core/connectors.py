"""Integration connectors for all CXFlow services."""

import json
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


class CxSpaceLLMConnector(ServiceConnector):
    """Connector for CxSpaceLLM - GitHub Space Model."""
    
    # Constants for data truncation
    MAX_DATA_LENGTH = 1000
    TRUNCATION_SUFFIX_LENGTH = 3
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus, config: "CXFlowConfig | None" = None):
        super().__init__("cxspacellm", registry, event_bus)
        self.config = config
        
        # Get configuration from config object or environment
        if config:
            self.base_url = config.cxspacellm_base_url
            self.token = config.cxspacellm_token
            self.model = config.cxspacellm_model
            self.timeout = config.cxspacellm_timeout
            self.enabled = config.cxspacellm_enabled
        else:
            import os
            self.base_url = os.getenv("CXSPACELLM_BASE_URL", "https://models.inference.ai.azure.com")
            self.token = os.getenv("CXSPACELLM_TOKEN", "")
            self.model = os.getenv("CXSPACELLM_MODEL", "CxSpaceLLM")
            self.timeout = int(os.getenv("CXSPACELLM_TIMEOUT_SECONDS", "60"))
            self.enabled = os.getenv("CXSPACELLM_ENABLED", "true").lower() == "true"
    
    async def call(self, endpoint: str, method: str = "GET", **kwargs) -> Any:
        """Call CxSpaceLLM endpoint."""
        if not self.enabled:
            raise RuntimeError("CxSpaceLLM is not enabled")
        
        if not self.token:
            raise RuntimeError("CxSpaceLLM token not configured")
        
        full_url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = "application/json"
        
        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            response = await client.request(method, full_url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    def _extract_content_from_response(response: dict[str, Any]) -> str:
        """
        Safely extract content from API response.
        
        Args:
            response: API response dictionary
            
        Returns:
            Content string, or empty string if not found
        """
        choices = response.get("choices", [])
        if choices and len(choices) > 0:
            return choices[0].get("message", {}).get("content", "")
        return ""
    
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False
    ) -> dict[str, Any]:
        """
        Generate chat completion using CxSpaceLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            Chat completion response
        """
        await self.event_bus.publish(Event(
            type="cxspacellm.chat.start",
            source="cxspacellm_connector",
            payload={"messages": len(messages), "model": self.model}
        ))
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        result = await self.call("chat/completions", method="POST", json=payload)
        
        await self.event_bus.publish(Event(
            type="cxspacellm.chat.complete",
            source="cxspacellm_connector",
            payload={"model": self.model, "usage": result.get("usage", {})}
        ))
        
        return result
    
    async def analyze_data(self, data: dict[str, Any], prompt: str | None = None) -> dict[str, Any]:
        """
        Analyze data using CxSpaceLLM.
        
        Args:
            data: Data to analyze
            prompt: Optional custom prompt for analysis
            
        Returns:
            Analysis results
        """
        default_prompt = f"Analyze the following data and provide insights:\n\n{json.dumps(data, indent=2)}"
        messages = [
            {"role": "system", "content": "You are a helpful data analysis assistant."},
            {"role": "user", "content": prompt or default_prompt}
        ]
        
        return await self.chat_completion(messages)
    
    async def enrich_dataflow(self, dataflow_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich dataflow with AI-generated insights from CxSpaceLLM.
        
        Args:
            dataflow_data: Dataflow data to enrich
            
        Returns:
            Enriched dataflow data with AI insights
        """
        await self.event_bus.publish(Event(
            type="cxspacellm.enrich.start",
            source="cxspacellm_connector",
            payload={"dataflow_id": dataflow_data.get("id")}
        ))
        
        # Extract key information for analysis
        # Safely truncate JSON data while preserving structure
        data_str = json.dumps(dataflow_data.get('data', {}), indent=2)
        if len(data_str) > self.MAX_DATA_LENGTH:
            data_str = data_str[:self.MAX_DATA_LENGTH - self.TRUNCATION_SUFFIX_LENGTH] + "..."
        
        prompt = f"""Analyze this dataflow and provide insights:
        
Dataflow Type: {dataflow_data.get('type', 'unknown')}
Status: {dataflow_data.get('status', 'unknown')}
Data: {data_str}

Provide:
1. Summary of the dataflow
2. Key insights from the data
3. Potential issues or recommendations
4. Suggested next actions
"""
        
        messages = [
            {"role": "system", "content": "You are an expert data engineer analyzing dataflows."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages, temperature=0.3)
        
        # Extract AI insights from response using helper method
        insights = self._extract_content_from_response(response)
        
        # Enrich the dataflow data
        enriched_data = dataflow_data.copy()
        enriched_data["ai_insights"] = insights
        enriched_data["enriched_by"] = "CxSpaceLLM"
        enriched_data["enriched_at"] = response.get("created")
        
        await self.event_bus.publish(Event(
            type="cxspacellm.enrich.complete",
            source="cxspacellm_connector",
            payload={"dataflow_id": dataflow_data.get("id")}
        ))
        
        return enriched_data
