# CX Performance Capacity Ingestion from Power Automate

This package handles data ingestion from Power Automate workflows for CX Performance Capacity data.

## Configuration

The ingestion is configured to fetch data from:

```
https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/1a760c48e4904f5caa00edab64671623/triggers/manual/paths/invoke
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CX_CAPACITY_WEBHOOK_URL` | Base webhook URL | (configured URL) |
| `CX_CAPACITY_SIG` | Signature for authentication | (configured signature) |
| `CX_CAPACITY_PATH` | Storage path for ingested data | `./data/cx_performance/capacity` |

## Usage

### Python API

```python
from ingestion.cx_performance.capacity import (
    PowerAutomateClient,
    CapacityIngestor,
    IngestionConfig,
)

# Simple ingestion
ingestor = CapacityIngestor()
result = ingestor.ingest()

print(f"Processed: {result.items_processed}")
print(f"Stored: {result.items_stored}")

# With custom configuration
config = IngestionConfig(
    storage_path=Path("./my_capacity_data"),
    timeout=60,
    max_retries=5,
)
ingestor = CapacityIngestor(config)

# With data transformation
def transform_item(item):
    return {
        "capacity_id": item["CapacityId"],
        "current_capacity": item["CurrentCapacity"],
        "max_capacity": item["MaxCapacity"],
        "utilization_pct": item.get("UtilizationPercent"),
        "timestamp": item["Timestamp"],
    }

result = ingestor.ingest(transformer=transform_item)

# Paginated ingestion
result = ingestor.ingest_all(page_size=100, max_pages=10)

# Access stored items
items = ingestor.get_stored_items()
item = ingestor.get_item("capacity-id-123")
```

### CLI

```bash
# Run ingestion
python -m ingestion.cx_performance.capacity.cli ingest

# Paginated ingestion
python -m ingestion.cx_performance.capacity.cli ingest --paginated --page-size 50

# List stored items
python -m ingestion.cx_performance.capacity.cli list
python -m ingestion.cx_performance.capacity.cli list --format json

# Check endpoint health
python -m ingestion.cx_performance.capacity.cli health

# Clear stored data
python -m ingestion.cx_performance.capacity.cli clear --force
```

## Storage Structure

```
data/cx_performance/capacity/
├── raw/           # Raw responses from Power Automate
├── processed/     # Processed and validated items
├── failed/        # Items that failed validation/processing
└── logs/          # Ingestion logs
```

## Scheduled Ingestion

Add to crontab:
```cron
0 * * * * cd /path/to/project && python -m ingestion.cx_performance.capacity.cli ingest >> /var/log/cx-capacity-ingestion.log 2>&1
```

Or use Laravel scheduler:
```php
// app/Console/Kernel.php
$schedule->exec('python -m ingestion.cx_performance.capacity.cli ingest')
    ->hourly()
    ->appendOutputTo(storage_path('logs/cx-capacity-ingestion.log'));
```
