# ML Automation Platform - Documentation

## Overview

This is an integrated internal ML platform stub that combines:
- **Grok (GitHub Models)**: OpenAI-compatible chat API with retry/backoff
- **AutoML**: Microservice client for automated training
- **MLOps Automation**: End-to-end pipeline with dataset ingestion, training, and model management
- **Persistence**: Eloquent models for datasets, models, and runs
- **Webhooks**: Configurable event notifications with payload sampling and redaction
- **API**: Internal REST endpoints for triggering runs and managing models

## Environment Variables

### Core ML Automation

```bash
# Enable/disable the ML automation pipeline
ML_AUTOMATION_ENABLED=true

# Enable/disable internal API endpoints
ML_AUTOMATION_API_ENABLED=false

# Storage configuration
ML_AUTOMATION_STORAGE_DISK=local
ML_AUTOMATION_STORAGE_PATH=ml

# Dataset ingestion
ML_AUTOMATION_MAX_ROWS=5000
ML_AUTOMATION_INGEST_TIMEOUT_SECONDS=30
ML_AUTOMATION_INCLUDE_ROWS=false
ML_AUTOMATION_SAMPLE_ROWS=50

# Default pipeline configuration
ML_AUTOMATION_SOURCE=/path/to/data.csv
ML_AUTOMATION_FORMAT=auto
ML_AUTOMATION_TARGET=target_column
ML_AUTOMATION_PROBLEM=classification
ML_AUTOMATION_METRIC=accuracy
ML_AUTOMATION_AUTO_PROMOTE=true

# Assistant (model card generation)
ML_AUTOMATION_ASSISTANT_ENABLED=true
ML_AUTOMATION_MODEL_CARD_ENABLED=true
```

### Webhooks

```bash
# ML Automation webhooks
ML_AUTOMATION_WEBHOOK_ENABLED=false
ML_AUTOMATION_WEBHOOK_URL=https://your-webhook-url.com
ML_AUTOMATION_WEBHOOK_TIMEOUT_SECONDS=15

# Full payload mode (forces include_rows=true, sampling=0)
ML_AUTOMATION_WEBHOOK_FULL_PAYLOAD=false

# Individual controls (ignored if full_payload=true)
ML_AUTOMATION_WEBHOOK_INCLUDE_ROWS=false
ML_AUTOMATION_WEBHOOK_SAMPLE_ROWS=50

# Event mode: multiple|single|both
ML_AUTOMATION_WEBHOOK_MODE=multiple
ML_AUTOMATION_WEBHOOK_SINGLE_EVENT=ml.data
ML_AUTOMATION_WEBHOOK_SINGLE_SUMMARY=false

# Security: redact sensitive keys
ML_AUTOMATION_WEBHOOK_REDACT_KEYS=password,token,secret,api_key
ML_AUTOMATION_WEBHOOK_TRUNCATE_LENGTH=0

# AutoML webhooks (similar structure)
AUTOML_WEBHOOK_ENABLED=false
AUTOML_WEBHOOK_URL=https://your-webhook-url.com
AUTOML_WEBHOOK_FULL_PAYLOAD=false
AUTOML_WEBHOOK_INCLUDE_ROWS=false
AUTOML_WEBHOOK_SAMPLE_ROWS=50
AUTOML_WEBHOOK_SAMPLE_PREDICTIONS=200
AUTOML_WEBHOOK_REDACT_KEYS=password,token,secret
AUTOML_WEBHOOK_TRUNCATE_LENGTH=0
```

### AutoML Service

```bash
AUTOML_BASE_URL=http://ml:8000
AUTOML_TIMEOUT_SECONDS=60
```

### GitHub Models (Grok)

```bash
# Required: GitHub Models API token
GITHUB_MODELS_TOKEN=your_token_here

# Optional overrides
GITHUB_MODELS_BASE_URL=https://models.inference.ai.azure.com
GITHUB_MODELS_MODEL=grok-3
GITHUB_MODELS_ALLOW_OTHER_MODELS=false
GITHUB_MODELS_TIMEOUT_SECONDS=60

# Retry configuration (for 429, 5xx errors)
GITHUB_MODELS_RETRIES=2
GITHUB_MODELS_RETRY_BASE_DELAY_MS=250
GITHUB_MODELS_RETRY_MAX_DELAY_MS=2000
GITHUB_MODELS_RETRY_JITTER_MS=150
```

