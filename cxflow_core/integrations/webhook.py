"""Integration of webhook engine with CXFlow Core."""

import logging
from typing import Any

from webhook_engine.engine import WebhookEngine
from webhook_engine.config import WebhookConfig, WebhookEndpoint

logger = logging.getLogger(__name__)


class WebhookEngineIntegration:
    """
    Integration layer for webhook engine with CXFlow Core.
    
    Connects webhook engine to:
    - Event bus for event-driven webhooks
    - Service registry for health tracking
    - ML service for model notifications
    - Ingestion for data flow notifications
    """
    
    def __init__(
        self,
        webhook_engine: WebhookEngine,
        event_bus,
        registry,
    ):
        self.engine = webhook_engine
        self.event_bus = event_bus
        self.registry = registry
        
        # Register webhook engine
        self.registry.register(
            name="webhook_engine",
            url="http://localhost:8001",
            metadata={"engine": "webhook_engine"},
        )
        
        # Setup event subscriptions
        self._setup_subscriptions()
    
    def _setup_subscriptions(self) -> None:
        """Setup event subscriptions."""
        
        # ML events
        self.event_bus.subscribe("ml.train.complete", self._on_ml_train_complete)
        self.event_bus.subscribe("ml.predict.complete", self._on_ml_predict_complete)
        
        # Ingestion events
        self.event_bus.subscribe("ingestion.complete", self._on_ingestion_complete)
        self.event_bus.subscribe("ingestion.failed", self._on_ingestion_failed)
        
        # Workflow events
        self.event_bus.subscribe("workflow.*", self._on_workflow_event)
        
        # Research events
        self.event_bus.subscribe("research.analyze.complete", self._on_research_complete)
        
        # CxSpaceLLM events
        self.event_bus.subscribe("cxspacellm.chat.complete", self._on_cxspacellm_event)
        self.event_bus.subscribe("cxspacellm.enrich.complete", self._on_cxspacellm_event)
    
    async def _on_ml_train_complete(self, event) -> None:
        """Handle ML training completion."""
        logger.info(f"ML training complete event: {event.id}")
        
        # Find webhook endpoints tagged for ML events
        endpoints = self._get_endpoints_for_event("ml.train")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": "ml.train.complete",
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent ML train webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_ml_predict_complete(self, event) -> None:
        """Handle ML prediction completion."""
        logger.info(f"ML prediction complete event: {event.id}")
        
        endpoints = self._get_endpoints_for_event("ml.predict")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": "ml.predict.complete",
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent ML predict webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_ingestion_complete(self, event) -> None:
        """Handle ingestion completion."""
        logger.info(f"Ingestion complete event: {event.id}")
        
        endpoints = self._get_endpoints_for_event("ingestion")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": "ingestion.complete",
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent ingestion webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_ingestion_failed(self, event) -> None:
        """Handle ingestion failure."""
        logger.warning(f"Ingestion failed event: {event.id}")
        
        endpoints = self._get_endpoints_for_event("ingestion.failed")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": "ingestion.failed",
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent ingestion failure webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_workflow_event(self, event) -> None:
        """Handle workflow events."""
        logger.info(f"Workflow event: {event.type}")
        
        endpoints = self._get_endpoints_for_event("workflow")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": event.type,
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent workflow webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_research_complete(self, event) -> None:
        """Handle research completion."""
        logger.info(f"Research complete event: {event.id}")
        
        endpoints = self._get_endpoints_for_event("research")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": "research.analyze.complete",
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent research webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    async def _on_cxspacellm_event(self, event) -> None:
        """Handle CxSpaceLLM events."""
        logger.info(f"CxSpaceLLM event: {event.type}")
        
        endpoints = self._get_endpoints_for_event("cxspacellm")
        
        for endpoint in endpoints:
            try:
                payload = {
                    "event_type": event.type,
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.payload,
                }
                
                await self.engine.send(endpoint, payload)
                logger.info(f"Sent CxSpaceLLM webhook to {endpoint}")
            
            except Exception as e:
                logger.error(f"Failed to send webhook to {endpoint}: {e}")
    
    def _get_endpoints_for_event(self, event_prefix: str) -> list[str]:
        """
        Get webhook endpoints that should receive events with given prefix.
        
        This can be configured via tags or configuration.
        For now, returns all endpoints.
        """
        # TODO: Implement endpoint filtering based on tags/config
        # For now, return all configured endpoints
        return [ep.name for ep in self.engine.config.endpoints]
    
    def add_endpoint(
        self,
        name: str,
        url: str,
        events: list[str] | None = None,
        **kwargs
    ) -> None:
        """
        Add a webhook endpoint.
        
        Args:
            name: Endpoint name
            url: Webhook URL
            events: List of event prefixes to subscribe to
            **kwargs: Additional WebhookEndpoint parameters
        """
        endpoint = WebhookEndpoint(
            name=name,
            url=url,
            **kwargs
        )
        self.engine.add_endpoint(endpoint)
        logger.info(f"Added webhook endpoint: {name} -> {url}")
    
    async def health_check(self) -> dict[str, Any]:
        """Get health status."""
        health = self.engine._health.get_status()
        
        return {
            "status": health.status.value,
            "endpoints": len(self.engine.config.endpoints),
            "queue_size": self.engine._queue.size() if self.engine._queue else 0,
            "metrics": self.engine._metrics.to_dict() if self.engine._metrics else {},
        }


def create_webhook_integration(
    event_bus,
    registry,
    config: WebhookConfig | None = None,
):
    """
    Create webhook engine integration.
    
    Args:
        event_bus: Event bus
        registry: Service registry
        config: Optional webhook config
        
    Returns:
        WebhookEngineIntegration instance
    """
    engine = WebhookEngine(config=config)
    integration = WebhookEngineIntegration(engine, event_bus, registry)
    
    # Update registry status
    from cxflow_core.registry import ServiceStatus
    registry.update_status("webhook_engine", ServiceStatus.HEALTHY)
    
    return integration
