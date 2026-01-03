# CXFlow - GitHub Copilot Instructions

This repository contains **CXFlow**, a comprehensive data integration and automation platform combining Laravel (PHP), Python microservices, and Docker infrastructure.

## Project Architecture

CXFlow is a multi-technology stack platform with:

- **PHP/Laravel Application** (in `src/`) - Main web application with Apache + MySQL
- **Python Services** - Multiple microservices for ML, research, automation
- **CXFlow Core** (`cxflow_core/`) - Unified integration layer with API Gateway, Event Bus, Service Registry
- **Docker Infrastructure** - Complete containerized development environment

### Key Components

1. **CXFlow Core** (Python) - Port 8100
   - API Gateway: Unified entry point for all services
   - Service Registry: Dynamic service discovery and health tracking
   - Event Bus: Pub/sub messaging between components
   - Workflow Orchestrator: Cross-service automation

2. **ML Service** (`ml/`) - Port 8090
   - FastAPI-based AutoML microservice
   - Automated training and prediction
   - Uses scikit-learn, pandas, numpy, shap

3. **Research Agent** (`research_agent/`) - Port 8002
   - Python tool for cloning and analyzing GitHub repositories
   - Builds inverted indexes and generates markdown reports

4. **Webhook Engine** (`webhook_engine/`) - Port 8001
   - Event processing and distribution

5. **JupyterBook Builder** (`jupyterbook/`) - Port 8003
   - Documentation generation service

6. **Ingestion & Orchestration** (`ingestion/`)
   - PHP scripts for data ingestion, validation, and routing
   - Auto-validation, smart routing, self-healing capabilities
   - Integration with Supabase Storage

7. **Workflows** (`workflows/`)
   - Python automation workflows
   - Enhanced memory management with versioning
   - Macro execution engine with conditionals and loops
   - Power Automate synchronization

8. **CxSpaceLLM Integration**
   - AI-powered dataflow enrichment using GitHub Models
   - Automatic insights generation for workflows

## Technology Stack

### Backend
- **PHP 8.3** with Laravel framework
- **Python 3.11+** for microservices
- **MySQL 8.0** - Primary database
- **Redis** - Cache and queue backend
- **Apache** - Web server with mod_rewrite

### Python Frameworks & Libraries
- FastAPI, uvicorn - API services
- Pydantic - Data validation
- scikit-learn, pandas, numpy - ML and data processing
- httpx, click - HTTP client and CLI tools

### Infrastructure
- **Docker & Docker Compose** - Containerization
- phpMyAdmin - Database management UI
- Mailhog - SMTP testing
- Node/Vite - Frontend tooling

## Development Workflow

### Starting the Environment

```bash
# Initialize Laravel (if not exists)
bin/init

# Start all services
bin/up  # or bin/dev for foreground

# Start CXFlow Core API Gateway
python cxflow.py gateway

# Check system health
curl http://localhost:8100/system/health
```

### Build & Test Commands

```bash
# Lint all code (Python, PHP, Bash, Docker)
bin/lint

# Run tests (lint + optional smoke test)
bin/test

# Smoke test with Docker
SMOKE_DOCKER=1 bin/test

# Run specific Python tests
python -m pytest ml/
python -m pytest workflows/

# PHP Artisan commands
bin/artisan migrate
bin/artisan test
```

### Common Development Tasks

```bash
# Laravel/PHP
bin/composer install          # Install PHP dependencies
bin/artisan migrate          # Run migrations
bin/shell                    # Shell into app container

# Python Services
python -m research_agent --help
python -m workflows.cxflow_enhanced memory query

# ML Automation
php artisan ml:automate --sync

# Assistant/AI commands
php artisan assistant:run "Your prompt"
```

## Coding Standards & Best Practices

### General Principles

1. **Keep secrets out of git** - Use `.env` files (ignored by git)
2. **Minimal changes** - Make surgical, focused modifications
3. **Follow existing patterns** - Match the style of surrounding code
4. **Validate changes** - Test before committing

### PHP/Laravel Code

- Follow **PSR-12** coding standards
- Use Laravel conventions:
  - Models in `app/Models/`
  - Controllers in `app/Http/Controllers/`
  - Services in `app/Services/`
  - Jobs in `app/Jobs/`
- Use type hints for method parameters and return types
- Prefer dependency injection over facades where appropriate
- Use Laravel's helper functions: `config()`, `env()`, `cache()`, etc.
- Database connection: `DB_HOST=db` (Docker service name)

**Example PHP Pattern:**
```php
<?php

namespace App\Services;

class MyService
{
    public function __construct(
        private readonly OtherService $otherService
    ) {}

    public function process(string $input): array
    {
        // Implementation
        return ['status' => 'success'];
    }
}
```

### Python Code

- Follow **PEP 8** style guide
- Use **type hints** consistently (Python 3.10+ style)
- Prefer **Pydantic models** for data validation in APIs
- Use **async/await** for FastAPI endpoints
- Structure imports: standard library, third-party, local
- Use descriptive variable names

**Example Python Pattern:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class TrainingRequest(BaseModel):
    data: list[dict]
    target_column: str

@app.post("/train")
async def train_model(request: TrainingRequest) -> dict:
    """Train a model with the provided data."""
    # Implementation
    return {"status": "success", "model_id": "123"}
