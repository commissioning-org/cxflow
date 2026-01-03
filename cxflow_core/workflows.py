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
    CxSpaceLLMConnector,
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
    
    def __init__(self, registry: ServiceRegistry, event_bus: EventBus, config=None):
        self.registry = registry
        self.event_bus = event_bus
        self.config = config
        
        # Initialize connectors
        self.ml = MLServiceConnector(registry, event_bus)
        self.webhook = WebhookConnector(registry, event_bus)
        self.research = ResearchAgentConnector(registry, event_bus)
        self.jupyterbook = JupyterBookConnector(registry, event_bus)
        self.superset = SupersetConnector(registry, event_bus)
        self.cxspacellm = CxSpaceLLMConnector(registry, event_bus, config)
        
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
        enrich_with_ai: bool = True,
    ) -> dict[str, Any]:
        """
        Run complete ML workflow with optional CxSpaceLLM enrichment.
        
        Steps:
        1. Train model
        2. Enrich with CxSpaceLLM insights (if enabled)
        3. Optionally send webhook notification
        4. Return results
        """
        logger.info("Starting ML workflow")
        
        # Train model
        train_result = await self.ml.train(data)
        model_id = train_result["model_id"]
        
        # Enrich with CxSpaceLLM if enabled
        if enrich_with_ai and self.cxspacellm.enabled:
            try:
                dataflow_data = {
                    "id": model_id,
                    "type": "ml_training",
                    "status": "complete",
                    "data": train_result
                }
                enriched = await self.cxspacellm.enrich_dataflow(dataflow_data)
                train_result["ai_insights"] = enriched.get("ai_insights")
                logger.info(f"Enriched ML workflow with CxSpaceLLM insights")
            except Exception as e:
                logger.error(f"Failed to enrich with CxSpaceLLM: {e}")
        
        # Send webhook if URL provided
        if webhook_url:
            try:
                await self.webhook.send_webhook(webhook_url, {
                    "event": "ml.train.complete",
                    "model_id": model_id,
                    "score": train_result.get("score"),
                    "ai_insights": train_result.get("ai_insights"),
                })
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")
        
        return train_result
    
    async def run_research_workflow(
        self,
        repo: str,
        generate_docs: bool = True,
        enrich_with_ai: bool = True,
    ) -> dict[str, Any]:
        """
        Run research and documentation workflow with optional CxSpaceLLM enrichment.
        
        Steps:
        1. Analyze repository
        2. Enrich with CxSpaceLLM insights (if enabled)
        3. Generate documentation
        4. Return results
        """
        logger.info(f"Starting research workflow for {repo}")
        
        # Analyze repo
        analysis = await self.research.analyze_repo(repo)
        
        # Enrich with CxSpaceLLM if enabled
        if enrich_with_ai and self.cxspacellm.enabled:
            try:
                dataflow_data = {
                    "id": repo,
                    "type": "research_analysis",
                    "status": "complete",
                    "data": analysis
                }
                enriched = await self.cxspacellm.enrich_dataflow(dataflow_data)
                analysis["ai_insights"] = enriched.get("ai_insights")
                logger.info(f"Enriched research workflow with CxSpaceLLM insights")
            except Exception as e:
                logger.error(f"Failed to enrich with CxSpaceLLM: {e}")
        
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
        enrich_with_ai: bool = True,
    ) -> dict[str, Any]:
        """
        Run analytics and visualization workflow with optional CxSpaceLLM enrichment.
        
        Steps:
        1. Get model information
        2. Enrich with CxSpaceLLM insights (if enabled)
        3. Create Superset dashboard
        4. Return results
        """
        logger.info(f"Starting analytics workflow for model {model_id}")
        
        # Get model details
        models = await self.ml.list_models()
        model = next((m for m in models.get("models", []) if m.get("model_id") == model_id), None)
        
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        result = {"model": model}
        
        # Enrich with CxSpaceLLM if enabled
        if enrich_with_ai and self.cxspacellm.enabled:
            try:
                dataflow_data = {
                    "id": model_id,
                    "type": "analytics",
                    "status": "complete",
                    "data": model
                }
                enriched = await self.cxspacellm.enrich_dataflow(dataflow_data)
                result["ai_insights"] = enriched.get("ai_insights")
                logger.info(f"Enriched analytics workflow with CxSpaceLLM insights")
            except Exception as e:
                logger.error(f"Failed to enrich with CxSpaceLLM: {e}")
        
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
    
    async def enrich_dataflow(self, dataflow_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich any dataflow with CxSpaceLLM insights.
        
        Args:
            dataflow_data: Dataflow data to enrich
            
        Returns:
            Enriched dataflow data
        """
        if not self.cxspacellm.enabled:
            logger.warning("CxSpaceLLM is not enabled, returning original dataflow")
            return dataflow_data
        
        try:
            return await self.cxspacellm.enrich_dataflow(dataflow_data)
        except Exception as e:
            logger.error(f"Failed to enrich dataflow: {e}")
            return dataflow_data
    
    async def analyze_dataflow_with_ai(
        self,
        dataflow_data: dict[str, Any],
        custom_prompt: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze dataflow data using CxSpaceLLM.
        
        Args:
            dataflow_data: Dataflow data to analyze
            custom_prompt: Optional custom prompt for analysis
            
        Returns:
            Analysis results from CxSpaceLLM
        """
        if not self.cxspacellm.enabled:
            raise RuntimeError("CxSpaceLLM is not enabled")
        
        return await self.cxspacellm.analyze_data(dataflow_data, custom_prompt)


def create_orchestrator(registry: ServiceRegistry, event_bus: EventBus, config=None) -> WorkflowOrchestrator:
    """Create a workflow orchestrator with CxSpaceLLM support."""
    return WorkflowOrchestrator(registry, event_bus, config)