## CLI Commands

### Run ML Automation Pipeline

```bash
# Synchronous execution (waits for completion)
php artisan ml:automate --sync

# Asynchronous execution (returns result key)
php artisan ml:automate

# With overrides
php artisan ml:automate \
  --pipeline=default \
  --source=/path/to/data.csv \
  --target=price \
  --problem=regression \
  --metric=r2
```

### Monitor ML Runs

```bash
php artisan ml:monitor
```

## API Endpoints

**Important**: API endpoints are disabled by default. Enable with `ML_AUTOMATION_API_ENABLED=true`.

**Security**: In production, protect these routes with authentication middleware (e.g., Sanctum, JWT).

### Base URL

All endpoints are prefixed with `/internal/ml`

### Create ML Run

**POST** `/internal/ml/runs`

Trigger a new ML automation run.

**Request Body:**
```json
{
  "pipeline": "default",
  "async": true,
  "overrides": {
    "source": "/path/to/data.csv",
    "target": "price",
    "problem": "regression",
    "metric": "r2"
  }
}
```

**Response (async=true):**
```json
{
  "ok": true,
  "trace_id": "uuid",
  "result_key": "ml:result:uuid",
  "message": "Run dispatched. Poll status using result_key or run_uuid."
}
```

**Response (async=false):**
```json
{
  "ok": true,
  "trace_id": "uuid",
  "run_uuid": "uuid",
  "artifact": { ... }
}
```

### Get Run Status

**GET** `/internal/ml/runs/{run_uuid}`

Get status and results of a specific run.

**Response:**
```json
{
  "ok": true,
  "run": {
    "run_uuid": "uuid",
    "pipeline": "default",
    "kind": "train",
    "status": "completed",
    "payload": { ... },
    "result": { ... },
    "error": null,
    "started_at": "2025-01-01T12:00:00Z",
    "finished_at": "2025-01-01T12:05:00Z"
  }
}
```

### Get Run Artifact

**GET** `/internal/ml/runs/{run_uuid}/artifact`

Retrieve the stored artifact for a run.

**Response:**
```json
{
  "ok": true,
  "artifact": {
    "run_uuid": "uuid",
    "dataset_uuid": "uuid",
    "model_uuid": "uuid",
    "pipeline": "default",
    "dataset": { ... },
    "train": { ... },
    "model_card": { ... }
  }
}
```

### List Models

**GET** `/internal/ml/models?status=active&limit=10`

List models with optional filters.

**Query Parameters:**
- `status` (optional): `candidate`, `active`, or `archived`
- `dataset_uuid` (optional): Filter by dataset
- `limit` (optional): Max results (1-100, default 20)

**Response:**
```json
{
  "ok": true,
  "models": [
    {
      "model_uuid": "uuid",
      "dataset_uuid": "uuid",
      "automl_model_id": "model_123",
      "status": "active",
      "problem": "classification",
      "metric": "accuracy",
      "score": 0.95,
      "features": ["col1", "col2"],
      "train_result": { ... },
      "model_card": { ... },
      "trained_at": "2025-01-01T12:00:00Z",
      "promoted_at": "2025-01-01T12:05:00Z"
    }
  ]
}
```

### Promote Model

**POST** `/internal/ml/models/{model_uuid}/promote`

Manually promote a model to active status.

**Response:**
```json
{
  "ok": true,
  "message": "Model promoted to active",
  "model_uuid": "uuid",
  "promoted_at": "2025-01-01T12:10:00Z"
}
```

## Database Schema

### ml_datasets

Stores ingested datasets.

- `dataset_uuid`: Unique identifier
- `name`: Dataset name
- `source`: Source path/URL
- `schema`: Column definitions
- `row_count`: Number of rows
- `target`: Target column name
- `meta`: Additional metadata (includes trace_id, run_uuid)

### ml_models

Stores trained models.

