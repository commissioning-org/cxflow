# CXFlow Integration Guide

Complete guide for integrating and wiring all CXFlow capabilities.

## System Architecture

CXFlow provides a unified integration layer that connects all components:

```
┌──────────────────────────────────────────────────────────────────┐
│                      CXFlow Core Integration                      │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Registry │  │Event Bus │  │ Gateway  │  │ Health Monitor    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────────────┘ │
└───────┼─────────────┼─────────────┼──────────────┼───────────────┘
        │             │             │              │
  ┌─────┴─────┬───────┴───────┬─────┴─────┬────────┴─────────┐
  │           │               │           │                  │
┌─▼───┐  ┌───▼────┐    ┌─────▼────┐  ┌──▼─────┐  ┌────────▼──────┐
│ ML  │  │Webhook │    │ Research │  │Jupyter │  │   Superset    │
│     │  │Engine  │    │  Agent   │  │ Book   │  │               │
└─────┘  └────────┘    └──────────┘  └────────┘  └───────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd cxflow_core
pip install -r requirements.txt
```

### 2. Start Services with Docker

```bash
docker-compose up -d
```

### 3. Start the API Gateway

```bash
python cxflow.py gateway
```

### 4. Verify System Health

```bash
# Check gateway
curl http://localhost:8100/health

# Check all services
curl http://localhost:8100/system/health

# List services
curl http://localhost:8100/system/services
```

## Integration Components

### 1. Service Registry

The registry tracks all services and their health status.

```python
from cxflow_core import ServiceRegistry, ServiceStatus

registry = ServiceRegistry()

# Register a service
registry.register("ml", "http://ml:8000", version="2.0.0")

# Update health status
registry.update_status("ml", ServiceStatus.HEALTHY)

# Find healthy service
url = registry.find_service("ml")
```

### 2. Event Bus

Pub/sub messaging for cross-service communication.

```python
from cxflow_core import EventBus, Event, EventPriority

bus = EventBus()

# Subscribe to events
def on_ml_complete(event: Event):
    print(f"Model trained: {event.payload['model_id']}")

bus.subscribe("ml.train.complete", on_ml_complete)

# Publish events
await bus.publish(Event(
    type="ml.train.complete",
    source="ml_service",
    priority=EventPriority.HIGH,
    payload={"model_id": "abc123"}
))
```

### 3. API Gateway

Unified entry point for all services.

```bash
# Access services through gateway
curl http://localhost:8100/ml/health
curl http://localhost:8100/ml/models

# Send training request
curl -X POST http://localhost:8100/ml/train \
  -H "Content-Type: application/json" \
  -d '{"rows": [...], "target": "label"}'
```

### 4. Service Connectors

Type-safe clients for all services.

```python
from cxflow_core.connectors import MLServiceConnector

ml = MLServiceConnector(registry, event_bus)

# Train model
result = await ml.train({
    "rows": training_data,
    "target": "label",
})

# Make predictions
predictions = await ml.predict(model_id, test_data)
```

### 5. Workflow Orchestrator

Coordinate complex workflows across services.

```python
from cxflow_core.workflows import create_orchestrator

orchestrator = create_orchestrator(registry, event_bus)

# Run ML workflow with webhook notification
result = await orchestrator.run_ml_workflow(
    data=training_data,
    webhook_url="https://example.com/webhook"
)

# Run research and documentation workflow
analysis = await orchestrator.run_research_workflow(
    repo="username/repo",
    generate_docs=True
)
```

### 6. Webhook Integration

Event-driven webhook notifications.

```python
from cxflow_core.integrations import create_webhook_integration

webhook_integration = create_webhook_integration(event_bus, registry)

# Add webhook endpoint
webhook_integration.add_endpoint(
    name="power_automate",
    url="https://prod-123.westus.logic.azure.com:443/workflows/..."
)

# Events automatically trigger webhooks:
# - ml.train.complete
# - ml.predict.complete
# - ingestion.complete
# - workflow.*
# - research.analyze.complete
```

## Complete Integration Example

```python
import asyncio
from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    EventBus,
    ServiceStatus,
)
from cxflow_core.workflows import create_orchestrator
from cxflow_core.integrations import create_webhook_integration

async def main():
    # Setup
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Register services
    for service in config.get_enabled_services():
        registry.register(
            name=service.name,
            url=f"http://{service.host}:{service.port}"
        )
    
    # Create integrations
    webhook = create_webhook_integration(bus, registry)
    webhook.add_endpoint("webhook", "https://example.com/webhook")
    
    orchestrator = create_orchestrator(registry, bus)
    
    # Mark services as healthy
    registry.update_status("ml", ServiceStatus.HEALTHY)
    registry.update_status("webhook_engine", ServiceStatus.HEALTHY)
    
    # Run workflow
    result = await orchestrator.run_ml_workflow(
        data={"rows": [...], "target": "label"},
        webhook_url="https://example.com/webhook"
    )
    
    print(f"Model ID: {result['model_id']}")
    print(f"Score: {result['score']}")

asyncio.run(main())
```

