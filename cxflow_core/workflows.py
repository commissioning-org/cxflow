"""
Workflow integrations - Connect workflows with all services.
"""

import asyncio
import logging
from typing import Any

from cxflow_core.connectors import (
    JupyterBookConnector,
    MLServiceConnector,
    ResearchAgentConnector,
    SupersetConnector,
    WebhookConnector,
)
from cxflow_core.events import Event, EventBus, EventPriority
from cxflow_core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Orchestrate workflows across all services.
    
    Coordinates:
    - Data ingestion -> ML training
    - ML predictions -> Webhook notifications
    - Research analysis -> Documentation generation
    - Model results -> Dashboard creation
    """
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        
        # Initialize connectors
        self.ml = MLServiceConnector(registry, event_bus)
        self.webhook = WebhookConnector(registry, event_bus)
        self.research = ResearchAgentConnector(registry, event_bus)
        self.jupyterbook = JupyterBookConnector(registry, event_bus)
        self.superset = SupersetConnector(registry, event_bus)
        
        # Subscribe to events
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for workflow coordination."""
        
        # When ML training completes, send webhook
        self.event_bus.subscribe("ml.train.complete", self._on_ml_train_complete)
        
        # When research completes, generate docs
        self.event_bus.subscribe("research.analyze.complete", self._on_research_complete)
        
        # When book builds, create dashboard
        self.event_bus.subscribe("jupyterbook.build.complete", self._on_book_complete)
    
    async def _on_ml_train_complete(self, event: Event) -> None:
        """Handle ML training completion."""
        model_id = event.payload.get("model_id")
        if model_id:
            logger.info(f"ML training completed for model: {model_id}")
            
            # Publish success event
            await self.event_bus.publish(Event(
                type="workflow.ml_complete",
                source="orchestrator",
                priority=EventPriority.HIGH,
                payload={"model_id": model_id}
            ))
    
    async def _on_research_complete(self, event: Event) -> None:
        """Handle research analysis completion."""
        repo = event.payload.get("repo")
        if repo:
            logger.info(f"Research completed for repo: {repo}")
            
            # Could trigger documentation generation
            await self.event_bus.publish(Event(
                type="workflow.research_complete",
                source="orchestrator",
                payload={"repo": repo}
            ))
    
    async def _on_book_complete(self, event: Event) -> None:
        """Handle Jupyter Book build completion."""
        book_id = event.payload.get("book_id")
        if book_id:
            logger.info(f"Book build completed: {book_id}")
    
    async def run_ml_workflow(
        self,
        data: dict[str, Any],
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Run complete ML workflow.
        
        Steps:
        1. Train model
        2. Optionally send webhook notification
        3. Return results
        """
        logger.info("Starting ML workflow")
        
        # Train model
        train_result = await self.ml.train(data)
        model_id = train_result["model_id"]
        
        # Send webhook if URL provided
        if webhook_url:
            try:
                await self.webhook.send_webhook(webhook_url, {
                    "event": "ml.train.complete",
                    "model_id": model_id,
                    "score": train_result.get("score"),
                })
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")
        
        return train_result
    
    async def run_research_workflow(
        self,
        repo: str,
        generate_docs: bool = True,
    ) -> dict[str, Any]:
        """
        Run research and documentation workflow.
        
        Steps:
        1. Analyze repository
        2. Generate documentation
        3. Return results
        """
        logger.info(f"Starting research workflow for {repo}")
        
        # Analyze repo
        analysis = await self.research.analyze_repo(repo)
        
        # Generate docs if requested
        if generate_docs:
            try:
                book_config = {
                    "title": f"Analysis of {repo}",
                    "content": analysis,
                }
                docs = await self.jupyterbook.build_book(book_config)
                analysis["documentation"] = docs
            except Exception as e:
                logger.error(f"Failed to generate docs: {e}")
        
        return analysis
    
    async def run_analytics_workflow(
        self,
        model_id: str,
        create_dashboard: bool = True,
    ) -> dict[str, Any]:
        """
        Run analytics and visualization workflow.
        
        Steps:
        1. Get model information
        2. Create Superset dashboard
        3. Return results
        """
        logger.info(f"Starting analytics workflow for model {model_id}")
        
        # Get model details
        models = await self.ml.list_models()
        model = next((m for m in models.get("models", []) if m.get("model_id") == model_id), None)
        
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        result = {"model": model}
        
        # Create dashboard if requested
        if create_dashboard:
            try:
                dashboard_config = {
                    "title": f"Model {model_id} Analytics",
                    "model_id": model_id,
                }
                dashboard = await self.superset.create_dashboard(dashboard_config)
                result["dashboard"] = dashboard
            except Exception as e:
                logger.error(f"Failed to create dashboard: {e}")
        
        return result


def create_orchestrator(registry: ServiceRegistry, event_bus: EventBus) -> WorkflowOrchestrator:
    """Create a workflow orchestrator."""
    return WorkflowOrchestrator(registry, event_bus)
