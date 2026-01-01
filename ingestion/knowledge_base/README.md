# Knowledge Base Ingestion from Power Automate

This package handles data ingestion from Power Automate workflows into a local knowledge base.

## Configuration

The ingestion is configured to fetch data from:

```
https://3eeeffe7fbb2ec6eac086222fffec8.14.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/3a852aa38d424061b03c0ba231fffc37/triggers/manual/paths/invoke
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POWER_AUTOMATE_WEBHOOK_URL` | Base webhook URL | (configured URL) |
| `POWER_AUTOMATE_SIG` | Signature for authentication | (configured signature) |
| `KNOWLEDGE_BASE_PATH` | Storage path for ingested data | `./data/knowledge_base` |

## Usage

### Python API

```python
from ingestion.knowledge_base import (
    PowerAutomateClient,
    KnowledgeBaseIngestor,
    IngestionConfig,
)

# Simple ingestion
ingestor = KnowledgeBaseIngestor()
result = ingestor.ingest()

print(f"Processed: {result.items_processed}")
print(f"Stored: {result.items_stored}")

# With custom configuration
config = IngestionConfig(
    storage_path=Path("./my_knowledge_base"),
    timeout=60,
    max_retries=5,
)
ingestor = KnowledgeBaseIngestor(config)

# With data transformation
def transform_item(item):
    return {
        "id": item["Id"],
        "title": item["Title"],
        "content": item["Content"],
        "created_at": item["CreatedDate"],
    }

result = ingestor.ingest(transformer=transform_item)

# Paginated ingestion
result = ingestor.ingest_all(page_size=100, max_pages=10)

# Access stored items
items = ingestor.get_stored_items()
item = ingestor.get_item("item-id-123")
```

### CLI

```bash
# Run ingestion
python -m ingestion.knowledge_base.cli ingest

# Paginated ingestion
python -m ingestion.knowledge_base.cli ingest --paginated --page-size 50

# List stored items
python -m ingestion.knowledge_base.cli list
python -m ingestion.knowledge_base.cli list --format json

# Check endpoint health
python -m ingestion.knowledge_base.cli health

# Clear stored data
python -m ingestion.knowledge_base.cli clear --force
```

## Storage Structure

```
data/knowledge_base/
├── raw/           # Raw responses from Power Automate
├── processed/     # Processed and validated items
├── failed/        # Items that failed validation/processing
└── logs/          # Ingestion logs
```

## Integration with Other Systems

### Laravel/PHP

```php
// Call Python ingestion from Laravel
$result = shell_exec('python -m ingestion.knowledge_base.cli ingest 2>&1');

// Or use HTTP client directly
$response = Http::get(config('services.power_automate.webhook_url'), [
    'api-version' => '1',
    'sp' => '/triggers/manual/run',
    'sv' => '1.0',
    'sig' => config('services.power_automate.sig'),
]);
```

### Scheduled Ingestion

Add to crontab:
```cron
0 * * * * cd /path/to/project && python -m ingestion.knowledge_base.cli ingest >> /var/log/kb-ingestion.log 2>&1
```

Or use Laravel scheduler:
```php
// app/Console/Kernel.php
$schedule->exec('python -m ingestion.knowledge_base.cli ingest')
    ->hourly()
    ->appendOutputTo(storage_path('logs/kb-ingestion.log'));
```