- `model_uuid`: Unique identifier
- `dataset_uuid`: Reference to dataset
- `automl_model_id`: AutoML service model ID
- `status`: `candidate`, `active`, or `archived`
- `problem`: Problem type (classification, regression)
- `metric`: Evaluation metric
- `score`: Model score
- `features`: Feature list
- `train_result`: Training results
- `model_card`: Generated model card
- `meta`: Additional metadata (includes trace_id, run_uuid, pipeline)
- `trained_at`: Training completion timestamp
- `promoted_at`: Promotion timestamp

### ml_runs

Stores execution runs.

- `run_uuid`: Unique identifier
- `pipeline`: Pipeline name
- `kind`: Run type (default: `train`)
- `status`: `running`, `completed`, or `failed`
- `payload`: Input configuration
- `result`: Output artifact
- `error`: Error message (if failed)
- `started_at`: Start timestamp
- `finished_at`: Completion timestamp

## Traceability

Every run generates a unique `trace_id` that propagates through:
- Pipeline execution
- AutoML client calls
- Webhook events
- Database records (in `meta` fields)
- Cached results

Use `trace_id` to correlate logs, events, and database records for debugging.

## Webhook Events

### Event Structure

```json
{
  "event": "ml.run.started",
  "event_version": 1,
  "timestamp": "2025-01-01T12:00:00Z",
  "app": {
    "name": "MyApp",
    "env": "production"
  },
  "data": {
    "trace_id": "uuid",
    "run_uuid": "uuid",
    "pipeline": "default",
    ...
  }
}
```

### Event Types

- `ml.run.started`: Run initiated
- `ml.ingest.completed`: Dataset loaded
- `ml.ingest.failed`: Dataset loading failed
- `ml.train.completed`: Training succeeded
- `ml.train.failed`: Training failed
- `ml.run.completed`: Run finished successfully
- `ml.run.payload`: Aggregated summary (if `single_summary=true`)
- `automl.train.completed`: AutoML training succeeded
- `automl.train.failed`: AutoML training failed
- `automl.predict.completed`: AutoML prediction succeeded
- `automl.predict.failed`: AutoML prediction failed

### Payload Sampling & Redaction

**Full Payload Mode** (`full_payload=true`):
- Forces `include_rows=true`
- Forces `sample_rows=0` (no sampling)
- Includes complete data in webhooks
- ⚠️ Can be very large and may include sensitive data

**Sampled Mode** (default):
- `include_rows=false`: Excludes raw rows
- `sample_rows=50`: Includes first N rows as sample
- Smaller, safer payloads

**Redaction**:
- `redact_keys`: Comma-separated list of keys to redact (e.g., `password,token,secret`)
- `truncate_length`: Truncate string values longer than N characters

## Safety & Security

1. **Never commit secrets**: Use environment variables for tokens and URLs
2. **Protect API endpoints**: Add authentication middleware in production
3. **Limit data exposure**: Use sampling and redaction for webhooks
4. **Monitor trace_id**: Track operations for debugging and auditing
5. **Review model cards**: Ensure no provider/vendor names are exposed
6. **Control auto-promotion**: Disable `auto_promote` if manual review is required

## Example Workflow

1. **Configure environment**:
   ```bash
   ML_AUTOMATION_ENABLED=true
   ML_AUTOMATION_SOURCE=/data/sales.csv
   ML_AUTOMATION_TARGET=revenue
   GITHUB_MODELS_TOKEN=your_token
   ```

2. **Run pipeline via CLI**:
   ```bash
   php artisan ml:automate --sync
   ```

3. **Or via API** (if enabled):
   ```bash
   curl -X POST http://localhost/internal/ml/runs \
     -H "Content-Type: application/json" \
     -d '{"pipeline":"default","async":true}'
   ```

4. **Check status**:
   ```bash
   curl http://localhost/internal/ml/runs/{run_uuid}
   ```

5. **List active models**:
   ```bash
   curl http://localhost/internal/ml/models?status=active
   ```

6. **Manually promote a model**:
   ```bash
   curl -X POST http://localhost/internal/ml/models/{model_uuid}/promote
   ```

## Architecture Notes

- **Separation of concerns**: Webhooks, persistence, and pipeline logic are decoupled
- **Resilience**: Webhook failures never break core logic
- **Flexibility**: Multiple pipelines can be configured
- **Observability**: Comprehensive event emission and trace_id propagation
- **Extensibility**: Easy to add new endpoints or pipeline steps
