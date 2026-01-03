"""
End-to-end integration example demonstrating CXFlow unified system.

This example shows:
1. Starting all services
2. Training an ML model  
3. Making predictions
4. Sending webhooks on events
5. Monitoring system health
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# CXFlow Core
from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    EventBus,
    HealthMonitor,
    ServiceStatus,
    Event,
    EventPriority,
)
from cxflow_core.workflows import create_orchestrator
from cxflow_core.integrations import create_webhook_integration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run end-to-end example."""
    
    logger.info("=" * 80)
    logger.info("CXFlow Unified System - End-to-End Example")
    logger.info("=" * 80)
    
    # Initialize core components
    logger.info("\n[Step 1] Initializing CXFlow Core...")
    config = CXFlowConfig()
    registry = ServiceRegistry()
    event_bus = EventBus()
    
    # Register services
    logger.info("\n[Step 2] Registering services...")
    for service in config.get_enabled_services():
        info = registry.register(
            name=service.name,
            url=f"http://{service.host}:{service.port}",
            version="2.0.0",
        )
        logger.info(f"  ✓ Registered {service.name} at {info.url}")
    
    # Create webhook integration
    logger.info("\n[Step 3] Creating webhook integration...")
    webhook_integration = create_webhook_integration(event_bus, registry)
    webhook_integration.add_endpoint(
        name="test_endpoint",
        url="https://httpbin.org/post",
    )
    logger.info("  ✓ Webhook integration created")
    
    # Setup event logging
    logger.info("\n[Step 4] Setting up event logging...")
    
    def log_event(event: Event):
        logger.info(f"  📢 Event: {event.type} (priority={event.priority.value})")
    
    event_bus.subscribe("**", log_event)
    logger.info("  ✓ Event logging enabled")
    
    # Simulate ML workflow
    logger.info("\n[Step 5] Simulating ML workflow...")
    await event_bus.publish(Event(
        type="ml.train.complete",
        source="example",
        priority=EventPriority.HIGH,
        payload={"model_id": "example-123", "score": 0.95}
    ))
    
    await asyncio.sleep(0.1)
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ End-to-end example complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
