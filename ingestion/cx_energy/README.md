# CX Energy Ingestion from Power Automate

This package handles data ingestion from Power Automate workflows for CX Energy data.

## Configuration

The ingestion is configured to fetch data from:

```
https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/c04f210aa7d44ffea0d8d01e0a2d3dc8/triggers/manual/paths/invoke
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CX_ENERGY_WEBHOOK_URL` | Base webhook URL | (configured URL) |
| `CX_ENERGY_SIG` | Signature for authentication | (configured signature) |
| `CX_ENERGY_PATH` | Storage path for ingested data | `./data/cx_energy` |

## Usage

### Python API

```python
from ingestion.cx_energy import (
    PowerAutomateClient,
    CXEnergyIngestor,
    IngestionConfig,
)

# Simple ingestion
ingestor = CXEnergyIngestor()
result = ingestor.ingest()

print(f"Processed: {result.items_processed}")
print(f"Stored: {result.items_stored}")

# With custom configuration
config = IngestionConfig(
    storage_path=Path("./my_energy_data"),
    timeout=60,
    max_retries=5,
)
ingestor = CXEnergyIngestor(config)

# With data transformation
def transform_item(item):
    return {
        "meter_id": item["MeterId"],
        "reading": item["Reading"],
        "unit": item.get("Unit", "kWh"),
        "timestamp": item["Timestamp"],
    }

result = ingestor.ingest(transformer=transform_item)

# Paginated ingestion
result = ingestor.ingest_all(page_size=100, max_pages=10)

# Access stored items
items = ingestor.get_stored_items()
item = ingestor.get_item("meter-id-123")
```

### CLI

```bash
# Run ingestion
python -m ingestion.cx_energy.cli ingest

# Paginated ingestion
python -m ingestion.cx_energy.cli ingest --paginated --page-size 50

# List stored items
python -m ingestion.cx_energy.cli list
python -m ingestion.cx_energy.cli list --format json

# Check endpoint health
python -m ingestion.cx_energy.cli health

# Clear stored data
python -m ingestion.cx_energy.cli clear --force
```

## Storage Structure

```
data/cx_energy/
├── raw/           # Raw responses from Power Automate
├── processed/     # Processed and validated items
├── failed/        # Items that failed validation/processing
└── logs/          # Ingestion logs
```

## Scheduled Ingestion

Add to crontab:
```cron
0 * * * * cd /path/to/project && python -m ingestion.cx_energy.cli ingest >> /var/log/cx-energy-ingestion.log 2>&1
```

Or use Laravel scheduler:
```php
// app/Console/Kernel.php
$schedule->exec('python -m ingestion.cx_energy.cli ingest')
    ->hourly()
    ->appendOutputTo(storage_path('logs/cx-energy-ingestion.log'));
```
