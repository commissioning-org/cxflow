# Power Automate Sync Workflow

Comprehensive workflow for syncing memory, macros, metadata, and data to Microsoft Power Automate.

## Overview

This module provides a complete solution for pushing CXFlow data to Power Automate webhooks, enabling integration with Microsoft 365 automation workflows.

## Architecture

```
workflows/
├── __init__.py                 # Module exports
├── power_automate_sync.py      # Core sync implementation
└── execute_sync.py             # CLI execution script
```

## Quick Start

### 1. Simple Sync

```python
from workflows import sync_to_power_automate

# Sync all data
result = sync_to_power_automate()

if result.status.value == "completed":
    print(f"✅ Synced {result.items_sent} items in {result.duration_ms}ms")
else:
    print(f"❌ Failed: {result.errors}")
```

### 2. Memory Operations

```python
from workflows import set_memory, get_memory

# Store data in memory
set_memory("session_id", "abc123", category="session", ttl_seconds=3600)
set_memory("user_preferences", {"theme": "dark"}, category="user")

# Retrieve data
session = get_memory("session_id")
print(session)  # "abc123"
```

### 3. Register Macros

```python
from workflows import register_macro

# Register an automation macro
register_macro(
    name="daily_report",
    description="Generate and send daily report",
    trigger="schedule",
    actions=[
        {"type": "collect", "source": "metrics"},
        {"type": "generate", "format": "pdf"},
        {"type": "email", "to": "team@example.com"},
    ]
)
```

### 4. Set Metadata

```python
from workflows import set_metadata

# Set entity metadata
set_metadata(
    entity_type="project",
    entity_id="cxflow",
    attributes={
        "version": "1.0.0",
        "status": "active",
        "owner": "team@example.com",
    }
)
```

### 5. Record Events

```python
from workflows import record_event

# Record application events
record_event("build_completed", {
    "project": "documentation",
    "format": "html",
    "pages": 42,
})
```

## Full Workflow Usage

```python
from workflows import CXFlowSyncWorkflow, SyncStatus

# Initialize workflow
workflow = CXFlowSyncWorkflow()

# Add memory entries
workflow.memory.set("config", {"debug": True}, category="system")
workflow.memory.set("cache_key", "v1.2.3", category="cache")

# Register macros
workflow.macros.register(
    name="refresh_data",
    description="Refresh all data sources",
    trigger="manual",
    actions=[
        {"type": "refresh", "source": "database"},
        {"type": "refresh", "source": "api"},
        {"type": "notify", "channel": "slack"},
    ]
)

# Set metadata
workflow.metadata.set("service", "api", {
    "endpoint": "/api/v1",
    "status": "healthy",
})

# Execute full sync
result = workflow.sync_all(
    include_metrics=True,
    include_logs=True,
    custom_data={"extra": "data"},
)

print(f"Status: {result.status.value}")
print(f"Items: {result.items_sent}")
print(f"Duration: {result.duration_ms}ms")
```

## Async Support

```python
import asyncio
from workflows import sync_to_power_automate_async, CXFlowSyncWorkflow

async def main():
    workflow = CXFlowSyncWorkflow()
    
    # Setup data...
    workflow.memory.set("async_test", True)
    
    # Async sync
    result = await workflow.sync_all_async(
        include_metrics=True,
        custom_data={"async": True},
    )
    
    return result

result = asyncio.run(main())
```

## CLI Usage

```bash
# Full sync
python -m workflows.power_automate_sync sync

# Sync with logs
python -m workflows.power_automate_sync sync --include-logs

# Memory operations
python -m workflows.power_automate_sync memory set --key "test" --value "hello"
python -m workflows.power_automate_sync memory get --key "test"
python -m workflows.power_automate_sync memory list
python -m workflows.power_automate_sync memory sync

# Macro operations
python -m workflows.power_automate_sync macro list
python -m workflows.power_automate_sync macro sync

# Check status
python -m workflows.power_automate_sync status
```

## Execute Sync Script

```bash
# Run the comprehensive sync
python workflows/execute_sync.py
```