## Event Types

The system publishes these event types:

### ML Events
- `ml.train.start` - Training started
- `ml.train.complete` - Training completed
- `ml.predict.start` - Prediction started
- `ml.predict.complete` - Prediction completed

### Ingestion Events
- `ingestion.start` - Ingestion started
- `ingestion.complete` - Ingestion completed
- `ingestion.failed` - Ingestion failed

### Workflow Events
- `workflow.ml_complete` - ML workflow completed
- `workflow.research_complete` - Research workflow completed

### Research Events
- `research.analyze.start` - Analysis started
- `research.analyze.complete` - Analysis completed

### System Events
- `gateway.proxy.*` - Gateway proxy requests
- `service.register` - Service registered
- `service.unregister` - Service unregistered
- `service.status_change` - Service status changed

## Configuration

Configure via environment variables:

```bash
# Gateway
export GATEWAY_PORT=8100
export GATEWAY_ENABLED=true

# ML Service
export ML_HOST=ml
export ML_PORT=8000
export ML_ENABLED=true

# Webhook Engine
export WEBHOOK_HOST=localhost
export WEBHOOK_PORT=8001
export WEBHOOK_ENABLED=true

# Event Bus
export EVENT_BUS_ENABLED=true
export EVENT_BUS_BACKEND=memory
```

## CLI Commands

```bash
# Start API Gateway
python cxflow.py gateway [--host HOST] [--port PORT]

# Run health monitoring
python cxflow.py monitor [--interval SECONDS]

# List services
python cxflow.py services

# Check service health
python cxflow.py check SERVICE_NAME

# Show system info
python cxflow.py info
```

## Docker Compose Integration

Add the gateway service to `docker-compose.yml`:

```yaml
services:
  gateway:
    build:
      context: .
      dockerfile: .docker/gateway/Dockerfile
    container_name: cxflow_gateway
    ports:
      - "8100:8100"
    environment:
      - GATEWAY_PORT=8100
      - ML_HOST=ml
      - ML_PORT=8000
      - WEBHOOK_HOST=localhost
      - WEBHOOK_PORT=8001
    depends_on:
      - ml
```

## Testing

Run the integration tests:

```bash
cd cxflow_core
pytest tests/ -v
```

Run the end-to-end example:

```bash
python examples/end_to_end_integration.py
```

## Monitoring

### System Health

```bash
curl http://localhost:8100/system/health
```

Returns:
```json
{
  "total": 5,
  "healthy": 4,
  "degraded": 0,
  "unhealthy": 1,
  "unknown": 0,
  "services": [
    {
      "name": "ml",
      "status": "healthy",
      "url": "http://ml:8000",
      "last_check": "2026-01-03T00:45:00.000Z"
    }
  ]
}
```

### Event History

```bash
curl http://localhost:8100/system/events?limit=50
```

### Service List

```bash
curl http://localhost:8100/system/services
```

## Troubleshooting

### Service Not Available

If a service shows as unavailable:

1. Check service is running: `docker ps`
2. Check health endpoint: `curl http://ml:8000/health`
3. Check registry: `python cxflow.py services`
4. Update status: See service integration code

### Events Not Publishing

1. Check event bus is enabled: `EVENT_BUS_ENABLED=true`
2. Verify subscriptions: Check `event_bus.get_topics()`
3. Check event history: `event_bus.get_history()`

### Webhooks Not Sending

1. Verify webhook integration is created
2. Check endpoints are registered
3. Verify event subscriptions
4. Check webhook engine logs

## Next Steps

1. **Add Custom Services**: Extend the registry with your own services
2. **Create Custom Events**: Define domain-specific event types
3. **Build Workflows**: Create complex multi-service workflows
4. **Add Monitoring**: Integrate with Prometheus/Grafana
5. **Scale Services**: Deploy with Kubernetes

## Resources

- CXFlow Core README: [`cxflow_core/README.md`](cxflow_core/README.md)
- End-to-End Example: [`examples/end_to_end_integration.py`](examples/end_to_end_integration.py)
- API Documentation: See individual service docs
- Community: See main README for links
