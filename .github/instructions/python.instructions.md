---
applyTo: "**/*.py"
---

# Python Code Instructions for CXFlow

## Style & Standards

- Follow **PEP 8** style guide strictly
- Use **type hints** for all function parameters and return types
- Prefer Python 3.10+ style type hints: `list[str]` over `List[str]`
- Maximum line length: 100 characters (not 79)
- Use double quotes for strings consistently
- One import per line, grouped and sorted:
  1. Standard library imports
  2. Third-party imports
  3. Local application imports

## Type Hints

Always use type hints with modern Python syntax:

```python
from typing import Any

# Good
def process_data(items: list[dict], threshold: float = 0.5) -> dict[str, Any]:
    pass

# Not this
def process_data(items, threshold=0.5):
    pass
```

For complex types, use from `typing`:
```python
from typing import Optional, Callable
from collections.abc import Awaitable

async def fetch(url: str) -> Optional[dict]:
    pass

def apply(func: Callable[[int], str]) -> str:
    pass
```

## FastAPI Services

All microservices use FastAPI with this standard structure:

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    """Use Pydantic settings for configuration."""
    service_name: str = "my-service"
    port: int = 8000
    
    class Config:
        env_prefix = "MY_SERVICE_"

class RequestModel(BaseModel):
    """Use Pydantic models for request/response validation."""
    data: list[dict]
    threshold: float = Field(ge=0.0, le=1.0)

app = FastAPI(title="My Service")

@app.get("/health")
async def health_check() -> dict:
    """All services MUST have a /health endpoint."""
    return {"status": "healthy", "service": "my-service"}

@app.post("/process")
async def process(request: RequestModel) -> dict:
    """Use async/await for all endpoints."""
    try:
        # Process logic here
        return {"status": "success", "results": []}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

## Error Handling

Always use specific exception handling:

```python
# Good
try:
    result = await some_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    raise HTTPException(status_code=503, detail="Service unavailable")

# Avoid bare except
except:  # BAD - don't do this
    pass
```

## Logging

Use Python's logging module:

```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.info("Starting operation")
    logger.debug(f"Processing item: {item}")
    logger.warning("Potential issue detected")
    logger.error("Operation failed", exc_info=True)
```

## Async/Await

- Use `async def` for I/O-bound operations
- Await all async calls
- Use `asyncio.gather()` for parallel operations

```python
async def fetch_multiple(urls: list[str]) -> list[dict]:
    """Fetch multiple URLs in parallel."""
    tasks = [fetch_one(url) for url in urls]
    return await asyncio.gather(*tasks)
```

## CXFlow Core Integration

When working with CXFlow Core services:

```python
from cxflow_core import (
    CXFlowConfig,
    ServiceRegistry,
    EventBus,
    Event,
    EventPriority,
    MLServiceConnector
)

# Configuration
config = CXFlowConfig()

# Service Registry
registry = ServiceRegistry()
registry.register("my-service", "http://localhost:8000", version="1.0.0")
url = registry.find_service("ml")  # Returns healthy service URL

# Event Bus
bus = EventBus()
await bus.publish(Event(
    type="data.processed",
    data={"id": "123"},
    priority=EventPriority.HIGH
))

# Subscribe to events
async def handle_event(event: Event) -> None:
    logger.info(f"Received event: {event.type}")

bus.subscribe("data.*", handle_event)

# Service Connectors
ml = MLServiceConnector(config)
result = await ml.train_model(data=[...], target="label")
```

## Data Validation with Pydantic

Always validate data with Pydantic models:

```python
from pydantic import BaseModel, Field, validator

class DataItem(BaseModel):
    id: str
    value: float = Field(ge=0, description="Must be non-negative")
    tags: list[str] = []
    
    @validator('id')
    def id_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('ID cannot be empty')
        return v.strip()
```

## File Operations

Use pathlib for file operations:

```python
from pathlib import Path

# Good
config_file = Path("config") / "settings.json"
if config_file.exists():
    data = config_file.read_text()

# Not this
import os
config_file = os.path.join("config", "settings.json")
```

## Common Patterns

### ML Service Pattern

```python
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
import joblib

def train_model(X, y):
    """Train and save model."""
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = Path("models") / f"model_{timestamp}.joblib"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    
    return {"model_id": model_path.stem, "path": str(model_path)}
```

### Workflow Pattern

```python
from workflows import EnhancedCXFlowWorkflow, MemoryQuery

workflow = EnhancedCXFlowWorkflow(enable_versioning=True)

# Query memory
results = workflow.query_memory(
    category="config",
    tags=["production"]
)

# Execute macro
execution = workflow.execute_macro_by_name(
    "daily_sync",
    context={"source": "api", "destination": "db"}
)
```

## Testing

Use pytest for all Python tests:

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def sample_data():
    return [{"id": 1, "value": 10}, {"id": 2, "value": 20}]

@pytest.mark.asyncio
async def test_async_function(sample_data):
    """Test async functions with pytest-asyncio."""
    result = await process_async(sample_data)
    assert result["status"] == "success"

def test_with_mock():
    """Use mocks for external dependencies."""
    mock_client = Mock()
    mock_client.fetch.return_value = {"data": []}
    
    result = process_with_client(mock_client)
    assert result is not None
    mock_client.fetch.assert_called_once()
```

## Documentation

Use Google-style docstrings:

```python
def complex_function(param1: str, param2: int, flag: bool = False) -> dict:
    """Brief description of what the function does.
    
    Longer description if needed, explaining the function's behavior,
    side effects, or important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        flag: Description of flag (default: False)
    
    Returns:
        Dictionary containing:
            - status: Operation status
            - result: Processed result
    
    Raises:
        ValueError: If param1 is empty
        ConnectionError: If unable to connect to service
    
    Example:
        >>> result = complex_function("test", 42, flag=True)
        >>> print(result["status"])
        'success'
    """
    pass
```

## Environment Variables

Use pydantic-settings for configuration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings from environment."""
    service_name: str
    port: int = 8000
    debug: bool = False
    api_token: str
    
    class Config:
        env_prefix = "MY_APP_"
        env_file = ".env"

settings = Settings()
```

## Common Mistakes to Avoid

1. ❌ Don't use mutable default arguments
```python
# Bad
def add_item(item, items=[]):
    items.append(item)
    return items

# Good
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

2. ❌ Don't use bare except clauses
3. ❌ Don't mix sync and async code without proper handling
4. ❌ Don't use global variables for state
5. ❌ Don't hardcode file paths - use Path objects

## Running Python Code

Always run Python modules from the repository root:

```bash
# Good
python -m research_agent clone owner/repo
python -m workflows.cxflow_enhanced memory query

# Not this
cd research_agent && python __main__.py
```

## Dependencies

- Keep `requirements.txt` files minimal and pinned
- Use `pip install -r requirements.txt` for installation
- Never commit virtual environment directories
- Document any system dependencies

## CxSpaceLLM Integration

When using AI enrichment:

```python
from cxflow_core.workflows import create_orchestrator

orchestrator = create_orchestrator(registry, bus, config)

# Enrich dataflow with AI insights
result = await orchestrator.run_ml_workflow(
    data=training_data,
    enrich_with_ai=True  # Enable CxSpaceLLM enrichment
)

if "ai_insights" in result:
    logger.info(f"AI insights: {result['ai_insights']}")
```