Output:
```
============================================================
CXFlow Power Automate Sync
============================================================

📦 Initializing workflow...
📝 Setting up data...
🔍 Collecting workspace data...
   Found 5 modules
   - jupyterbook: 4 files
  - superset: 2 files
   - workflows: 3 files
   - ml: 2 files
   - ingestion: 5 files

📊 Data Summary:
   Memory entries: 5
   Macros: 4
   Metadata records: 5

🚀 Syncing to Power Automate...

============================================================
✅ SYNC COMPLETED SUCCESSFULLY
============================================================

Sync ID:      abc123def456
Status:       completed
Items sent:   14
Items failed: 0
Duration:     342ms
```

## Payload Structure

The sync sends a JSON payload to Power Automate:

```json
{
  "sync_id": "abc123def456",
  "sync_type": "full",
  "source": "cxflow",
  "environment": "development",
  "timestamp": "2025-12-31T12:00:00Z",
  
  "memory": [
    {
      "key": "session_id",
      "value": "xyz789",
      "category": "session",
      "timestamp": "2025-12-31T12:00:00Z",
      "ttl_seconds": 3600,
      "tags": ["active"],
      "metadata": {}
    }
  ],
  
  "macros": [
    {
      "name": "daily_sync",
      "description": "Daily sync of all data",
      "trigger": "schedule",
      "actions": [
        {"type": "collect", "source": "memory"},
        {"type": "sync", "destination": "power_automate"}
      ],
      "enabled": true,
      "version": "1.0.0",
      "metadata": {"schedule": "0 0 * * *"}
    }
  ],
  
  "metadata": [
    {
      "entity_type": "repository",
      "entity_id": "cxflow",
      "attributes": {
        "owner": "commissioning-org",
        "branch": "main"
      },
      "schema_version": "1.0",
      "source": "cxflow"
    }
  ],
  
  "data": {
    "collection": "workspace",
    "records": [...],
    "count": 10
  },
  
  "config": {
    "environment": "development",
    "debug": false,
    "version": "1.0.0"
  },
  
  "metrics": {
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "disk_percent": 30.1
  },
  
  "events": [
    {
      "type": "sync_initiated",
      "data": {"source": "api"},
      "timestamp": "2025-12-31T12:00:00Z"
    }
  ],
  
  "checksum": "sha256:...",
  "batch_info": {
    "system": {
      "hostname": "codespace",
      "platform": "Linux"
    },
    "item_counts": {
      "memory": 5,
      "macros": 4,
      "metadata": 5,
      "events": 2
    }
  }
}
```

## Power Automate Webhook Configuration

The webhook URL is configured in the module:

```python
POWER_AUTOMATE_WEBHOOK_URL = (
    "https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/workflows/3d2dbeba15b5425b8551f67e61084464"
    "/triggers/manual/paths/invoke"
    "?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=zcOVZS6oRhfwU-R6rTxxk8EW32faD-S-bcar0DiFfno"
)
```

### Custom Webhook URL

```python
from workflows import CXFlowSyncWorkflow

workflow = CXFlowSyncWorkflow(
    webhook_url="https://your-custom-webhook-url.com"
)
```

## Data Persistence

Data is persisted to `.cxflow/` directory:

```
.cxflow/
├── memory/
│   └── memory.json       # Memory entries
├── macros/
│   ├── daily_sync.json   # Macro definitions
│   └── build_docs.json
├── metadata/
├── events.json           # Event log
└── config.json           # Configuration
```

## Hooks

Add pre/post sync hooks for custom processing:

```python
def pre_sync_hook(context):
    print(f"Starting sync: {context['sync_id']}")
    # Add custom data, validate, etc.

def post_sync_hook(context):
    result = context['result']
    if result.status.value == "completed":
        print(f"Sync successful: {result.items_sent} items")
    else:
        # Alert, retry, etc.
        pass

workflow = CXFlowSyncWorkflow()
workflow.add_pre_sync_hook(pre_sync_hook)
workflow.add_post_sync_hook(post_sync_hook)

workflow.sync_all()
```