```

### FastAPI Services

- All microservices use **FastAPI** with **uvicorn**
- Standard structure: `/health` endpoint for health checks
- Use **Pydantic settings** for configuration
- Return structured responses with proper HTTP status codes

### Docker & Infrastructure

- Use `docker compose` (not `docker-compose`)
- Service names in docker-compose.yml are DNS names
- Environment variables: Define in `.env` (root) and `src/.env` (Laravel)
- Health checks: Include for critical services

### File Organization

- **Scripts in `bin/`** - Use for common operations
- **Stubs in `.stubs/`** - Reusable code templates
- **Examples in `examples/` or `*/examples/`** - Reference implementations
- **Documentation in `docs/`** - Markdown files for features
- **Tests alongside code** - `test_*.py` or Laravel tests in `tests/`

## Environment Variables

### Required for CXFlow Core
```bash
# CxSpaceLLM Integration
CXSPACELLM_ENABLED=true
CXSPACELLM_TOKEN=your_github_models_token
CXSPACELLM_MODEL=CxSpaceLLM
CXSPACELLM_BASE_URL=https://models.inference.ai.azure.com
```

### Laravel/PHP
```bash
DB_CONNECTION=mysql
DB_HOST=db
DB_PORT=3306
DB_DATABASE=laravel
DB_USERNAME=laravel
DB_PASSWORD=secret

REDIS_HOST=redis
REDIS_PORT=6379
```

### ML & Automation
```bash
ML_AUTOMATION_ENABLED=true
ML_AUTOMATION_SOURCE=/path/to/data.csv
ML_AUTOMATION_TARGET=target_column
```

## Service Integration Patterns

### Using the API Gateway

All services are accessible through the unified gateway on port 8100:

```bash
# Access ML service
curl http://localhost:8100/ml/health

# Check system services
curl http://localhost:8100/system/services
```

### Event Bus Pattern

Services communicate via the Event Bus:

```python
from cxflow_core import EventBus, Event, EventPriority

bus = EventBus()
await bus.publish(Event(
    type="training.completed",
    data={"model_id": "123"},
    priority=EventPriority.NORMAL
))
```

### Service Connectors

Use type-safe connectors for inter-service communication:

```python
from cxflow_core import MLServiceConnector, CXFlowConfig

config = CXFlowConfig()
ml = MLServiceConnector(config)
result = await ml.train_model(data, target="label")
```

## Common Patterns & Examples

### Ingestion Pipeline

PHP scripts in `ingestion/` follow this pattern:
1. Fetch/receive data
2. Auto-validation (schema, quality checks)
3. Auto-transformation (type inference, cleaning)
4. Smart routing (with failover)
5. Store artifacts in `ingestion/runs/<run_id>/`

### Workflow Automation

Python workflows use enhanced features:
```python
from workflows import EnhancedCXFlowWorkflow

workflow = EnhancedCXFlowWorkflow(enable_versioning=True)
results = workflow.query_memory(category="config", tags=["prod"])
execution = workflow.execute_macro_by_name("daily_sync", context={})
```

### Assistant/AI Integration

Server-side AI assistance (not exposed to end users):
```bash
php artisan assistant:run "Review this code" \
    --context-file=src/MyClass.php \
    --template=code-review
```

## Security & Secrets

- **Never commit secrets** - Use `.env` files and GitHub Secrets
- **Service role keys** - Store in environment variables
- **API tokens** - Never hardcode, use config files
- **Validation** - Always validate external input
- **Sanitization** - Use appropriate escaping for output context

## Testing Strategy

1. **Linting** - `bin/lint` (fast, no secrets needed)
2. **Unit Tests** - Python pytest, PHP PHPUnit
3. **Integration Tests** - Test service interactions
4. **Smoke Tests** - `SMOKE_DOCKER=1 bin/test` (end-to-end)

## Documentation References

- Main README: `README.md`
- Usage Guide: `USAGE.md`
- Quick Reference: `QUICK_REFERENCE.md`
- CXFlow Core: `cxflow_core/README.md`
- Enhanced Features: `docs/CXFLOW_ENHANCED.md`
- Automation: `docs/ENHANCED_AUTOMATION.md`
- Integration: `docs/INTEGRATION_GUIDE.md`

## Key Files to Know

- `cxflow.py` - Main entry point for CXFlow Core CLI
- `docker-compose.yml` - Service orchestration
- `.env.example` - Environment variable template
- `bin/lint` - Linting script (Python, PHP, Bash, Docker)
- `bin/test` - Test runner
- `bin/init` - Initialize Laravel application

## When Adding New Features

1. **Follow the existing service structure** - Look at similar components
2. **Add health endpoints** - For new services
3. **Update documentation** - Add to relevant docs in `docs/`
4. **Include examples** - Add to `examples/` or service directory
5. **Environment variables** - Document in `.env.example`
6. **Integration** - Register in Service Registry if it's a service
7. **Tests** - Add appropriate test coverage

## AI/Assistant Usage

This repository includes internal AI assistance capabilities:
- **CxSpaceLLM** - GitHub Models integration for dataflow enrichment
- **Assistant Service** - Laravel service for AI tasks (server-side only)
- **Keep AI interactions invisible to end users** - Process internally, return normal responses
- **Disclose automated processing** - In privacy policy where required
- **Use for:** Code review, summarization, data enrichment, automation

## Common Gotchas

1. **DB_HOST=db** not `localhost` (Docker networking)
2. **Use docker service names** for inter-service communication
3. **Secrets in .env** - Never commit real tokens/keys
4. **Port conflicts** - Check `.env` for port assignments
5. **Python modules** - Run from repository root: `python -m module_name`
6. **Permissions** - Run `bin/perm` if hitting permission issues
7. **Disable pagers** - Use `git --no-pager` in scripts

## Support & Troubleshooting

- Check service health: `curl http://localhost:8100/system/health`
- View logs: `bin/logs app` or `docker compose logs service_name`
- Verify environment: Check `.env` and `src/.env`
- Run lint: `bin/lint` to catch syntax issues
- Service discovery: `python cxflow.py services`

---

**Remember:** This is a development environment. Production deployments require proper secrets management, TLS, backups, and security hardening.
