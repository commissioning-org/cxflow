# Laravel (LAMP: Apache + MySQL + PHP) — Dockerized Dev Stack

This repository scaffolds a **Linux/Apache/MySQL/PHP** environment tailored for the **Laravel** framework.

## 🚀 New: Unified Integration Layer (CXFlow Core)

**CXFlow Core** provides a complete integration framework that wires together all services:

- **API Gateway** (`:8100`) - Single entry point for all services
- **Service Registry** - Dynamic service discovery with health tracking
- **Event Bus** - Pub/sub messaging between components
- **Workflow Orchestrator** - Cross-service automation
- **Service Connectors** - Type-safe clients for ML, Webhooks, Research, JupyterBook, Superset
- **CxSpaceLLM Integration** - GitHub Space AI model for dataflow enrichment ⭐ NEW

### Quick Start with Integrated System

```bash
# Start all services
docker-compose up -d

# Configure CxSpaceLLM (add to .env)
export CXSPACELLM_ENABLED=true
export CXSPACELLM_TOKEN=your_token_here
export CXSPACELLM_MODEL=CxSpaceLLM

# Start the API Gateway (unified access point)
python cxflow.py gateway

# Check system health
curl http://localhost:8100/system/health

# Access services via gateway
curl http://localhost:8100/ml/health
curl http://localhost:8100/system/services
```

**Full Documentation**: [`cxflow_core/README.md`](cxflow_core/README.md)

## 🤖 New: CxSpaceLLM - AI-Powered Dataflow Enrichment

**CxSpaceLLM** is now integrated into all dataflows, providing AI-powered insights and analysis:

### Key Features

- **🧠 Automatic Enrichment**: All dataflows can be automatically enriched with AI insights
- **📊 Data Analysis**: Analyze any dataflow data with natural language prompts
- **💡 Smart Insights**: Get recommendations, identify issues, and suggest improvements
- **🔄 Event-Driven**: Seamlessly integrated with the event bus for real-time processing
- **🎯 Workflow Integration**: Works with ML, Research, Analytics, and all other workflows

### Quick Example

```python
from cxflow_core import CXFlowConfig, ServiceRegistry, EventBus
from cxflow_core.workflows import create_orchestrator

# Setup
config = CXFlowConfig()
registry = ServiceRegistry()
bus = EventBus()
orchestrator = create_orchestrator(registry, bus, config)

# Run ML workflow with AI enrichment
result = await orchestrator.run_ml_workflow(
    data=training_data,
    enrich_with_ai=True  # Enable CxSpaceLLM enrichment
)

# Access AI-generated insights
print(result["ai_insights"])

# Or enrich any dataflow directly
enriched = await orchestrator.enrich_dataflow({"type": "custom", "data": {...}})
```

**Examples**: [`examples/cxspacellm_integration.py`](examples/cxspacellm_integration.py)

**Configuration**:
```bash
# Required environment variables
CXSPACELLM_ENABLED=true
CXSPACELLM_TOKEN=your_github_models_token
CXSPACELLM_MODEL=CxSpaceLLM
CXSPACELLM_BASE_URL=https://models.inference.ai.azure.com
CXSPACELLM_TIMEOUT_SECONDS=60
```

## 🚀 Significantly Enhanced Full Automation Capabilities

The CXFlow system now includes **significantly enhanced automation for ingestion, pipelines, dataflows, routing, and distribution with full no human intervention**:

### Core Automation Features

- **🔍 Auto-Validation**: Automatic data quality checks with schema detection, anomaly detection, and fix suggestions
- **🎯 Smart Routing**: Intelligent load balancing, automatic failover, circuit breaker, and retry with exponential backoff
- **⚡ Auto-Transformation**: Intelligent data transformation with type inference, missing value handling, and feature engineering
- **🔄 Self-Healing**: Automatic error recovery, rollback capabilities, and health monitoring
- **📊 Priority Queue**: Message prioritization, batch processing, and automatic deduplication
- **📈 Intelligent Monitoring**: Real-time anomaly detection with statistical methods (Z-score, IQR, MAD)
- **⚙️ Resource Optimization**: Automatic resource allocation, connection pool tuning, and performance optimization

### Workflow Enhancements

- **Advanced Query Engine**: Filter, search, and aggregate data with 11 operators
- **Macro Execution**: Actually execute macros with conditionals, loops, and transformations
- **Version Control**: Full history with rollback to any previous state
- **Audit Trail**: Complete logging for compliance and debugging
- **Template System**: 4 built-in templates for common patterns
- **Batch Operations**: Efficient bulk operations
- **Encryption Support**: Secure sensitive data

### Quick Example - Full Automation

```bash
# Enable all automation features
export CX_AUTO_VALIDATE=true
export CX_AUTO_TRANSFORM=true
export CX_SMART_ROUTING_ENABLED=true
export CX_ROUTER_TARGETS_JSON='[{"name":"primary","url":"https://api.example.com","priority":10}]'

# Run fully automated ingestion
php ingestion/cx_orchestrate.php "$CX_INGESTION_URI"

# Results include:
# - Validated data with quality report
# - Transformed data with schema changes
# - Smart routing results with failover
# - Complete audit trail
```