## Sync Types

| Type | Description |
|------|-------------|
| `full` | All data (memory, macros, metadata, config, events) |
| `memory` | Only memory entries |
| `macros` | Only macro definitions |
| `metadata` | Only metadata records |
| `data` | Custom data collections |
| `events` | Only events |
| `logs` | Application logs |
| `metrics` | System metrics |

## Error Handling

```python
from workflows import CXFlowSyncWorkflow, SyncStatus

workflow = CXFlowSyncWorkflow()
result = workflow.sync_all()

if result.status == SyncStatus.COMPLETED:
    print("Success!")
elif result.status == SyncStatus.PARTIAL:
    print(f"Partial: {result.items_sent} sent, {result.items_failed} failed")
elif result.status == SyncStatus.FAILED:
    print(f"Failed: {result.errors}")
    for error in result.errors:
        print(f"  - {error}")
```

## Compression

Large payloads (>100KB) are automatically compressed:

```python
from workflows import PowerAutomateSyncClient

client = PowerAutomateSyncClient(
    compress_threshold=1024 * 50,  # 50KB
)
```

Compressed payloads include:
- `compressed: true`
- `encoding: "gzip+base64"`
- `original_size` and `compressed_size`

## Retry Logic

Failed requests are automatically retried with exponential backoff:

- Default: 3 retries
- Backoff: 2^attempt seconds
- Timeout: 60 seconds per request

```python
client = PowerAutomateSyncClient(
    max_retries=5,
    timeout=120,
)
```

## Integration Examples

### With FastAPI

```python
from fastapi import FastAPI, BackgroundTasks
from workflows import CXFlowSyncWorkflow

app = FastAPI()
workflow = CXFlowSyncWorkflow()

@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    async def do_sync():
        await workflow.sync_all_async()
    
    background_tasks.add_task(do_sync)
    return {"status": "sync_started"}
```

### Scheduled Sync

```python
import schedule
import time
from workflows import sync_to_power_automate

def scheduled_sync():
    result = sync_to_power_automate()
    print(f"Scheduled sync: {result.status.value}")

# Run every hour
schedule.every().hour.do(scheduled_sync)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### With Power Automate Flow

In Power Automate, create a flow with:

1. **Trigger**: When an HTTP request is received
2. **Parse JSON**: Parse the incoming payload
3. **Condition**: Check `sync_type`
4. **Actions**: Process based on type
   - Store memory in Dataverse
   - Log events to SharePoint
   - Update Excel with metrics
   - Send Teams notification

## API Reference

### CXFlowSyncWorkflow

| Method | Description |
|--------|-------------|
| `sync_all()` | Full sync (synchronous) |
| `sync_all_async()` | Full sync (async) |
| `sync_memory()` | Sync only memory |
| `sync_macros()` | Sync only macros |
| `sync_metadata()` | Sync only metadata |
| `sync_data()` | Sync custom data |
| `sync_events()` | Sync events |

### MemoryManager

| Method | Description |
|--------|-------------|
| `set(key, value, ...)` | Set memory entry |
| `get(key)` | Get memory entry |
| `get_all(category)` | List all entries |
| `delete(key)` | Delete entry |
| `clear(category)` | Clear entries |
| `export_for_sync()` | Export for payload |

### MacroManager

| Method | Description |
|--------|-------------|
| `register(name, ...)` | Register macro |
| `get(name)` | Get macro |
| `list_all(enabled_only)` | List macros |
| `update(name, ...)` | Update macro |
| `delete(name)` | Delete macro |
| `export_for_sync()` | Export for payload |

### SyncResult

| Property | Type | Description |
|----------|------|-------------|
| `sync_id` | str | Unique sync identifier |
| `sync_type` | SyncType | Type of sync |
| `status` | SyncStatus | Result status |
| `items_sent` | int | Items successfully sent |
| `items_failed` | int | Items that failed |
| `duration_ms` | int | Duration in milliseconds |
| `errors` | List[str] | Error messages |
| `response_data` | Dict | Response from webhook |
