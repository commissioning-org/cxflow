# CXFlow Core Integration

Unified integration layer that wires together all CXFlow components into a cohesive system.

## Overview

CXFlow Core provides:

- **Service Registry**: Dynamic service discovery and health tracking
- **Event Bus**: Pub/sub messaging between services
- **API Gateway**: Unified entry point for all services
- **Health Monitor**: Automated health checks and status tracking
- **Service Connectors**: Type-safe clients for all services
- **Workflow Orchestrator**: Cross-service workflow coordination

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       API Gateway                            │
│                    (Port 8100)                               │
└───┬─────────────────────────────────────────────────────┬───┘
    │                                                     │
    ├─────────────────┬───────────────┬──────────────────┤
    │                 │               │                  │
┌───▼───┐      ┌─────▼─────┐  ┌─────▼──────┐    ┌─────▼─────┐
│  ML   │      │  Webhook  │  │  Research  │    │Jupyterbook│
│Service│      │  Engine   │  │   Agent    │    │           │
│:8000  │      │   :8001   │  │   :8002    │    │   :8003   │
└───────┘      └───────────┘  └────────────┘    └───────────┘
    │                 │               │                  │
    └─────────────────┴───────────────┴──────────────────┘
                          │
                    ┌─────▼──────┐
                    │ Event Bus  │
                    │  (Memory)  │
                    └────────────┘
```

## Quick Start

### Installation

```bash
cd cxflow_core
pip install -r requirements.txt
```

### Start the Gateway

```bash
# Start all services (via docker-compose)
docker-compose up -d

# Start the API Gateway
python ../cxflow.py gateway --host 0.0.0.0 --port 8100
```

### Check System Health

```bash
# List all services
python ../cxflow.py services

# Check specific service
python ../cxflow.py check ml

# View system info
python ../cxflow.py info
```

## Components

### Service Registry

Tracks all running services and their health status.

```python
from cxflow_core import ServiceRegistry, ServiceStatus

registry = ServiceRegistry()

# Register a service
registry.register("ml", "http://ml:8000", version="2.0.0")

# Update status
registry.update_status("ml", ServiceStatus.HEALTHY)

# Find healthy service
url = registry.find_service("ml")
```

### Event Bus

Pub/sub messaging for cross-service communication.

```python
from cxflow_core import EventBus, Event, EventPriority

bus = EventBus()

# Subscribe to events
def on_ml_complete(event: Event):
    print(f"Model trained: {event.payload['model_id']}")

bus.subscribe("ml.train.complete", on_ml_complete)

# Publish event
bus.publish_sync(Event(
    type="ml.train.complete",
    source="ml_service",
    priority=EventPriority.HIGH,
    payload={"model_id": "abc123"}
))
```

### Service Connectors

Type-safe clients for all services.

```python
from cxflow_core import ServiceRegistry, EventBus
from cxflow_core.connectors import MLServiceConnector

registry = ServiceRegistry()
registry.register("ml", "http://ml:8000")
registry.update_status("ml", ServiceStatus.HEALTHY)

bus = EventBus()
ml = MLServiceConnector(registry, bus)

# Train model
result = await ml.train({
    "rows": [...],
    "target": "label",
})

# Make predictions
predictions = await ml.predict(model_id, rows)
```

### Workflow Orchestrator

Coordinate workflows across services.

```python
from cxflow_core.workflows import create_orchestrator

orchestrator = create_orchestrator(registry, bus)

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

# Run analytics workflow
analytics = await orchestrator.run_analytics_workflow(
    model_id="abc123",
    create_dashboard=True
)
```

## API Gateway Endpoints

The gateway provides unified access to all services:

### System Endpoints

- `GET /health` - Gateway health check
- `GET /system/health` - All services health
- `GET /system/services` - List registered services
- `GET /system/events` - Event history

### Service Proxies

- `/ml/*` - Proxy to ML Service
- `/webhook/*` - Proxy to Webhook Engine
- `/research/*` - Proxy to Research Agent
- `/jupyterbook/*` - Proxy to JupyterBook
- `/superset/*` - Proxy to Superset

### Example Requests

```bash
# Check system health
curl http://localhost:8100/system/health

# List all services
curl http://localhost:8100/system/services

# Train a model (via gateway)
curl -X POST http://localhost:8100/ml/train \
  -H "Content-Type: application/json" \
  -d '{"rows": [...], "target": "label"}'

# View event history
curl http://localhost:8100/system/events?limit=50
```

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

# Research Agent
export RESEARCH_HOST=localhost
export RESEARCH_PORT=8002
export RESEARCH_ENABLED=true

# JupyterBook
export JUPYTERBOOK_HOST=localhost
export JUPYTERBOOK_PORT=8003
export JUPYTERBOOK_ENABLED=true

# Event Bus
export EVENT_BUS_ENABLED=true
export EVENT_BUS_BACKEND=memory
```

## Testing

Run the test suite:

```bash
cd cxflow_core
pytest tests/ -v
```

## CLI Commands

```bash
# Start API Gateway
cxflow gateway [--host HOST] [--port PORT]

# Run health monitoring
cxflow monitor [--interval SECONDS]

# List services
cxflow services

# Check service health
cxflow check SERVICE_NAME

# Show system info
cxflow info
```

## Integration Examples

### Complete ML Workflow

```python
import asyncio
from cxflow_core import CXFlowConfig, ServiceRegistry, EventBus, ServiceStatus
from cxflow_core.workflows import create_orchestrator

async def main():
    # Setup
    config = CXFlowConfig()
    registry = ServiceRegistry()
    bus = EventBus()
    
    # Register services
    registry.register("ml", "http://ml:8000")
    registry.update_status("ml", ServiceStatus.HEALTHY)
    
    registry.register("webhook_engine", "http://webhook:8001")
    registry.update_status("webhook_engine", ServiceStatus.HEALTHY)
    
    # Create orchestrator
    orchestrator = create_orchestrator(registry, bus)
    
    # Run workflow
    result = await orchestrator.run_ml_workflow(
        data={
            "rows": [...],
            "target": "label",
        },
        webhook_url="https://example.com/webhook"
    )
    
    print(f"Model ID: {result['model_id']}")
    print(f"Score: {result['score']}")

asyncio.run(main())
```

### Research and Documentation

```python
async def research_workflow():
    orchestrator = create_orchestrator(registry, bus)
    
    # Analyze repository and generate docs
    result = await orchestrator.run_research_workflow(
        repo="tensorflow/tensorflow",
        generate_docs=True
    )
    
    print(f"Analysis: {result}")
    print(f"Documentation: {result.get('documentation')}")
```

## Features

### ✅ Implemented

- Service registry with health tracking
- Event bus with pub/sub messaging
- API Gateway with request routing
- Health monitoring with periodic checks
- Service connectors for all components
- Workflow orchestrator
- CLI interface
- Configuration management
- Integration tests

### 🚧 Future Enhancements

- Redis-based event bus backend
- Service mesh integration
- Distributed tracing
- Rate limiting per service
- Circuit breaker patterns
- Service authentication/authorization
- Metrics and observability dashboard

## Architecture Decisions

1. **Event Bus**: In-memory by default, pluggable backend for production
2. **Service Discovery**: Registry-based with health checks
3. **API Gateway**: FastAPI for high performance and async support
4. **Connectors**: Type-safe async clients with event integration
5. **Configuration**: Environment variables with sensible defaults

## License

See main repository LICENSE.