**Documentation**: 
- Enhanced Automation: [`docs/ENHANCED_AUTOMATION.md`](docs/ENHANCED_AUTOMATION.md)
- Workflow Features: [`docs/CXFLOW_ENHANCED.md`](docs/CXFLOW_ENHANCED.md)
- **Enhanced Macros: [`docs/ENHANCED_MACROS.md`](docs/ENHANCED_MACROS.md)** ⭐ NEW
- Enhancement Summary: [`docs/ENHANCEMENT_SUMMARY.md`](docs/ENHANCEMENT_SUMMARY.md)

**Examples**: 
- Run `python workflows/examples/enhanced_usage.py` for comprehensive demos
- **Run `python workflows/demo_enhanced_macros.py` for macro demonstrations** ⭐ NEW

## What you get

- **Apache + PHP 8.3** (with `mod_rewrite` enabled and `DocumentRoot` set to `public/`)
- **MySQL 8.0** with healthcheck
- **phpMyAdmin** (optional, enabled by default)
- **Redis** (cache/queue)
- **Mailhog** (SMTP testing + web UI)
- **Queue worker** container (`worker`)
- **Scheduler** container (`scheduler`)
- **Node/Vite** container (`node`) for frontend tooling
- **AutoML microservice** (`ml`) for automated training/prediction (internal)
- Helper scripts to initialize a fresh Laravel app into `./src`

## Quick start

1) Initialize the Laravel app (creates it inside `./src` if missing):

- `bin/init`

> If you want an internal “assistant” integration, `bin/init` will also install a small scaffold into `src/`.

2) (Recommended) Create your local Docker Compose env file:

- Copy `.env.example` to `.env` and set values as needed (especially `GITHUB_MODELS_TOKEN`).

3) Start the stack:

- Foreground: `bin/dev`
- Background: `bin/up`

3) Open in browser:

- App: http://localhost:8080 (or `APP_PORT`)
- phpMyAdmin: http://localhost:8081 (or `PHPMYADMIN_PORT`)
- Mailhog UI: http://localhost:8025 (or `MAILHOG_UI_PORT`)

AutoML service (dev only):

- Health: http://localhost:8090/health (or `ML_PORT`)

## Configuration

Docker Compose reads settings from the repo-root `.env` file (ports, MySQL credentials, optional assistant token).

This repo includes `.env.example`. Your real `.env` is ignored by git.

Laravel’s own environment file will live at:

- `src/.env`

After initialization, update `src/.env` to match your DB settings:

- `DB_HOST=db`
- `DB_PORT=3306`
- `DB_DATABASE=laravel`
- `DB_USERNAME=laravel`
- `DB_PASSWORD=secret`

## SQL Server (sqlsrv) support

This stack also supports **Microsoft SQL Server** (optional):

- The PHP image installs the `sqlsrv` and `pdo_sqlsrv` extensions.
- Docker Compose includes an optional `mssql` service.

### Use SQL Server from Laravel

In `src/.env`, set:

- `DB_CONNECTION=sqlsrv`
- `DB_HOST=mssql`
- `DB_DATABASE=...`
- `DB_USERNAME=sa`
- `DB_PASSWORD=YourStrong!Passw0rd`

Notes:

- SQL Server runs on port `1433` inside the Docker network; `DB_PORT` is often optional for `sqlsrv`.
- The reference repo you shared also mentions that sometimes commenting out `DB_PORT` can help with certain environments; if you hit connectivity issues, try removing `DB_PORT` for `sqlsrv`.

## Internal assistant integration

This scaffold adds (server-side only):

- `config/assistant.php`
- `App\Services\Assistant\AssistantClient`
- `App\Services\Assistant\AssistantService` (caching, retries, JSON helpers)
- `App\Jobs\RunAssistantTask` (queueable automation)
- `php artisan assistant:run` (internal CLI)

### Keep it invisible to end users

Nothing is added to your public routes by default. You call the service from your existing application flows and return your normal UI/API responses.

You should still disclose automated processing where required (privacy policy/terms), but you don’t need to expose provider/model details in responses.

### Secrets stay out of git

Set your token in one of these places:

- Repo root `.env` (picked up by Docker Compose and passed into the app container), **or**
- `src/.env` (Laravel env file)

Do **not** commit real tokens.

By default, the client enforces a single configured model (defaults to `grok-3`) but does not expose the model/provider to end users.

## Common commands

- Install PHP deps: `bin/composer install`
- Run Artisan: `bin/artisan migrate`
- Shell into app container: `bin/shell`
- Tail logs: `bin/logs app` (or `bin/logs worker` / `bin/logs scheduler`)
- Run a one-off queue worker: `bin/queue`
- Run scheduler once: `bin/schedule`
- Frontend tooling: `bin/npm install` or `bin/vite`
- Stop containers: `bin/down`

## Lint + smoke tests

- Lint (fast, secretless): `bin/lint`
- Tests (lint + optional Docker smoke test): `bin/test`

By default `bin/test` only runs `bin/lint`. To run a lightweight end-to-end smoke test (starts containers and hits health endpoints):

- `SMOKE_DOCKER=1 bin/test`

## CX ingestion orchestration + routing

The scheduled workflow runs ingestion and stores artifacts under `ingestion/runs/<run_id>/`.

If `ingestion/cx_orchestrate.php` is present, the workflow uses it to additionally generate:

- `event.json` (clean event envelope)
- optional `webhook.result.json`
- optional `route.*.result.json` (fan-out routing results)

To enable downstream routing (fan-out) from `cx_orchestrate.php`:

- `CX_ORCH_ROUTE_ENABLED=true`
- `CX_ORCH_TARGETS_JSON` = JSON array of targets, e.g.:
	- each target can set `name`, `url`, `timeout_seconds`, `headers` (secret), `include_manifest`, `include_rows`, `max_rows`, `max_ndjson_bytes`

Keep URLs/headers in GitHub Secrets or local `.env`; do not commit them.

## Automated file upload to Supabase Storage

This repo includes an internal uploader that can automatically upload ingestion artifacts and extracted files to **Supabase Storage**.

Files:
- `ingestion/supabase_upload.php` (uploads a run directory to Supabase Storage)
- `ingestion/cx_orchestrate.php` (will call the uploader automatically when enabled)

Enable (local/dev or in GitHub Actions via secrets):
- `SUPABASE_UPLOAD_ENABLED=true`
- `SUPABASE_PROJECT_URL=https://<project>.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=...` (secret)
- optional `SUPABASE_API_KEY=...` (secret; if omitted, service role key is used)

Upload config:
- `SUPABASE_BUCKET=cx-ingestion`
- `SUPABASE_PREFIX=runs/<run_id>` (default: `runs/<basename(run_dir)>`)
- `SUPABASE_UPSERT=true`
- `SUPABASE_TIMEOUT_SECONDS=30`
- `SUPABASE_INCLUDE_MANIFEST=true`
- `SUPABASE_INCLUDE_ROWS=true`
- `SUPABASE_INCLUDE_FILES=true`

The uploader writes `supabase.upload.result.json` into the run directory (and the scheduled workflow uploads it as an artifact).

## AutoML service (internal)

This repo includes an internal Python service in `./ml` that can:

- Train a simple model automatically (tries a small set of common estimators)
- Persist the best model and return a `model_id`
- Run predictions against saved models

Laravel integration stubs:

- `config/automl.php`
- `App\Services\Automl\AutomlClient`
- `App\Jobs\TrainAutomlModel`

Install into `src/` (after Laravel exists):

- `bin/integrate-automl`

## ML automation (applied ML, fully automated)

This repo also includes an **internal ML automation pipeline** that can run unattended:

1. Ingest dataset from a file path or HTTP JSON endpoint
2. Train via the internal AutoML microservice
3. Store a run artifact under `storage/app/ml/runs/*.json`
4. (Optional) emit webhook events for Power Automate
5. (Optional) generate an internal “model card” summary using the internal assistant layer

Install into `src/`:

- `bin/integrate-mlops`

After install, enable in `src/.env` (or repo root `.env` passed through Docker):

- `ML_AUTOMATION_ENABLED=true`
- `ML_AUTOMATION_SOURCE=/path/to/data.csv` (or `https://.../data.json`)
- `ML_AUTOMATION_TARGET=your_target_column` (optional; will be guessed if empty)

Run manually:

- `php artisan ml:automate --sync`

If you keep the `scheduler` service running, the installer also appends schedule hooks to `routes/console.php`.

## Notes

- This is intended for **local development**.
- For production, you’d typically use a separate deploy setup (real secrets management, TLS, backups, etc.).

## Security note (important)

If you use `src/database/storage.env` for Power Platform / Supabase connector work, treat it as **secret material**.

- `src/database/storage.env` is ignored by git.
- Use `src/database/storage.env.example` as a template.

If real keys were ever committed in git history, rotate them and consider rewriting history (e.g., via `git filter-repo`) to fully purge them.

## Dependabot automation (enhanced)

This repo ships with:

- **Dependabot** configuration (`.github/dependabot.yml`) for:
	- GitHub Actions (daily)
	- Python (`/ml/requirements.txt`) (daily)
	- Dockerfiles (`/ml/Dockerfile`, `/.docker/php/Dockerfile`) (daily)
	- Grouped PRs for patch/minor vs major where supported
- A **Dependabot PR review comment** workflow powered by the internal assistant endpoint
- An optional **auto-merge** workflow for Dependabot **patch/minor** updates (CI-gated)

### Required repo secrets

To enable the assistant review comment on Dependabot PRs, set these repository secrets:

- `ASSISTANT_API_KEY`
- `ASSISTANT_BASE_URL`
- `ASSISTANT_MODEL`

No secrets are committed to git.
